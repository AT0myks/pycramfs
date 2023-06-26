import io
from functools import partial
from pathlib import Path

from pycramfs.const import MAGIC, MAGIC_BYTES, SIGNATURE, SIGNATURE_BYTES, SUPPORTED_FLAGS, Flag
from pycramfs.exception import CramfsError
from pycramfs.file import PAGE_SIZE
from pycramfs.structure import Super


class BoundedSubStream:
    """Wrapper around a stream with boundaries that won't allow
    to move before the start or past the end of a sub stream.
    """

    def __init__(self, fd, start=0, end=None) -> None:
        """`start` and `end` are the absolute limits of the sub stream.

        `end` will usually be `start` + data size.
        """
        self._fd = fd
        self._start = start
        self._end = end if end is not None else self._find_size()

    def __getattr__(self, name: str):
        # Treat anything else as if called directly on the wrapped stream.
        return getattr(self._fd, name)

    def _find_size(self) -> int:
        pos = self._fd.tell()
        size = self._fd.seek(0, io.SEEK_END)
        self._fd.seek(pos)
        return size

    def read(self, size=-1, /) -> bytes:
        max_read = self._end - self._fd.tell()
        if size is None or size < 0 or size > max_read:
            size = max_read
        return self._fd.read(size)

    def seek(self, offset, whence=io.SEEK_SET, /) -> int:
        if whence == io.SEEK_SET:
            offset = max(self._start, offset + self._start)
        elif whence == io.SEEK_CUR:
            pos = self._fd.tell()
            if pos + offset > self._end:  # Positive offset
                offset = self._end - pos
            elif pos + offset < self._start:  # Negative offset
                offset = pos - self._start
        elif whence == io.SEEK_END:
            whence = io.SEEK_SET
            offset = min(self._end, offset + self._end)
        return self._fd.seek(offset, whence) - self._start

    def tell(self) -> int:
        return self._fd.tell() - self._start


def find_superblocks(file_or_bytes, size=1024**2):
    """Return a list of dictionaries representing the
    superblocks found in the file with their offset.
    """
    count = 0
    indexes = set()
    result = []
    if isinstance(file_or_bytes, (str, Path)):
        stream = open(file_or_bytes, "rb")
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        stream = io.BytesIO(file_or_bytes)
    else:
        raise TypeError("argument must be a path or bytes")
    with stream as f:
        prev_block = b''
        for next_block in iter(partial(f.read, size), b''):
            # We don't want to "cut" in the middle of a magic.
            block = prev_block + next_block
            index = block.find(MAGIC_BYTES)
            if index != -1:
                indexes.add(index + (count * size) - len(prev_block))
            prev_block = next_block
            count += 1
        for index in sorted(indexes):
            f.seek(index)
            super = Super.from_fd(f)
            # It's possible that the magic shows up but is just random bytes.
            # That's why we dont decode() the signature and compare the raw bytes.
            if super.magic == MAGIC and super._signature == SIGNATURE_BYTES:
                result.append(dict(super, offset=index))
    return result


def test_super(superblock: Super):
    if superblock.magic != MAGIC:
        raise CramfsError("wrong magic")
    if superblock.signature != SIGNATURE:
        raise CramfsError("wrong signature")
    if superblock.flags & ~SUPPORTED_FLAGS:
        raise CramfsError("unsupported filesystem features")
    if superblock.size < PAGE_SIZE:
        raise CramfsError(f"superblock size {superblock.size} too small")
    if superblock.flags & Flag.FSID_VERSION_2:
        if superblock.fsid.files == 0:
            raise CramfsError("zero file count")
    else:
        print("WARNING: old cramfs format")


def _print(*args, **kwargs):
    if not kwargs.pop("quiet", False):
        print(*args, **kwargs)
