# pycramfs

<p align="left">
<a><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/pycramfs"></a>
<a href="https://pypi.org/project/pycramfs/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pycramfs"></a>
<a href="https://github.com/AT0myks/pycramfs/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/pycramfs"></a>
</p>

* [Requirements](#requirements)
* [Installation](#installation)
* [Usage](#usage)
* [References](#references)

A library and tool to read and extract cramfs images.

It is far from being as complete as the tools it's based on,
but should be enough for simple images.
For example, as of right now it only supports contiguous data layout.
Only little endian images are supported.

It also provides ways to extract data from an image,
although you might prefer using
[`cramfsck`](https://github.com/npitre/cramfs-tools)
on Linux and 7-Zip on Windows for better compatibility.

## Requirements

Python 3.8+.

## Installation

```
pip install pycramfs
```

## Usage

### API

Here's an overview of what you can do:
```py
from pycramfs import Cramfs
from pycramfs.extract import extract_dir, extract_file
from pycramfs.util import find_superblocks

fsimage = "cramfs.bin"
superblocks = find_superblocks(fsimage)

with Cramfs.from_file(fsimage, offset=superblocks[0]["offset"]) as cramfs:
    # Optional offset for start of file system.
    # You can also create Cramfs instances from bytes or a file descriptor.

    sblock = cramfs.super  # Access the file system's superblock
    print(sblock.name)
    print(dict(sblock))  # Superblock as a dictionary
    assert cramfs.calculate_crc() == sblock.fsid.crc

    rootdir = cramfs.rootdir  # root directory
    print(cramfs.size)  # File system size in bytes (shortcut to sblock.size)
    # Number of files in the whole file system (shortcut to sblock.fsid.files).
    print(len(cramfs))
    print("/etc/passwd" in cramfs)  # Check if path exists

    # Iterate over the whole file system.
    for file in cramfs:
        print(file.parent)  # Instance of Directory (None for the root directory)
        print(file in cramfs)  # Check if file belongs to this image
        if file.is_symlink:  # Check the file's type
            print(file.readlink())  # Symlink target

    etc = cramfs.select("/etc")  # Select a specific file or directory
    etc = cramfs.select("etc")  # Can also be a relative path
    rootdir = etc.select("..")  # And a special entry
    assert rootdir == rootdir.select('.')
    print(etc)  # print the file or directory's name
    # The file or directory's absolute path (an instance of PurePosixPath).
    print(etc.path)
    print(etc.files)  # A dictionary mapping file names to File instances
    print(len(etc))  # Number of entries in the directory (shortcut to len(etc.files))
    print(etc.total)  # Number of entries in this whole subtree
    # A list of this directory's children (shortcut to list(etc.files.values())).
    print(list(etc))

    # Find the first file in this subtree that has this name.
    passwd = cramfs.find("passwd")
    # Return the child entry if present else raise KeyError (shortcut to etc.files["passwd"]).
    passwd = etc["passwd"]
    print("passwd" in etc)  # Check if directory contains this file
    print(passwd in etc)  # Also works with instances of File

    # Iterate over this directory's files.
    for file in etc:
        print(file.inode)  # Access inode information
        # These attributes are shortcuts to file.inode.<attr>
        print(file.mode)
        print(file.uid)
        print(file.size)
        print(file.gid)

    # Iterate over this whole subtree.
    for file in etc.riter():
        print(file.name)  # File name, equivalent to file.path.name
        print(file.filemode)  # File mode as a string, for example drwxrwxrwx
    
    # Iterate over files in the subtree that match a pattern.
    for config_file in etc.itermatch("*.conf"):
        print(config_file.read_bytes())  # Read the file's raw content
        print(config_file.read_text("utf8"))  # Or as a string with optional encoding

    assert etc > cramfs.select("/bin")  # Comparing instances of File compares their name

    # You can use absolute paths from any directory.
    cramfs.select("/my/dir/over/here").select("/bin")  # Selects /bin
    cramfs.select("/my/dir/over/here").select("bin")  # Selects /my/dir/over/here/bin

    # Calling find(), select() and itermatch() on cramfs
    # is the same as calling them on cramfs.rootdir.

    extract_dir(etc, "extract/etc")  # Extract a directory tree
    extract_file(passwd, "extract/passwd")  # Extract a single file
```

### Command line

pycramfs comes with a command-line interface that consists of 4 sub-commands.

#### Info

```
usage: pycramfs info [-h] file

Show information about all the superblocks that can be found in a file

positional arguments:
  file
```

Example output:
```
$ pycramfs info cramfs.bin
Superblock #1
Magic:     0x28CD3D45
Size:      282,624
Flags:     <Flag.SORTED_DIRS|FSID_VERSION_2: 3>
Future:    0
Signature: Compressed ROMFS
Name:      Compressed
CRC:       0xDEADBEEF
Edition:   0
Blocks:    6,926
Files:     420
Offset:    8157
```

#### List

```
usage: pycramfs list [-h] [-o OFFSET] [-p PATTERN] [-t TYPE [TYPE ...]] file

List the contents of the file system

positional arguments:
  file

options:
  -o OFFSET, --offset OFFSET      absolute position of file system's start. Default: 0
  -p PATTERN, --pattern PATTERN   filter by file name pattern with fnmatch
  -t TYPE [TYPE ...], --type TYPE [TYPE ...]
                                  filter by file type with f, d, l, p, s, b, c
```

Example that lists only directories and symlinks that match a pattern:
```
$ pycramfs list cramfs.bin -t d l -p "*bin*"
drwxrwxr-x      256   123:0   /bin 
lrwxrwxrwx        7   123:0   /bin/ash -> busybox
lrwxrwxrwx        7   123:0   /bin/base64 -> busybox
3 file(s) found
```

#### Extract

```
usage: pycramfs extract [-h] [-o OFFSET] [-d DEST] [-p PATH] [-f] [-q] file

Extract files from the file system

positional arguments:
  file

options:
  -o OFFSET, --offset OFFSET   absolute position of file system's start. Default: 0
  -d DEST, --dest DEST         destination directory. Default: next to file
  -p PATH, --path PATH         absolute path of directory or file to extract. Default: '/'
  -f, --force                  overwrite files that already exist. Default: False
  -q, --quiet                  don't print extraction status. Default: False
```

On Linux, just like `cramfsck -x` you need to run as root
if you want to preserve file mode, owner and group.

On Windows, the only reason to run as a privileged user is to be able to create
symlinks.
Unprivileged accounts can create symlinks if Developer Mode is enabled.
Otherwise, a regular file containing the target will be created.
Special files will always just be empty files.

#### Check

This command is similar to running `cramfsck -c file` but is not as thorough.

```
usage: pycramfs check [-h] [-o OFFSET] file

Make a few superficial checks of the file system

positional arguments:
  file

options:
  -o OFFSET, --offset OFFSET   absolute position of file system's start. Default: 0
```

## References

- [cramfs readme](https://github.com/torvalds/linux/blob/master/fs/cramfs/README)
- [cramfs_fs.h](https://github.com/npitre/cramfs-tools/blob/master/linux/cramfs_fs.h)
- [cramfsck.c](https://github.com/npitre/cramfs-tools/blob/master/cramfsck.c)
- [mkcramfs.c](https://github.com/npitre/cramfs-tools/blob/master/mkcramfs.c)
