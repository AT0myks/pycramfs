from __future__ import annotations

import stat
from os import chmod, utime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pycramfs.const import Width
from pycramfs.file import (
    FIFO,
    BlockDevice,
    CharacterDevice,
    DataFile,
    Directory,
    File,
    RegularFile,
    Socket,
    Symlink
)
from pycramfs.structure import Inode
from pycramfs.util import printq

if TYPE_CHECKING:
    from pycramfs.types import StrOrBytesPath

try:
    from os import lchown  # type: ignore
except ImportError:
    def lchown(path: StrOrBytesPath, uid: int, gid: int) -> None:
        pass


def write_file(path: Path, file: Optional[DataFile] = None, force: bool = False) -> int:
    if force or not path.exists():
        written = 0
        with path.open("wb") as f:
            if file is not None:
                for block in file.iter_bytes():
                    written += f.write(block)
        return written
    else:
        raise FileExistsError(f"{path.resolve()} already exists")


try:
    from os import mknod  # type: ignore
except ImportError:
    def mknod(path: Path, mode: int = 0o600, device: int = 0) -> None:
        write_file(path)


def change_file_status(path: Path, inode: Inode) -> None:
    try:
        lchown(path, inode.uid, inode.gid)
    except PermissionError:  # Not root or not Unix
        pass
    else:
        if inode.is_symlink:
            return
        if (stat.S_ISUID | stat.S_ISGID) & inode.mode:
            chmod(path, inode.mode)
    if inode.is_symlink:
        return
    utime(path, (0, 0))


def extract_file(file: File, dest: Path, force: bool = False, quiet: bool = True) -> bool:
    """Extract a file that is not a directory.

    Return whether the file was created.
    """
    if isinstance(file, RegularFile):
        write_file(dest, file, force)
        chmod(dest, file.mode)
    elif isinstance(file, Symlink):
        try:
            dest.symlink_to(file.read_bytes())
        except FileExistsError:
            if force:
                dest.unlink()
                return extract_file(file, dest, force, quiet)
            raise
        except OSError:
            # Windows: fallback to writing link destination in file.
            # Either the user is unprivileged or Developer Mode is not enabled.
            write_file(dest, file, force)
    else:
        if isinstance(file, (CharacterDevice, BlockDevice)):
            devtype = file.size
        elif isinstance(file, (FIFO, Socket)):
            devtype = 0
        else:
            printq(f"bogus mode: {file.path} ({file.mode:o})", quiet=quiet)
            return False
        mknod(dest, file.mode, devtype)  # force is not taken into account here
    change_file_status(dest, file.inode)
    return True


def extract_dir(directory: Directory, dest: Path, force: bool = False, quiet: bool = True) -> int:
    """Extract a directory tree. Return the amount of files created."""
    total = directory.total
    width = 2**Width.NAMELEN
    count = created = -1  # Account for creation of destination directory
    for file in directory.riter():
        path = dest / file.path.relative_to(directory.path)
        if file.is_dir:
            path.mkdir(file.mode, exist_ok=force)
            change_file_status(path, file.inode)
            created += 1
        else:
            created += extract_file(file, path, force, quiet)
        count += 1
        printq(f"{count}/{total} {file.name:{width}}", end='\r', quiet=quiet)
    printq(quiet=quiet)
    return created
