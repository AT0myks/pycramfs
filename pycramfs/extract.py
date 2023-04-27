import stat
from os import chmod, utime
from pathlib import Path

from pycramfs.const import Width
from pycramfs.file import Directory
from pycramfs.structure import Inode
from pycramfs.util import _print

try:
    from os import lchown
except ImportError:
    def lchown(path, uid, gid):
        raise PermissionError


def write_file(path: Path, content: bytes = b'', force: bool = False) -> int:
    if force or not path.exists():
        with path.open("wb") as f:
            return f.write(content)
    else:
        raise FileExistsError(f"{path.resolve()} already exists")


try:
    from os import mknod
except ImportError:
    def mknod(path, mode=0o600, device=0):
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


def extract_file(file, dest: Path, force: bool = False, quiet: bool = True) -> bool:
    """Extract a file that is not a directory.

    Return whether the file was created.
    """
    if file.is_file:
        write_file(dest, file.read_bytes(), force)
        chmod(dest, file.mode)
    elif file.is_symlink:
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
            write_file(dest, file.read_bytes(), force)
    else:
        if file.is_char_device or file.is_block_device:
            devtype = file.size
        elif file.is_fifo or file.is_socket:
            devtype = 0
        else:
            _print(f"bogus mode: {file.path} ({file.mode:o})", quiet=quiet)
            return False
        mknod(dest, file.mode, devtype)  # force is not taken into account here
    change_file_status(dest, file.inode)
    return True


def extract_dir(directory: Directory, dest: Path, force: bool = False, quiet: bool = True):
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
        _print(f"{count}/{total} {file.name:{width}}", end='\r', quiet=quiet)
    _print(quiet=quiet)
    return created
