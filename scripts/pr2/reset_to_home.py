#!/usr/bin/env python3
import argparse

from skrobot.interfaces.ros import PR2ROSRobotInterface  # type: ignore
from skrobot.models import PR2

from mohou_ros_utils import _default_project_name
from mohou_ros_utils.config import Config

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-pn", type=str, default=_default_project_name, help="project name")
    parser.add_argument("--rarm", action="store_true", help="loose rarm")
    parser.add_argument("--larm", action="store_true", help="loose larm")
    parser.add_argument("--mirror", action="store_true", help="mirror mode")
    parser.add_argument("--home", action="store_true", help="use home position")
    parser.add_argument("-open", type=float, default=0.06, help="max gripper position")
    parser.add_argument("-close", type=float, default=0.00, help="max gripper position")

    args = parser.parse_args()
    loose_larm = args.larm
    loose_rarm = args.rarm
    pos_open = args.open
    pos_close = args.close
    mirror = args.mirror
    home = args.home
    config = Config.from_project_name(args.pn)

    robot = PR2()
    ri = PR2ROSRobotInterface(robot)

    assert config.home_position is not None

    for joint_name in config.home_position.keys():
        angle = config.home_position[joint_name]
        robot.__dict__[joint_name].joint_angle(angle)
    ri.angle_vector(robot.angle_vector(), time=2.0, time_scale=1.0)
    ri.move_gripper("larm", config.home_position["l_gripper_joint"], effort=100)
    ri.move_gripper("rarm", config.home_position["r_gripper_joint"], effort=100)
    ri.wait_interpolation()
