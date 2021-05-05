#!/usr/bin/env python

# Beverley Sun
# bsun448

from __future__ import print_function, absolute_import, division

import logging

from collections import defaultdict
from errno import ENOENT, ENOSPC, ENOSYS, ENOTEMPTY
from stat import S_IFDIR, S_IFREG, S_ISDIR
from time import time
from disktools import read_block, write_block, BLOCK_SIZE, NUM_BLOCKS
from byte_locations import *
from bitmap import next_avail_block_num, set_bit, clear_bit, num_avail_blocks
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context

#constants
END_OF_FILE = 20
BLOCK_DATA_SIZE = DATA_END - DATA_START
OVERFLOW_BLOCK_DATA_SIZE = OVERFLOW_DATA_END - OVERFLOW_DATA_START
BYTEORDER = "little"
STR_ENCODING = "utf-8"

if not hasattr(__builtins__, 'bytes'):
    bytes = str

def get_block_from_path(path):
    if path == "/":
        return read_block(0)
    path_array = path.split("/")

    #assume all paths start at the root directory
    dir_block_to_check = 0

    #iterate through folders in the path
    for i in range(1, len(path_array)):
        #get dir info
        dir_block = read_block(dir_block_to_check)
        dir_block_nlinks = int.from_bytes(dir_block[NLINKS_START:NLINKS_END], BYTEORDER)
        dir_block_links = dir_block[DATA_START:DATA_START+dir_block_nlinks-2] #get actual links

        #iterate through all files in directory
        for j in range(0, len(dir_block_links)): 
            #get file info
            block_num = dir_block_links[j] #get file location (block number)
            block = read_block(block_num) #get file block
            block_name = block[NAME_START:NAME_END].decode(STR_ENCODING).rstrip('\x00')
            block_mode = int.from_bytes(block[MODE_START:MODE_END], BYTEORDER)

            if path_array[i] == block_name and i == len(path_array) - 1:
                return block
            if path_array[i] == block_name and S_ISDIR(block_mode):
                dir_block_to_check = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)
                break
    #if nothing is returned by this stage, the file/dir doesn't exist
    raise FuseOSError(ENOENT)

def add_link_to_dir(dir_block, link_location):
    nlinks = int.from_bytes(dir_block[NLINKS_START:NLINKS_END], BYTEORDER) #get current num links
    dir_block[DATA_START+nlinks-2] = link_location #add the link location to the directory
    dir_block[NLINKS_START:NLINKS_END] = (nlinks + 1).to_bytes(1, BYTEORDER) #update num links in the dir

    #write the updated block back into disk
    dir_location = int.from_bytes(dir_block[LOCATION_START:LOCATION_END], BYTEORDER)
    write_block(dir_location, dir_block)

def rm_link_from_dir(path, block_num):
    #get dir info
    parent_block = get_block_from_path(path)
    parent_location = int.from_bytes(parent_block[LOCATION_START:LOCATION_END], BYTEORDER)
    parent_nlinks = int.from_bytes(parent_block[NLINKS_START:NLINKS_END], BYTEORDER)
    parent_links = parent_block[DATA_START:DATA_START+parent_nlinks-2]

    #remove the link for the removed dir
    updated_links = []
    for i in range(0, len(parent_links)):
        link_num = parent_links[i]
        if link_num != block_num:
            updated_links.append(parent_links[i])
    
    #remove all links and them back, except for the removed dir
    parent_block[DATA_START:DATA_END] = bytearray([0]*(DATA_END-DATA_START))
    for i in range(0, len(updated_links)):
        parent_block[DATA_START:DATA_START+i] = updated_links[i].to_bytes(1, BYTEORDER)

    parent_block[NLINKS_START:NLINKS_END] =(parent_nlinks-1).to_bytes(1, BYTEORDER)
    write_block(parent_location, parent_block) #update parent block in disk

