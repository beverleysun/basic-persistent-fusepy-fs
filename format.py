# Beverley Sun
# bsun448

from disktools import read_block, write_block, low_level_format, BLOCK_SIZE
from fuse import fuse_get_context
from time import time
from stat import S_IFDIR
from byte_locations import *
from stat import S_IFDIR

END_OF_FILE = 20
BYTEORDER = "little"
STR_ENCODING = "utf-8"

def setup_root_dir():
    now = int(time())
    block = read_block(0)
    block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END] = (END_OF_FILE).to_bytes(1, BYTEORDER)
    block[MODE_START:MODE_END] = (S_IFDIR | 0o755).to_bytes(2, BYTEORDER)
    block[UID_START:UID_END] = fuse_get_context()[0].to_bytes(2, BYTEORDER)
    block[GID_START:GID_END] = fuse_get_context()[1].to_bytes(2, BYTEORDER)
    block[NLINKS_START:NLINKS_END] = (2).to_bytes(1, BYTEORDER)
    block[SIZE_START:SIZE_END] = BLOCK_SIZE.to_bytes(2, BYTEORDER)
    block[CTIME_START:CTIME_END] = now.to_bytes(4, BYTEORDER)
    block[MTIME_START:MTIME_END] = now.to_bytes(4, BYTEORDER)
    block[ATIME_START:ATIME_END] = now.to_bytes(4, BYTEORDER)
    block[LOCATION_START:LOCATION_END] = (0).to_bytes(1, BYTEORDER)
    block[NAME_START:NAME_END] = bytes("/", STR_ENCODING)
    write_block(0, block)

def setup_bitmap():
    with open("bitmap", "w") as bitmap:
        bitmap.write(bin(2**15))
                
if __name__ == "__main__":
    low_level_format()
    setup_root_dir()
    setup_bitmap()
