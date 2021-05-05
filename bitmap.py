# Beverley Sun
# bsun448

import math

BITMAP_FILE_NAME = "bitmap"

def set_bit(offset_from_left):
    offset = 15 - offset_from_left
    mask = 1 << offset
    map = read_bitmap() | mask
    write_map_to_file(bin(map))
    return map

def clear_bit(offset_from_left):
    offset = 15 - offset_from_left
    mask = ~(1 << offset)
    map = read_bitmap() & mask
    write_map_to_file(bin(map))
    return map

def next_avail_block_num():
    map = read_bitmap()
    mask = 0b1111111111111111
    map ^= mask
    try:
        return 15 - int(math.log2(map))
    except ValueError:
        return -1

def num_avail_blocks():
    count = 0
    map_str = str(bin(read_bitmap()))[2:]
    for i in range(0,len(map_str)):
        if map_str[i] == "0":
            count += 1
    return count

def write_map_to_file(map):
    with open(BITMAP_FILE_NAME, "w") as bitmap:
            bitmap.write(map)

def read_bitmap():
    with open(BITMAP_FILE_NAME, "r") as bitmap:
        return int(bitmap.readline(), 2) 