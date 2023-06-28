from __future__ import annotations

import stat
from ctypes import LittleEndianStructure, c_char, c_uint32, sizeof
from typing import TYPE_CHECKING, Iterator, Tuple

from pycramfs.const import Flag, Width

if TYPE_CHECKING:
    from pycramfs.types import ByteStream, ReadableBuffer, StructAsDict


class _Base(LittleEndianStructure):

    def __iter__(self) -> Iterator[Tuple[str, StructAsDict]]:
        # This allows calling dict() on instances of this class.
        for name, *_ in self._fields_:
            name = name.lstrip('_')
            attr = getattr(self, name)
            yield name, dict(attr) if isinstance(attr, _Base) else attr

    @classmethod
    def from_bytes(cls, bytes_: ReadableBuffer, offset: int = 0):
        return cls.from_buffer_copy(bytes_, offset)

    @classmethod
    def from_fd(cls, fd: ByteStream):
        return cls.from_bytes(fd.read(sizeof(cls)))


class Inode(_Base):
    _fields_ = [
        ("_mode", c_uint32, Width.MODE),
        ("_uid", c_uint32, Width.UID),
        ("_size", c_uint32, Width.SIZE),
        ("_gid", c_uint32, Width.GID),
        ("_namelen", c_uint32, Width.NAMELEN),
        ("_offset", c_uint32, Width.OFFSET),
    ]
    _mode: int
    _uid: int
    _size: int
    _gid: int
    _namelen: int
    _offset: int

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def size(self) -> int:
        return self._size

    @property
    def gid(self) -> int:
        return self._gid

    @property
    def namelen(self) -> int:
        """Return the length of the file's name, already multiplied by 4."""
        return self._namelen * 4

    @property
    def offset(self) -> int:
        """Return the offset of the file's data, already multiplied by 4."""
        return self._offset * 4

    @property
    def is_dir(self) -> bool:
        return stat.S_ISDIR(self.mode)

    @property
    def is_file(self) -> bool:
        return stat.S_ISREG(self.mode)

    @property
    def is_symlink(self) -> bool:
        return stat.S_ISLNK(self.mode)

    @property
    def is_block_device(self) -> bool:
        return stat.S_ISBLK(self.mode)

    @property
    def is_char_device(self) -> bool:
        return stat.S_ISCHR(self.mode)

    @property
    def is_fifo(self) -> bool:
        return stat.S_ISFIFO(self.mode)

    @property
    def is_socket(self) -> bool:
        return stat.S_ISSOCK(self.mode)

    @property
    def filemode(self) -> str:
        return stat.filemode(self.mode)


class Info(_Base):
    _fields_ = [
        ("_crc", c_uint32),
        ("_edition", c_uint32),
        ("_blocks", c_uint32),
        ("_files", c_uint32),
    ]
    _crc: int
    _edition: int
    _blocks: int
    _files: int

    @property
    def crc(self) -> int:
        return self._crc

    @property
    def edition(self) -> int:
        return self._edition

    @property
    def blocks(self) -> int:
        return self._blocks

    @property
    def files(self) -> int:
        return self._files


class Super(_Base):
    _fields_ = [
        ("_magic", c_uint32),
        ("_size", c_uint32),
        ("_flags", c_uint32),
        ("_future", c_uint32),
        ("_signature", c_char * 16),
        ("_fsid", Info),
        ("_name", c_char * 16),
        ("_root", Inode),
    ]
    _magic: int
    _size: int
    _flags: int
    _future: int
    _signature: bytes
    _fsid: Info
    _name: bytes
    _root: Inode

    @property
    def magic(self) -> int:
        return self._magic

    @property
    def size(self) -> int:
        return self._size

    @property
    def flags(self) -> Flag:
        return Flag(self._flags)

    @property
    def future(self) -> int:
        return self._future

    @property
    def signature(self) -> str:
        return self._signature.decode()

    @property
    def fsid(self) -> Info:
        return self._fsid

    @property
    def name(self) -> str:
        return self._name.decode()

    @property
    def root(self) -> Inode:
        return self._root
