from __future__ import annotations

import io
from functools import partial
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, BinaryIO, Iterator, Optional
from zlib import crc32

from pycramfs.const import CRC_OFFSET, CRC_SIZE
from pycramfs.file import Directory, File
from pycramfs.structure import Super
from pycramfs.util import BoundedSubStream, test_super

if TYPE_CHECKING:
    from pycramfs.types import ByteStream, FileDescriptorOrPath, ReadableBuffer, StrPath

__version__ = "1.1.0"


class Cramfs:

    def __init__(
        self,
        fd: ByteStream,
        super: Super,
        rootdir: Directory,
        closefd: bool = True
    ) -> None:
        self._fd = fd
        self._super = super
        self._rootdir = rootdir
        self._closefd = closefd

    def __enter__(self):
        return self

    def __exit__(self, *_: Any) -> None:
        if self._closefd:
            self.close()

    def __len__(self) -> int:
        return self._super.fsid.files

    def __iter__(self) -> Iterator[File]:
        yield from self._rootdir.riter()

    def __contains__(self, item: Any):
        if isinstance(item, (str, PurePosixPath)):
            return self.select(item) is not None
        elif isinstance(item, File):
            # This would be wrong if you opened the same image twice
            # since we don't compare the file's content.
            # This avoids having to iterate over the whole file system.
            return item.image is self
        return False

    @property
    def super(self) -> Super:
        return self._super

    @property
    def rootdir(self) -> Directory:
        return self._rootdir

    @property
    def size(self) -> int:
        """Filesystem size in bytes."""
        return self._super.size

    def close(self) -> None:
        self._fd.close()

    def find(self, filename: StrPath) -> Optional[File]:
        return self._rootdir.find(filename)

    def select(self, path: StrPath) -> Optional[File]:
        return self._rootdir.select(path)

    def itermatch(self, pattern: str) -> Iterator[File]:
        yield from self._rootdir.itermatch(pattern)

    def calculate_crc(self, size: int = 1024**2) -> int:
        self._fd.seek(0)
        crc = crc32(self._fd.read(CRC_OFFSET))  # Read until CRC
        self._fd.read(CRC_SIZE)  # Read the CRC but ignore it
        crc = crc32(bytes(CRC_SIZE), crc)  # and "replace" it by NULL bytes
        for block in iter(partial(self._fd.read, size), b''):
            crc = crc32(block, crc)
        return crc

    @classmethod
    def from_fd(cls, fd: BinaryIO, offset: int = 0, closefd: bool = True):
        """Create a Cramfs object from a file descriptor.

        `offset` must be the absolute position at which the superblock starts.
        """
        fd.seek(offset)
        super = Super.from_fd(fd)
        test_super(super)
        fd_ = BoundedSubStream(fd, offset, offset + super.size)
        self = cls(fd_, super, None, closefd)  # type: ignore
        self._rootdir = Directory.from_fd(fd_, self, self._super.root)
        return self

    @classmethod
    def from_bytes(cls, bytes_: ReadableBuffer, offset: int = 0):
        return cls.from_fd(io.BytesIO(bytes_), offset)

    @classmethod
    def from_file(cls, file: FileDescriptorOrPath, offset: int = 0):
        return cls.from_fd(open(file, "rb"), offset)
