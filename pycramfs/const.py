from enum import IntEnum, IntFlag

MAGIC = 0x28CD3D45
SIGNATURE = "Compressed ROMFS"


class Width(IntEnum):
    MODE = 16
    UID = 16
    SIZE = 24
    GID = 8
    NAMELEN = 6
    OFFSET = 26


MAXPATHLEN = ((1 << Width.NAMELEN) - 1) << 2

PAGE_SIZE = 4096


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


BLK_FLAGS = BlockFlag.UNCOMPRESSED | BlockFlag.DIRECT_PTR

CRC_OFFSET = 32  # Bytes
CRC_SIZE = 4  # Bytes

BLK_PTR_FMT = "<I"

MAGIC_BYTES = MAGIC.to_bytes(4, "little")
SIGNATURE_BYTES = b"Compressed ROMFS"
