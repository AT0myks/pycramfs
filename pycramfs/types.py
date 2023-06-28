from os import PathLike
from typing import BinaryIO, Dict, Union

from pycramfs.const import Flag
from pycramfs.util import BoundedSubStream


ByteStream = Union[BinaryIO, BoundedSubStream[bytes]]
ReadableBuffer = Union[bytes, bytearray, memoryview]
StrOrBytesPath = Union[str, bytes, PathLike[str], PathLike[bytes]]
FileDescriptorOrPath = Union[int, StrOrBytesPath]
StrPath = Union[str, PathLike[str]]
StructAsDict = Dict[str, Union[int, str, Flag, "StructAsDict"]]
