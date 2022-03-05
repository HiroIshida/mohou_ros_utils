from typing import List, Any, Optional, Tuple
import numpy as np

from mohou_ros_utils.types import TimeStampedSequence


def get_intersection_time_bound(seq_list: List[TimeStampedSequence]):
    t_start_list = [seq.time_list[0] for seq in seq_list]
    t_end_list = [seq.time_list[-1] for seq in seq_list]
    return max(t_start_list), min(t_end_list)


def get_union_time_bound(seq_list: List[TimeStampedSequence]):
    t_start_list = [seq.time_list[0] for seq in seq_list]
    t_end_list = [seq.time_list[-1] for seq in seq_list]
    return min(t_start_list), max(t_end_list)


def check_valid_bins(booleans: np.ndarray):
    # valid sequcen must not have a holl of False
    idx_first_valid = booleans.tolist().index(True)
    idx_last_valid = len(booleans) - booleans[::-1].tolist().index(True) - 1
    is_valid_bins = np.all(booleans[idx_first_valid:idx_last_valid])
    return is_valid_bins


def get_middle_bound(booleans: np.ndarray) -> Tuple[int, int]:
    idx_first_valid = booleans.tolist().index(True)
    idx_last_valid = len(booleans) - booleans[::-1].tolist().index(True) - 1
    return idx_first_valid, idx_last_valid


def synclonize(seq_list: List[TimeStampedSequence], freq: float):
    t_start, t_end = get_union_time_bound(seq_list)
    n_bins = int((t_end - t_start )//freq + 1) + 1

    NO_OBJECT_EXIST_FLAG = -999999

    def pack_to_bin(seq: TimeStampedSequence):
        binidx_to_seqidx = [NO_OBJECT_EXIST_FLAG for _ in range(n_bins)]
        binidxes = ((np.array(seq.time_list) - t_start) // freq).astype(int)

        for seqidx, binidx in enumerate(binidxes):
            if binidx > -1:
                binidx_to_seqidx[binidx] = seqidx

        return np.array(binidx_to_seqidx, dtype=int)

    table = np.array([pack_to_bin(seq) for seq in seq_list], dtype=int)

    # valid means all object exist in the equaly spaced bin
    bools_valid_bin = np.all(table != NO_OBJECT_EXIST_FLAG, axis=0)
    assert check_valid_bins(bools_valid_bin), 'seems frequence is too small. Set larger value.'

    t_bin_end_list = np.array([t_start + freq * (i + 0.5) for i in range(n_bins)])

    seq_list_new = []
    times_new = t_bin_end_list[bools_valid_bin]
    for seq, binidx_to_seqidx in zip(seq_list, table):
        object_list_new = []
        seqidx_list = binidx_to_seqidx[bools_valid_bin].tolist()
        object_list_new = [seq.object_list[idx] for idx in seqidx_list]
        seq_new = TimeStampedSequence(seq.object_type, object_list_new, times_new.tolist(), seq.topic_name)
        seq_list_new.append(seq_new)
    return seq_list_new
