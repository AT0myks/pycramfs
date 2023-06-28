from __future__ import annotations

import fnmatch
import struct
import zlib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Literal, Optional, Tuple

from pycramfs.const import BLK_FLAGS, BLK_PTR_FMT, PAGE_SIZE, BlockFlag
from pycramfs.exception import CramfsError
from pycramfs.structure import Inode

if TYPE_CHECKING:
    from pycramfs import Cramfs
    from pycramfs.types import ByteStream, StrPath


class File:
    """Abstract base class for files."""

    def __init__(
        self,
        fd: ByteStream,
        image: Cramfs,
        inode: Inode,
        name: bytes,
        parent: Optional[Directory] = None
    ) -> None:
        self._fd = fd
        self._image = image
        self._inode = inode
        self._name = name
        self._parent = parent

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.name!r})"

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self._name < other._name

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self._name <= other._name

    @property
    def image(self) -> Cramfs:
        return self._image

    @property
    def inode(self) -> Inode:
        return self._inode

    @property
    def name(self) -> str:
        return self._name.decode()

    @property
    def parent(self) -> Optional[Directory]:
        return self._parent

    @property
    def path(self) -> PurePosixPath:
        """Return the file's absolute path."""
        if self._parent is None:
            return PurePosixPath('/')
        return self._parent.path / self.name

    @property
    def mode(self) -> int:
        return self._inode.mode

    @property
    def uid(self) -> int:
        return self._inode.uid

    @property
    def size(self) -> int:
        """Return the size attribute of this file's inode.

        - regular file: uncompressed file size in bytes
        - directory: sum(inode.namelen + sizeof(Inode) for each child inode)
        - symlink: uncompressed target path size in bytes
        - device file: i_rdev (device number, major and minor)
        - FIFO and socket should be 0
        """
        return self._inode.size

    @property
    def gid(self) -> int:
        return self._inode.gid

    @property
    def filemode(self) -> str:
        return self._inode.filemode

    @property
    def is_dir(self) -> bool:
        return False

    @property
    def is_file(self) -> bool:
        return False

    @property
    def is_symlink(self) -> bool:
        return False

    @property
    def is_block_device(self) -> bool:
        return False

    @property
    def is_char_device(self) -> bool:
        return False

    @property
    def is_fifo(self) -> bool:
        return False

    @property
    def is_socket(self) -> bool:
        return False


