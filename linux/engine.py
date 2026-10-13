"""Typed bindings to the original Zig rules. No gameplay is implemented here."""
import ctypes as C
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESETS = [(9, 9, 10), (16, 16, 40), (30, 16, 99)]


class Info(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ('w', 'h', 'mines', 'mode', 'seed', 'started', 'over', 'win')]
    _fields_ += [('boom', C.c_int32)]
    _fields_ += [(name, C.c_uint32) for name in ('elapsed_ms', 'moves', 'msg')]
    _fields_ += [('totals', C.c_uint32 * 4), ('flags', C.c_uint32 * 4)]


class Cell(C.Structure):
    _fields_ = [('clue', C.c_int16)] + [(name, C.c_uint8) for name in
                                     ('mine', 'open', 'flag', 'blank')]


class Engine:
    def __init__(self):
        self.lib = C.CDLL(str(ROOT / 'linux' / 'libcomplexweeper.so'))
        declarations = {
            'cs_create': ([], C.c_void_p),
            'cs_destroy': ([C.c_void_p], None),
            'cs_configure': ([C.c_void_p] + [C.c_uint32] * 4 +
                             [C.POINTER(C.c_uint32), C.c_uint32], C.c_uint32),
            'cs_new': ([C.c_void_p, C.c_uint32], None),
            'cs_tick': ([C.c_void_p, C.c_uint32], None),
            'cs_reveal': ([C.c_void_p, C.c_uint32, C.c_uint32], C.c_uint32),
            'cs_expand': ([C.c_void_p, C.c_uint32, C.c_uint32], C.c_uint32),
            'cs_flag': ([C.c_void_p, C.c_uint32], C.c_uint32),
            'cs_info': ([C.c_void_p, C.POINTER(Info)], None),
            'cs_cells': ([C.c_void_p, C.POINTER(Cell), C.c_uint32], C.c_uint32),
        }
        for name, (args, result) in declarations.items():
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.lib.cs_create()
        if not self.handle:
            raise MemoryError('无法创建棋盘')
        self.info = Info()
        self.cells = (Cell * 1200)()
        self.sync()

    def close(self):
        if self.handle:
            self.lib.cs_destroy(self.handle)
            self.handle = None

    def configure(self, w, h, mines, mode, counts=(0, 0, 0, 0), seed=1):
        vals = (w, h, mines, mode, *counts, seed)
        if len(counts) != 4 or any(not isinstance(v, int) or v < 0 or v > 0xFFFFFFFF for v in vals):
            raise ValueError('棋盘参数不合法')
        if not self.lib.cs_configure(self.handle, w, h, mines, mode,
                                     (C.c_uint32 * 4)(*counts), seed):
            raise ValueError('宽 9–40、高 9–30；雷数需为 1 到格子总数减 9')
        self.sync()

    def new(self, seed):
        self.lib.cs_new(self.handle, seed & 0xFFFFFFFF)
        self.sync()

    def action(self, name, cell, now=0):
        if name not in ('reveal', 'flag', 'expand'):
            raise ValueError(name)
        if not isinstance(cell, int) or not 0 <= cell < self.info.w * self.info.h:
            return False
        args = (self.handle, cell) if name == 'flag' else (self.handle, cell, now & 0xFFFFFFFF)
        result = getattr(self.lib, 'cs_' + name)(*args)
        self.sync()
        return bool(result)

    def tick(self, now):
        self.lib.cs_tick(self.handle, now & 0xFFFFFFFF)
        self.lib.cs_info(self.handle, C.byref(self.info))

    def sync(self):
        self.lib.cs_info(self.handle, C.byref(self.info))
        self.lib.cs_cells(self.handle, self.cells, len(self.cells))

    def neighbors(self, cell):
        w, h = self.info.w, self.info.h
        r, c = divmod(cell, w)
        return [(r + dy) * w + c + dx for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dx or dy) and 0 <= r + dy < h and 0 <= c + dx < w]
