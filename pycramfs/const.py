from enum import IntEnum, IntFlag
from typing import Final

MAGIC: Final = 0x28CD3D45
SIGNATURE: Final = "Compressed ROMFS"


class Width(IntEnum):
    MODE = 16
    UID = 16
    SIZE = 24
    GID = 8
    NAMELEN = 6
    OFFSET = 26


MAXPATHLEN: Final = ((1 << Width.NAMELEN) - 1) << 2

PAGE_SIZE: Final = 4096


class Flag(IntFlag):
    FSID_VERSION_2 = 0x00000001  # fsid version #2
    SORTED_DIRS = 0x00000002  # sorted dirs
    HOLES = 0x00000100  # support for holes
    WRONG_SIGNATURE = 0x00000200  # reserved
    SHIFTED_ROOT_OFFSET = 0x00000400  # shifted root fs
    EXT_BLOCK_POINTERS = 0x00000800  # block pointer extensions


SUPPORTED_FLAGS = (
    0xFF
    | Flag.HOLES
    | Flag.WRONG_SIGNATURE
    | Flag.SHIFTED_ROOT_OFFSET
    | Flag.EXT_BLOCK_POINTERS
)


class BlockFlag(IntFlag):
    UNCOMPRESSED = 1 << 31
    DIRECT_PTR = 1 << 30


BLK_FLAGS: Final = BlockFlag.UNCOMPRESSED | BlockFlag.DIRECT_PTR

CRC_OFFSET: Final = 32  # Bytes
CRC_SIZE: Final = 4  # Bytes

BLK_PTR_FMT: Final = "<I"

MAGIC_BYTES: Final = MAGIC.to_bytes(4, "little")
SIGNATURE_BYTES: Final = b"Compressed ROMFS"
