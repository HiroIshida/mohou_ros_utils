from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, List, Type, Dict
import math

from sensor_msgs.msg import Image, JointState
import genpy
import numpy as np
from mohou.types import AngleVector, ElementT, ElementBase, RGBImage, DepthImage
from tunable_filter.tunable import CompositeFilter, CropResizer, ResolutionChangeResizer

from mohou_ros_utils.config import Config


MessageT = TypeVar('MessageT', bound=genpy.Message)


def imgmsg_to_numpy(msg: Image) -> np.ndarray:  # actually numpy
    # NOTE: avoid cv_bridge for python3 on melodic
    # https://github.com/ros-perception/vision_opencv/issues/207
    image = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
    return image


def numpy_to_imgmsg(data: np.ndarray, encoding) -> Image:
    # NOTE: avoid cv_bridge for python3 on melodic
    # https://github.com/ros-perception/vision_opencv/issues/207

    assert encoding in ['rgb8', 'bgr8']

    # see: cv_bridge/core.py
    img_msg = Image()
    img_msg.height = data.shape[0]
    img_msg.width = data.shape[1]
    img_msg.encoding = encoding

    img_msg.data = data.tostring()  # type: ignore
    img_msg.step = len(img_msg.data) // img_msg.height

    if data.dtype.byteorder == '>':
        img_msg.is_bigendian = True
    return img_msg


class TypeConverter(ABC, Generic[MessageT, ElementT]):
    type_in: Type[MessageT]
    type_out: Type[ElementT]

    @abstractmethod
    def __call__(self, msg: MessageT) -> ElementT:
        pass


@dataclass
class RGBImageConverter(TypeConverter[Image, RGBImage]):
    image_filter: Optional[CompositeFilter] = None
    type_in = Image
    type_out = RGBImage

    @classmethod
    def from_config(cls, config: Config) -> 'RGBImageConverter':
        return cls(config.load_image_filter())

    def __call__(self, msg: Image) -> RGBImage:
        assert msg.encoding in ['bgr8', 'rgb8']
        image = imgmsg_to_numpy(msg)
        if self.image_filter is not None:
            image = self.image_filter(image)
        return RGBImage(image)


@dataclass
class DepthImageConverter(TypeConverter[Image, DepthImage]):
    image_filter: Optional[CompositeFilter] = None
    type_in = Image
    type_out = DepthImage

    @classmethod
    def from_config(cls, config: Config) -> 'DepthImageConverter':
        rgb_full_filter = config.load_image_filter()
        depth_filter = rgb_full_filter.extract_subfilter([CropResizer, ResolutionChangeResizer])
        return cls(depth_filter)

    def __call__(self, msg: Image) -> DepthImage:
        assert msg.encoding in ['32FC1']

        size = [msg.height, msg.width]
        buf: np.ndarray = np.ndarray(shape=(1, int(len(msg.data) / 4)), dtype=np.float32, buffer=msg.data)
        image = np.nan_to_num(buf.reshape(*size))
        if self.image_filter is not None:
            assert len(self.image_filter.logical_filters) == 0
            image = self.image_filter(image, True)
        image = np.expand_dims(image, axis=2)
        return DepthImage(image)


class AngleVectorConverter(TypeConverter[JointState, AngleVector]):
    type_in = JointState
    type_out = AngleVector
    control_joints: List[str]
    joint_indices: Optional[List[int]] = None

    def __init__(self, control_joints: List[str]):
        self.control_joints = control_joints

    def __call__(self, msg: JointState) -> AngleVector:

        if self.joint_indices is None:
            name_idx_map = {name: i for (i, name) in enumerate(msg.name)}
            self.joint_indices = [name_idx_map[name] for name in self.control_joints]

        def clamp_to_s1(something):
            lower_side = -math.pi
            return ((something - lower_side) % (2 * math.pi)) + lower_side

        angles = [clamp_to_s1(msg.position[idx]) for idx in self.joint_indices]
        return AngleVector(np.array(angles))


@dataclass
class VersatileConverter:
    converters: Dict[Type[ElementBase], TypeConverter]

    def __call__(self, msg: genpy.Message) -> ElementBase:

        if type(msg) == Image:
            if msg.encoding in ['rgb8', 'bgr8']:
                return self.converters[RGBImage](msg)
            elif msg.encoding == '32FC1':
                return self.converters[DepthImage](msg)
            else:
                assert False

        for converter in self.converters.values():
            # image is exceptional
            if converter.type_in == type(msg):
                return converter(msg)
        assert False, 'no converter compatible with {}'.format(type(msg))

    @classmethod
    def from_config(cls, config: Config):
        converters: Dict[Type[ElementBase], TypeConverter] = {}
        converters[RGBImage] = RGBImageConverter.from_config(config)
        converters[DepthImage] = DepthImageConverter.from_config(config)

        converters[AngleVector] = AngleVectorConverter(config.control_joints)
        return cls(converters)
