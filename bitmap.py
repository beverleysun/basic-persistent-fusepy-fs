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
    map_str = bin(read_bitmap())[2:]
    return map_str.find("0")
    
def num_avail_blocks():
    map_str = bin(read_bitmap())[2:]
    return map_str.count("0")

def write_map_to_file(map):
    with open(BITMAP_FILE_NAME, "w") as bitmap:
            bitmap.write(map)

def read_bitmap():
    with open(BITMAP_FILE_NAME, "r") as bitmap:
        return int(bitmap.readline(), 2)