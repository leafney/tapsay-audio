#!/usr/bin/env python3
"""Atomically promote an already verified directory on supported macOS."""
import ctypes
import os
from pathlib import Path
import sys


def publish(staged, destination):
    staged, destination = Path(staged), Path(destination)
    if staged.is_symlink() or destination.is_symlink() or not staged.is_dir():
        raise ValueError('发布目录必须是普通目录')
    if not destination.exists():
        os.rename(staged, destination)
        return
    if not destination.is_dir():
        raise ValueError('原产物路径不是目录')
    # RENAME_SWAP exchanges both directories in one filesystem operation. If it
    # fails, both the old release and the staged release remain in place.
    library = ctypes.CDLL(None, use_errno=True)
    exchange = library.renameatx_np
    exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    exchange.restype = ctypes.c_int
    if exchange(-2, os.fsencode(staged), -2, os.fsencode(destination), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


if __name__ == '__main__':
    publish(*sys.argv[1:])
