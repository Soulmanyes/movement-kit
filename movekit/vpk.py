"""Valve's VPK archives (v1 and v2): which files a VPK holds, and reading one out of it.

A game's VPK set is a <name>_dir.vpk holding the directory tree (and some small files after it), plus
numbered <name>_000.vpk, _001.vpk ... archives with the rest. A single .vpk (a mod in custom/) holds
everything itself.
"""
import struct

SIGNATURE = 0x55AA1234
_IN_DIR = 0x7FFF  # archive index of a file stored in the _dir.vpk itself, after the tree


def read_tree(path):
    """{path: (archive_index, offset, length, preload_bytes)} with lower-case paths, and the offset in
    the file where its own data starts. Raises OSError, ValueError (not a VPK v1/v2, cut short) or
    struct.error (shorter than the header)."""
    with open(path, "rb") as f:
        sig, version, tree_size = struct.unpack("<III", f.read(12))
        if sig != SIGNATURE or version not in (1, 2):
            raise ValueError(f"{path} is not a VPK v1 or v2")
        header = 12 if version == 1 else 28
        f.seek(header)
        blob = f.read(tree_size)
    pos = 0

    def string():
        nonlocal pos
        end = blob.index(b"\0", pos)
        text = blob[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return text

    tree = {}
    while (ext := string()):
        while (folder := string()):
            while (name := string()):
                _crc, preload, archive, offset, length, _end = struct.unpack_from("<IHHIIH", blob, pos)
                pos += 18
                # " " is the folder of files at the VPK's root
                rel = f"{'' if folder == ' ' else folder + '/'}{name}.{ext}".lower()
                tree[rel] = (archive, offset, length, blob[pos:pos + preload])
                pos += preload
    return tree, header + tree_size


def files(path):
    """The file paths a VPK lists, lower case; empty if it can't be read."""
    try:
        return set(read_tree(path)[0])
    except (OSError, struct.error, ValueError):
        return set()


_trees = {}


def read_file(dir_vpk, rel):
    """The bytes of the file at rel (any case) in the VPK set whose _dir.vpk is dir_vpk, or None if it
    has no such file. The tree is read once per dir_vpk and kept. Raises like read_tree."""
    if dir_vpk not in _trees:
        _trees[dir_vpk] = read_tree(dir_vpk)
    tree, data_start = _trees[dir_vpk]
    hit = tree.get(rel.lower())
    if not hit:
        return None
    archive, offset, length, preload = hit
    if archive == _IN_DIR:
        source, offset = dir_vpk, data_start + offset
    else:
        source = str(dir_vpk).replace("_dir.vpk", f"_{archive:03d}.vpk")
    with open(source, "rb") as f:
        f.seek(offset)
        return preload + f.read(length)