def init_block_data(block, name, nlinks, block_num, mode):
    now = int(time())
    
    block[MODE_START:MODE_END] = mode.to_bytes(2, BYTEORDER)
    block[UID_START:UID_END] = fuse_get_context()[0].to_bytes(2, BYTEORDER)
    block[GID_START:GID_END] = fuse_get_context()[1].to_bytes(2, BYTEORDER)
    block[NLINKS_START:NLINKS_END] = nlinks.to_bytes(1, BYTEORDER)
    block[CTIME_START:CTIME_END] = now.to_bytes(4, BYTEORDER)
    block[MTIME_START:MTIME_END] = now.to_bytes(4, BYTEORDER)
    block[ATIME_START:ATIME_END] = now.to_bytes(4, BYTEORDER)
    block[NAME_START:NAME_END] = bytes(name, STR_ENCODING)
    block[LOCATION_START:LOCATION_END] = (block_num).to_bytes(1, BYTEORDER)
    block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END] = (END_OF_FILE).to_bytes(1, BYTEORDER)
    if (S_ISDIR(mode)):
        block[SIZE_START:SIZE_END] = BLOCK_SIZE.to_bytes(2, BYTEORDER)
    return block

class Small(LoggingMixIn, Operations):
    def chmod(self, path, mode):
        raise FuseOSError(ENOSYS)

    def chown(self, path, uid, gid):
        raise FuseOSError(ENOSYS)

    def create(self, path, mode):
        block_num = next_avail_block_num()

        #no available blocks
        if block_num == -1:
            raise FuseOSError(ENOSPC)

        #get short file name
        path_split = path.split("/")
        name = path_split[len(path_split)-1]

        #initialise and write block
        block = read_block(block_num)
        block = init_block_data(block, name, 1, block_num, S_IFREG | 0o755)
        write_block(block_num, block)
        set_bit(block_num)

        #link it to its parent dir
        path_to_dir = "/" + "/".join(path_split[1:len(path_split) - 1])
        dir_block = get_block_from_path(path_to_dir)
        add_link_to_dir(dir_block, block_num)

        return block_num

    def getattr(self, path, fh=None):
        block = get_block_from_path(path)
        mode = int.from_bytes(block[MODE_START:MODE_END], BYTEORDER)
        ctime = int.from_bytes(block[CTIME_START:CTIME_END], BYTEORDER)
        mtime = int.from_bytes(block[MTIME_START:MTIME_END], BYTEORDER)
        atime = int.from_bytes(block[ATIME_START:ATIME_END], BYTEORDER)
        nlink = int.from_bytes(block[NLINKS_START:NLINKS_END], BYTEORDER)
        size = int.from_bytes(block[SIZE_START:SIZE_END], BYTEORDER)
        uid = int.from_bytes(block[UID_START:UID_END], BYTEORDER)
        gid = int.from_bytes(block[GID_START:GID_END], BYTEORDER)
        return dict(
            st_mode=mode,
            st_ctime=ctime,
            st_mtime=mtime,
            st_atime=atime,
            st_nlink=nlink,
            st_size=size,
            st_uid = uid,
            st_gid = gid
        )

    def getxattr(self, path, name, position=0):
        return ""

    def listxattr(self, path):
        raise FuseOSError(ENOSYS)

    def mkdir(self, path, mode):
        block_num = next_avail_block_num()

        #no free blocks available
        if block_num == -1:
            raise FuseOSError(ENOSPC)

        #get short name of dir
        path_split = path.split("/")
        name = path_split[len(path_split)-1]

        #initialise and write block
        block = read_block(block_num)
        block = init_block_data(block, name, 2, block_num, S_IFDIR | 0o755)
        write_block(block_num, block)
        set_bit(block_num)

        #link dir to parent dir
        path_to_dir = "/" + "/".join(path_split[1:len(path_split) - 1])
        dir_block = get_block_from_path(path_to_dir)
        add_link_to_dir(dir_block, block_num)

    def open(self, path, flags):
        block = get_block_from_path(path)
        location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)
        return location

    def read(self, path, size, offset, fh):
        block = get_block_from_path(path)

        block_size = int.from_bytes(block[SIZE_START:SIZE_END], BYTEORDER)
        if size > block_size - offset:
            size = block_size - offset
        
        #calculate offset for the required block
        num_blocks_for_offset = 1 #number of blocks needed to traverse to get to the offset
        if offset >= BLOCK_DATA_SIZE:
            offset -= BLOCK_DATA_SIZE
            num_blocks_for_offset += 1
            num_blocks_for_offset += int(offset/(OVERFLOW_BLOCK_DATA_SIZE))
            offset = offset%(OVERFLOW_BLOCK_DATA_SIZE)
        
        #find block to start reading from
        for i in range(1, num_blocks_for_offset):
            next_block_num = int.from_bytes(block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END], BYTEORDER)
            block = read_block(next_block_num)

        sizes = [] #the sizes to read from each block

        #calculate sizes needed to read for each block
        if num_blocks_for_offset == 1 and size > BLOCK_DATA_SIZE - offset:
            sizes.append(BLOCK_DATA_SIZE - offset)
            size -= BLOCK_DATA_SIZE - offset
        elif num_blocks_for_offset > 1 and size > OVERFLOW_BLOCK_DATA_SIZE - offset:
            sizes.append(OVERFLOW_BLOCK_DATA_SIZE - offset)
            size -= OVERFLOW_BLOCK_DATA_SIZE - offset
        else:
            sizes.append(size)
            size = 0
        
        while size > OVERFLOW_BLOCK_DATA_SIZE:
            sizes.append(OVERFLOW_BLOCK_DATA_SIZE)
            size  -= OVERFLOW_BLOCK_DATA_SIZE
        if size > 0:
            sizes.append(size)
        
        # read all required data from the block(s)
        data = ""
        if num_blocks_for_offset == 1:
            data += block[DATA_START+offset:DATA_START+offset+sizes[0]].decode(STR_ENCODING)
        else:
            data += block[OVERFLOW_DATA_START+offset:OVERFLOW_DATA_START+offset+sizes[0]].decode(STR_ENCODING)
        
        for s in sizes[1:]:
            next_block_num = int.from_bytes(block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END], BYTEORDER)
            block = read_block(next_block_num)
            data +=  block[OVERFLOW_DATA_START:OVERFLOW_DATA_START+s].decode(STR_ENCODING)

        return bytes(data, STR_ENCODING)

    def readdir(self, path, fh):
        block = get_block_from_path(path)
        files = ['.', '..']

        nlinks = int.from_bytes(block[NLINKS_START:NLINKS_END], BYTEORDER)
        if nlinks > 2:
            links = block[DATA_START:DATA_END]
            for i in range(0,nlinks-2):
                file_or_dir = read_block(links[i])
                files.append(file_or_dir[NAME_START:NAME_END].decode(STR_ENCODING).rstrip("\x00"))
        return files

    def readlink(self, path):
        block = get_block_from_path(path)
        block_size = int.from_bytes(block[SIZE_START:SIZE_END], BYTEORDER)
        block_data = self.read(path, block_size, 0, 0)
        return block_data

    def removexattr(self, path, name):
        raise FuseOSError(ENOSYS)

    def rename(self, old, new):
        block = get_block_from_path(old)
        block_location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)

        #rename
        new_path_split = new.split("/")
        new_name = new_path_split[len(new_path_split) - 1]
        block[NAME_START:NAME_END] = bytes(new_name.ljust(NAME_END-NAME_START, "\x00"), STR_ENCODING)

        write_block(block_location, block)

    def rmdir(self, path):
        block = get_block_from_path(path)
        nlinks = int.from_bytes(block[NLINKS_START:NLINKS_END], BYTEORDER)
        
        if nlinks > 2:
            raise FuseOSError(ENOTEMPTY)
        else:
            block_location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)
            path_split = path.split("/")

            #remove link from parent dir
            parent_dir_path = "/" + "/".join(path_split[1:len(path_split)-1])
            rm_link_from_dir(parent_dir_path, block_location)

            #zero out the removed dir
            write_block(block_location, bytearray([0]*BLOCK_SIZE))
            clear_bit(block_location)

    def setxattr(self, path, name, value, options, position=0):
        raise FuseOSError(ENOSYS)

    def statfs(self, path):
        return dict(f_bsize=BLOCK_SIZE, f_blocks=NUM_BLOCKS, f_bavail=num_avail_blocks())

    def symlink(self, target, source):
        raise FuseOSError(ENOSYS)

    def truncate(self, path, length, fh=None):
        raise FuseOSError(ENOSYS)

    def unlink(self, path):
        block = get_block_from_path(path)
        block_location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)

        #remove link from parent dir
        path_split = path.split("/")
        parent_dir_path = "/" + "/".join(path_split[1:len(path_split)-1])
        rm_link_from_dir(parent_dir_path, block_location)

        #remove the actual file
        next_block_num = int.from_bytes(block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END], BYTEORDER)
        write_block(block_location, bytearray([0]*BLOCK_SIZE)) #zero out the removed file
        clear_bit(block_location)
        while next_block_num != END_OF_FILE: #remove all subsequent blocks of the file
            next_block = read_block(next_block_num)
            write_block(next_block_num, bytearray([0]*BLOCK_SIZE))
            clear_bit(next_block_num)
            next_block_num = int.from_bytes(next_block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END], BYTEORDER)

    def utimens(self, path, times=None):
        now = int(time())
        atime, mtime = times if times else (now, now)

        block = get_block_from_path(path)
        block_location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)
        
        block[ATIME_START:ATIME_END] = int(atime).to_bytes(4, BYTEORDER)
        block[MTIME_START:MTIME_END] = int(mtime).to_bytes(4, BYTEORDER)

        write_block(block_location, block)

    def write(self, path, data, offset, fh):
        block = get_block_from_path(path)
        block_location = int.from_bytes(block[LOCATION_START:LOCATION_END], BYTEORDER)

        # calculate total available space
        block_size = int.from_bytes(block[SIZE_START:SIZE_END], BYTEORDER)
        avail_space_end_block = 0
        if block_size <= BLOCK_DATA_SIZE:
            avail_space_end_block = BLOCK_DATA_SIZE - block_size
        else:
            avail_space_end_block = OVERFLOW_BLOCK_DATA_SIZE - ((block_size - (BLOCK_DATA_SIZE)) % (OVERFLOW_BLOCK_DATA_SIZE))
        
        free_blocks_avail_space = num_avail_blocks() * (OVERFLOW_BLOCK_DATA_SIZE)
        total_avail_space = avail_space_end_block + free_blocks_avail_space
        
        #not enough space
        if len(data) > total_avail_space:
            raise FuseOSError(ENOSPC)

        #read in all data and add in new data at the offset
        block_data = self.read(path, block_size, 0, fh)
        new_data = block_data[0:offset].decode(STR_ENCODING) + data.decode(STR_ENCODING) + block_data[offset:].decode(STR_ENCODING)

        #update size of file
        block[SIZE_START:SIZE_END] = len(new_data).to_bytes(2, BYTEORDER)

        #insert data in first block
        if len(new_data) <= BLOCK_DATA_SIZE:
            block[DATA_START:DATA_END] = bytes(new_data.ljust(BLOCK_DATA_SIZE, "\x00"), STR_ENCODING)
            new_data = ""
        else:
            block[DATA_START:DATA_END] = bytes(new_data[0:BLOCK_DATA_SIZE], STR_ENCODING)
            new_data = new_data[BLOCK_DATA_SIZE:]
        write_block(block_location, block)
        current_block_num = block_location

        #insert remaining/leftover data in different blocks
        while new_data != "":
            next_block_num = int.from_bytes(block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END], BYTEORDER)
            if next_block_num == END_OF_FILE:
                #create new block if previous block was end of file
                next_block_num = next_avail_block_num()
                
                #set the next block number on the current block
                block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END] = next_block_num.to_bytes(1, BYTEORDER)
                write_block(current_block_num, block)

                #read in next block
                block = read_block(next_block_num)
                set_bit(next_block_num)
                block[NEXTBLOCKNUM_START:NEXTBLOCKNUM_END] = (END_OF_FILE).to_bytes(1, BYTEORDER)
            else:
                block = read_block(next_block_num)
            
            #insert data into the block
            if len(new_data) <= OVERFLOW_BLOCK_DATA_SIZE:
                block[OVERFLOW_DATA_START:OVERFLOW_DATA_END] = bytes(new_data.ljust(OVERFLOW_BLOCK_DATA_SIZE, "\x00"), STR_ENCODING)
                new_data = ""
            else:
                block[OVERFLOW_DATA_START:OVERFLOW_DATA_END] = bytes(new_data[0:OVERFLOW_BLOCK_DATA_SIZE], STR_ENCODING)
                new_data = new_data[OVERFLOW_BLOCK_DATA_SIZE:]
            write_block(next_block_num, block)

            #update current block number
            current_block_num = next_block_num
        
        return len(data)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Small(), args.mount, foreground=True)
