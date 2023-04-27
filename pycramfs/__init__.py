import io
from functools import partial
from pathlib import PurePosixPath
from zlib import crc32

from pycramfs.const import CRC_OFFSET, CRC_SIZE
from pycramfs.file import Directory, File
from pycramfs.structure import Super
from pycramfs.util import BoundedSubStream, test_super

__version__ = "1.0.0"


class Cramfs:

    def __init__(self, fd: BoundedSubStream, super: Super, rootdir: Directory = None, closefd: bool = True):
        self._fd = fd
        self._super = super
        self._rootdir = rootdir
        self._closefd = closefd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._closefd:
            self.close()

    def __len__(self):
        return self._super.fsid.files

    def __iter__(self):
        for file in self._rootdir.riter():
            yield file

    def __contains__(self, item):
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

    def find(self, filename):
        return self._rootdir.find(filename)

    def select(self, path):
        return self._rootdir.select(path)

    def itermatch(self, pattern):
        return self._rootdir.itermatch(pattern)

    def calculate_crc(self, size=4096):
        self._fd.seek(0)
        crc = crc32(self._fd.read(CRC_OFFSET))  # Read until CRC
        self._fd.read(CRC_SIZE)  # Read the CRC but ignore it
        crc = crc32(bytes(CRC_SIZE), crc)  # and "replace" it by NULL bytes
        for block in iter(partial(self._fd.read, size), b''):
            crc = crc32(block, crc)
        return crc

    @classmethod
    def from_fd(cls, fd, offset=0, closefd=True):
        """Create a Cramfs object from a file descriptor.

        `offset` must be the absolute position at which the superblock starts.
        """
        fd.seek(offset)
        super = Super.from_fd(fd)
        test_super(super)
        fd = BoundedSubStream(fd, offset, offset + super.size)
        self = cls(fd, super, closefd=closefd)
        self._rootdir = Directory.from_fd(fd, self, self._super.root)
        return self

    @classmethod
    def from_bytes(cls, bytes_, offset=0):
        return cls.from_fd(io.BytesIO(bytes_), offset)

    @classmethod
    def from_file(cls, path, offset=0):
        return cls.from_fd(open(path, "rb"), offset)