class Directory(File):

    def __init__(
        self,
        fd: ByteStream,
        image: Cramfs,
        inode: Inode,
        name: bytes = b'',
        parent: Optional[Directory] = None,
        files: Optional[Dict[str, File]] = None
    ) -> None:
        super().__init__(fd, image, inode, name, parent)
        self._files = files if files is not None else {}
        self._total = None

    def __len__(self) -> int:
        return len(self._files)

    def __iter__(self) -> Iterator[File]:
        yield from self.iterdir()

    def __getitem__(self, key: str) -> File:
        return self._files[key]

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return item in self._files
        elif isinstance(item, File):
            return item in self._files.values()
        return False

    def __reversed__(self) -> Iterator[File]:
        for filename in reversed(self._files):
            yield self._files[filename]

    @property
    def is_dir(self) -> Literal[True]:
        return True

    @property
    def files(self) -> Dict[str, File]:
        return self._files

    @property
    def total(self) -> int:
        """Return the total amount of files in this subtree."""
        if self._total is None:
            self._total = len(self) + sum(child.total for child in self._files.values() if isinstance(child, Directory))
        return self._total

    def iterdir(self) -> Iterator[File]:
        yield from self._files.values()

    def riter(self) -> Iterator[File]:
        """Iterate over this directory recursively."""
        yield self
        for file in self._files.values():
            if isinstance(file, Directory):
                yield from file.riter()
            else:
                yield file

    def find(self, filename: StrPath) -> Optional[File]:
        """Find a file of any kind anywhere under this directory."""
        filename = PurePosixPath(filename).name
        for file in self.riter():
            if file.name == filename:
                return file
        return None

    def select(self, path: StrPath) -> Optional[File]:
        """Select a file of any kind by path.

        The path can be absolute or relative.
        Special entries `'.'` and `'..'` are supported.
        """
        path = PurePosixPath(path)
        if str(path) == "..":
            return self.parent if self.parent is not None else self
        if path.root == '/':
            if str(self.path) == '/':
                path = path.relative_to('/')
            else:
                return self._image.rootdir.select(path)
        if str(path) == '.':
            return self
        child, *descendants = path.parts
        if (file := self._files.get(child, None)) is not None:
            if isinstance(file, Directory) and descendants:
                return file.select(PurePosixPath(*descendants))
            elif not descendants:
                return file
        return None

    def itermatch(self, pattern: str) -> Iterator[File]:
        """Iterate over files in this subtree that (fn)match the pattern."""
        # We must use str() here because filter doesn't call normcase on Posix.
        if str(self.path) == '/':
            paths = (str(file.path) for file in self.riter())
        else:
            paths = (str(file.path.relative_to(self.path)) for file in self.riter())
        for path in fnmatch.filter(paths, pattern):
            yield self.select(path)  # type: ignore

    @classmethod
    def from_fd(cls, fd: ByteStream, image: Cramfs, inode: Inode, name: bytes = b'') -> Directory:
        self = cls(fd, image, inode, name)
        if inode.offset == 0:  # Empty dir
            return self
        fd.seek(inode.offset)
        end = inode.size + inode.offset
        children: List[Tuple[Inode, bytes]] = []
        while fd.tell() != end:
            ino = Inode.from_fd(fd)
            name = fd.read(ino.namelen).rstrip(b'\x00')
            children.append((ino, name))
        for ino, name in children:
            if ino.is_dir:
                file = Directory.from_fd(fd, image, ino, name)
                file._parent = self
            else:
                cls = filetype[ino.filemode[0]]
                file = cls(fd, image, ino, name, self)
            self._files[name.decode()] = file
        return self


class DataFile(File):

    def iter_bytes(self) -> Iterator[bytes]:
        """Read blocks and decompress them if necessary."""
        maxblock = (self._inode.size + PAGE_SIZE - 1) // PAGE_SIZE
        self._fd.seek(self._inode.offset)
        block_pointers = self._fd.read(struct.calcsize(BLK_PTR_FMT) * maxblock)
        for block_ptr, *_ in struct.iter_unpack(BLK_PTR_FMT, block_pointers):
            uncompressed = block_ptr & BlockFlag.UNCOMPRESSED
            direct = block_ptr & BlockFlag.DIRECT_PTR
            if direct:
                raise CramfsError("Only contiguous data layout supported")
            block_ptr &= ~BLK_FLAGS  # Remove potential block pointer flags
            block_len = block_ptr - self._fd.tell()
            data = self._fd.read(block_len)
            if not uncompressed:
                data = zlib.decompress(data)
            yield data

    def read_bytes(self) -> bytes:
        return b''.join(self.iter_bytes())

    def read_text(self, encoding: str = "utf8", errors: str = "strict") -> str:
        return self.read_bytes().decode(encoding, errors)


class RegularFile(DataFile):

    @property
    def is_file(self) -> Literal[True]:
        return True


class Symlink(DataFile):

    @property
    def is_symlink(self) -> Literal[True]:
        return True

    def readlink(self) -> PurePosixPath:
        return PurePosixPath(self.read_text())


class FIFO(File):

    @property
    def is_fifo(self) -> Literal[True]:
        return True


class Socket(File):

    @property
    def is_socket(self) -> Literal[True]:
        return True


class CharacterDevice(File):

    @property
    def is_char_device(self) -> Literal[True]:
        return True


class BlockDevice(File):

    @property
    def is_block_device(self) -> Literal[True]:
        return True


filetype = {
    '-': RegularFile,
    'd': Directory,
    'l': Symlink,
    'p': FIFO,
    's': Socket,
    'b': BlockDevice,
    'c': CharacterDevice
}
