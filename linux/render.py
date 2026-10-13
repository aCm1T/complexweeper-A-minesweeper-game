"""Original sprite atlas rendered with Cairo, independent of a desktop session."""
import json
from dataclasses import dataclass
import cairo
from engine import ROOT


def value_digits(value, base=4):
    return base if value is None else max(base, len(str(value)))


@dataclass
class Layout:
    z: int
    width: int
    height: int
    hx: int
    hy: int
    hw: int
    hh: int
    bx: int
    by: int
    cell: int
    fx: int
    fy: int
    tx: int
    ty: int


class Renderer:
    def __init__(self, engine):
        self.engine = engine
        self.atlas = cairo.ImageSurface.create_from_png(str(ROOT / '素材' / '图集.png'))
        meta = json.loads((ROOT / '素材' / '图集.json').read_text())
        self.slots = {x['name']: x for x in meta['slots']}

    def typed(self, family, t):
        return ('h' if self.engine.info.mode and t >= 3 else '') + f'{family}_{t}'

    def counter(self, t):
        s = self.engine.info
        if not s.started:
            return None
        remaining = int(s.totals[t-1]) - int(s.flags[t-1])
        return -remaining if t in (2, 4) else remaining

    def layout(self, z):
        s = self.engine.info
        board_width = s.w * 16*z + 6*z
        counter_width = max((20 + 13 * (value_digits(self.counter(t), 3 if t >= 3 else 4) +
                                         int(t >= 3))) * z for t in range(1, 5))
        inner = max(board_width, (4 + 8 + 24 + 8 + 54 + 4)*z + counter_width)
        width, height = inner + 18*z, (18 + 120 + 6 + s.h*16 + 6)*z
        hx = hy = 9*z
        tx = hx + inner - 4*z - 54*z
        fx = hx + inner//2 - 12*z
        fx = max(fx, hx + 4*z + counter_width + 6*z)
        fx = min(fx, tx - 6*z - 24*z)
        return Layout(z, width, height, hx, hy, inner, 120*z,
                      hx + (inner - board_width)//2 + 3*z, hy + 129*z, 16*z,
                      fx - 2, hy + 48*z - 2, tx, hy + 47*z)

    def sprite(self, ctx, name, x, y, width, height=None):
        s = self.slots[name]
        height = width if height is None else height
        ctx.save()
        ctx.rectangle(x, y, width, height)
        ctx.clip()
        ctx.translate(x, y)
        ctx.scale(width/s['w'], height/s['h'])
        ctx.set_source_surface(self.atlas, -s['x'], -s['y'])
        ctx.get_source().set_filter(cairo.FILTER_NEAREST)
        ctx.paint()
        ctx.restore()

    @staticmethod
    def fill(ctx, x, y, w, h, color):
        ctx.set_source_rgb(*(v/255 for v in color))
        ctx.rectangle(x, y, w, h)
        ctx.fill()

    def bevel(self, ctx, x, y, w, h, t, raised=False):
        hi, lo = (255, 255, 255), (128, 128, 128)
        if not raised:
            hi, lo = lo, hi
        self.fill(ctx, x, y, w, t, hi)
        self.fill(ctx, x, y, t, h, hi)
        self.fill(ctx, x, y+h-t, w, t, lo)
        self.fill(ctx, x+w-t, y, t, h, lo)

    def led(self, ctx, x, y, value, digits, z):
        if value is None:
            names = ['led_blank'] * digits
        else:
            val = min(max(value, -(10**(digits-1)-1)), 10**digits-1)
            chars = ('-' + str(-val).zfill(digits-1)) if val < 0 else str(val).zfill(digits)
            names = ['led_minus' if c == '-' else 'led_' + c for c in chars]
        for i, name in enumerate(names):
            self.sprite(ctx, name, x+i*13*z, y, 13*z, 23*z)

    def chordable(self, cell):
        s = self.engine.info
        if cell is None or not 0 <= cell < s.w*s.h or s.over:
            return False
        c = self.engine.cells[cell]
        return bool(c.open and not c.mine and any(not self.engine.cells[j].open and
                    not self.engine.cells[j].flag for j in self.engine.neighbors(cell)))

    def cell_sprite(self, i, press=None, chord=None):
        c, s = self.engine.cells[i], self.engine.info
        if not c.open and not c.flag and (press == i or
                (self.chordable(chord) and i in self.engine.neighbors(chord))):
            return 'blank'
        if c.open:
            if c.mine:
                return self.typed('boom' if s.boom == i else 'mine', c.mine)
            if c.blank:
                return 'blank'
            if s.mode and c.clue < 0:
                return f'hnum_{-c.clue}_i'
            name = f'hnum_{c.clue}'
            return name if s.mode and name in self.slots else f'num_{c.clue}'
        if c.flag:
            if s.over and not s.win:
                if not c.mine:
                    return 'wrongblank'
                return self.typed('right' if c.flag == c.mine else 'wrong', c.mine)
            if s.win:
                return self.typed('rightflag' if c.flag == c.mine else 'wrongflag', c.mine or c.flag)
            return self.typed('flag', c.flag)
        if s.over and not s.win and c.mine:
            return self.typed('mine', c.mine)
        return 'closed'

    def paint(self, ctx, z=2, press=None, chord=None, face_down=False, flash=False):
        L, s = self.layout(z), self.engine.info
        ctx.set_antialias(cairo.ANTIALIAS_NONE)
        self.fill(ctx, 0, 0, L.width, L.height, (192, 192, 192))
        self.bevel(ctx, 0, 0, L.width, L.height, 3*z, True)
        self.bevel(ctx, L.hx, L.hy, L.hw, L.hh, 2*z)
        x, y = L.hx+4*z, L.hy+5*z
        for t in range(1, 5):
            val = self.counter(t)
            digits = value_digits(val, 3 if t >= 3 else 4)
            cells = digits + int(t >= 3)
            self.bevel(ctx, x, y, (20+13*cells)*z, 26*z, z)
            self.sprite(ctx, self.typed('flag', t), x+2*z, y+5*z, 16*z)
            self.led(ctx, x+19*z, y+z, val, digits, z)
            if t >= 3:
                unit = 'led_blank' if val is None else ('led_j' if s.mode else 'led_i')
                self.sprite(ctx, unit, x+(19+digits*13)*z, y+z, 13*z, 23*z)
            y += 28*z
        self.bevel(ctx, L.tx, L.ty, 54*z, 26*z, z)
        self.led(ctx, L.tx+z, L.ty+z, min(s.elapsed_ms//1000, 9999) if s.started else None, 4, z)
        face = ('face_down' if face_down else 'face_win' if s.win else 'face_dead' if s.over
                else 'face_scan' if press is not None or chord is not None or flash else 'face_normal')
        self.sprite(ctx, face, L.fx, L.fy, 24*z)
        self.bevel(ctx, L.bx-3*z, L.by-3*z, s.w*L.cell+6*z, s.h*L.cell+6*z, 3*z)
        for i in range(s.w*s.h):
            r, c = divmod(i, s.w)
            self.sprite(ctx, self.cell_sprite(i, press, chord), L.bx+c*L.cell, L.by+r*L.cell, L.cell)
        return L

    def screenshot(self, path, z=2):
        L = self.layout(z)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.width, L.height)
        self.paint(cairo.Context(surface), z)
        surface.write_to_png(str(path))
