# Persistent fusepy file system
A very basic (and persistent) file system using fusepy.
Has multi-level support (nested directories).

## Usage
### Initial setup
```shell
> mkdir mount
> python3 disktools.py
> python3 format.py
```

### Running the file system
1. Open 2 terminals
2. In terminal 1
   ```shell
   > python3 small.py mount
   ```
3. In terminal 2
   ```shell
   > cd mount
   ```
   Only switch into the `mount` directory after mounting the file system. If you are already in the `mount` directory when mounting the file system, 
   change out of it and then back into it.
