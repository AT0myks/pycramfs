from argparse import ArgumentParser, Namespace
from pathlib import Path, PurePosixPath

from pycramfs import Cramfs, __version__
from pycramfs.const import PAGE_SIZE
from pycramfs.exception import CramfsError
from pycramfs.extract import extract_dir, extract_file
from pycramfs.file import Directory, File, Symlink, filetype
from pycramfs.util import find_superblocks, printq


def print_file(file: File) -> None:
    # Max file size is 2**24-1 or 16777215 -> 8 characters.
    # Max UID is 2**16-1 or 65535 -> 5 characters.
    # Max GID is 2**8-1 or 255 -> 3 characters.
    link = f"-> {file.readlink()}" if isinstance(file, Symlink) else ''
    print(file.filemode, f"{file.size:8} {file.uid:5}:{file.gid:<3}", file.path, link)


def list_(args: Namespace) -> None:
    if (types := args.type) is not None:
        types = set(''.join(types).replace('f', '-'))
    count = 0
    with Cramfs.from_file(args.file, args.offset) as cramfs:
        if args.pattern is None:
            it = cramfs
        else:
            it = cramfs.itermatch(args.pattern)
        if types is None:
            for file in it:
                print_file(file)
                count += 1
        else:
            for file in it:
                if file.filemode[0] in types:
                    print_file(file)
                    count += 1
    print(f"{count} file(s) found")


def info(args: Namespace) -> None:
    width = 10
    superblocks = find_superblocks(args.file)
    if not superblocks:
        print("No superblock found")
        return
    for idx, superblock in enumerate(superblocks):
        super = Namespace(**superblock)
        fsid = Namespace(**super.fsid)
        print(f"Superblock #{idx + 1}")
        print(f"{'Magic:':{width}} 0x{super.magic:X}")
        print(f"{'Size:':{width}} {super.size:,}")
        print(f"{'Flags:':{width}} {super.flags!r}")
        print(f"{'Future:':{width}} {super.future}")
        print(f"{'Signature:':{width}} {super.signature}")
        print(f"{'Name:':{width}} {super.name}")
        print(f"{'CRC:':{width}} 0x{fsid.crc:08X}")
        print(f"{'Edition:':{width}} {fsid.edition}")
        print(f"{'Blocks:':{width}} {fsid.blocks:,}")
        print(f"{'Files:':{width}} {fsid.files:,}")
        print(f"{'Offset:':{width}} {super.offset}")
        if idx != len(superblocks) - 1:
            print()


def extract(args: Namespace) -> None:
    dest = args.dest
    with Cramfs.from_file(args.file, args.offset) as cramfs:
        file = cramfs.select(args.path)
        if file is None:
            raise CramfsError(f"{args.path} not found")
        elif isinstance(file, Directory):
            if dest is None:
                dest = args.file.with_name(args.file.stem)
            amount = extract_dir(file, dest, args.force, args.quiet)
        else:
            if dest is None:
                dest = args.file.parent / file.name
            amount = extract_file(file, dest, args.force, args.quiet)
    printq(f"{int(amount)} file(s) extracted to {dest.resolve()}", quiet=args.quiet)


def check(args: Namespace) -> None:
    with Cramfs.from_file(args.file, args.offset) as cramfs:
        for file in cramfs:
            if file.inode.namelen == 0 and str(file.path) != '/':
                print("filename length is zero", file.path)
            offset = file.inode.offset
            if file.is_dir:
                if offset == 0 and file.size != 0:
                    print("directory inode has zero offset and non-zero size:", file.path)
            elif file.is_file:
                if offset == 0 and file.size != 0:
                    print("file inode has zero offset and non-zero size", file.path)
                if file.size == 0 and offset != 0:
                    print("file inode has zero size and non-zero offset", file.path)
            elif file.is_symlink:
                if offset == 0:
                    print("symbolic link has zero offset", file.path)
                if file.size == 0:
                    print("symbolic link has zero size", file.path)
            else:
                if offset != 0:
                    print("special file has non-zero offset:", file.path)
                if file.is_char_device or file.is_block_device:
                    pass
                elif file.is_fifo or file.is_socket:
                    typ = "fifo" if file.is_fifo else "socket"
                    if file.size != 0:
                        print(f"{typ} has non-zero size: {file.path}")
                else:
                    print(f"bogus mode: {file.path} ({file.mode:o})")


def main():
    filetypes = list(''.join(filetype).replace('-', 'f'))

    pfile = ArgumentParser(add_help=False)
    pfile.add_argument("file", type=Path)

    poffset = ArgumentParser(add_help=False)
    poffset.add_argument("-o", "--offset", type=int, default=0, help="absolute position of file system's start. Default: %(default)s")

    parser = ArgumentParser()
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(required=True, dest="command")  # dest is only here to avoid a TypeError in Python 3.8 (see bpo-29298)

    helplist = "List the contents of the file system"
    parser_l = subparsers.add_parser("list", parents=[pfile, poffset], help=helplist.lower(), description=helplist)
    parser_l.add_argument("-p", "--pattern", help="filter by file name pattern with fnmatch")
    parser_l.add_argument("-t", "--type", nargs='+', metavar="TYPE", choices=filetypes, help="filter by file type with %(choices)s")
    parser_l.set_defaults(func=list_)

    helpinfo = "Show information about all the superblocks that can be found in a file"
    parser_i = subparsers.add_parser("info", parents=[pfile], help=helpinfo.lower(), description=helpinfo)
    parser_i.set_defaults(func=info)

    helpextr = "Extract files from the file system"
    parser_e = subparsers.add_parser("extract", parents=[pfile, poffset], help=helpextr.lower(), description=helpextr)
    parser_e.add_argument("-d", "--dest", type=Path, help="destination directory. Default: next to file")
    parser_e.add_argument("-p", "--path", type=PurePosixPath, default='/', help="absolute path of directory or file to extract. Default: %(default)r")
    parser_e.add_argument("-f", "--force", action="store_true", help="overwrite files that already exist. Default: %(default)s")
    parser_e.add_argument("-q", "--quiet", action="store_true", help="don't print extraction status. Default: %(default)s")
    parser_e.set_defaults(func=extract)

    helpchck = "Make a few superficial checks of the file system"
    parser_c = subparsers.add_parser("check", parents=[pfile, poffset], help=helpchck.lower(), description=helpchck)
    parser_c.set_defaults(func=check)

    args = parser.parse_args()
    if not args.file.exists():
        parser.error("file does not exist")
    if "offset" in args and args.offset is not None:
        if args.offset < 0:
            parser.error("offset cannot be negative")
        if (args.file.stat().st_size - args.offset) < PAGE_SIZE:
            parser.error("a cramfs image can't fit at this offset")
    try:
        args.func(args)
    except Exception as e:
        parser.error(repr(e))


if __name__ == "__main__":
    main()
