"""A sealed root made in a test: a squashfs-shaped root with its dm-verity
tree after it, laid out as image/seal-root's veritysetup leaves one (format
1, sha256, 4096-byte blocks, the top level first), written here on its own
so the reader in osimage.py is held to the layout and not to itself.
test_sealed_root.py holds this writer to the real veritysetup where one is
here."""
import hashlib

BLOCK = 4096


def root(payload=b"r", blocks=3):
    """A root of `blocks` blocks that reads as a squashfs: the magic, and
    its own length where a squashfs keeps it."""
    size = blocks * BLOCK - 7                      # not a whole block: the tree starts at the next one
    return (b"hsqs" + b"\0" * 36 + size.to_bytes(8, "little") + payload * size)[:size]


def seal(data, salt=b"\x5a" * 32):
    """(the root with its tree, the root hash as hex)."""
    data = data.ljust(-(-len(data) // BLOCK) * BLOCK, b"\0")
    blocks = len(data) // BLOCK

    def digests(of):
        return b"".join(hashlib.sha256(salt + of[i:i + BLOCK]).digest() for i in range(0, len(of), BLOCK))
    levels, below = [], digests(data)
    while len(below) > 32:
        level = below.ljust(-(-len(below) // BLOCK) * BLOCK, b"\0")
        levels.append(level)
        below = digests(level)
    sup = (b"verity\0\0" + (1).to_bytes(4, "little") + (1).to_bytes(4, "little") + b"\x11" * 16 + b"sha256".ljust(32, b"\0")
           + BLOCK.to_bytes(4, "little") + BLOCK.to_bytes(4, "little") + blocks.to_bytes(8, "little")
           + len(salt).to_bytes(2, "little") + b"\0" * 6 + salt.ljust(256, b"\0")).ljust(BLOCK, b"\0")
    return data + sup + b"".join(reversed(levels)), below.hex()


def initrd(root_hash, size, body=b"initrd"):
    """An initrd carrying the hash as seal-root appends it: the file's own
    line is in its last bytes, not compressed."""
    return body.ljust(512, b"\0") + f"etc/aerieos-verity\0HASH={root_hash}\nBYTES={size}\n".encode()
