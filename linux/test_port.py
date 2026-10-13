"""Regression tests for the Linux boundary, input gestures and persistence."""
import ctypes as C
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from controller import Controller
from engine import Engine, PRESETS
from preferences import Preferences
from render import Renderer


class PortTests(unittest.TestCase):
    def setUp(self):
        self.e = Engine()
        self.r = Renderer(self.e)

    def tearDown(self):
        self.e.close()

    def test_first_click_safe_both_modes_all_presets(self):
        for mode, preset, seed in itertools.product(range(2), PRESETS, [1, 42, 0xFFFFFFFF]):
            self.e.configure(*preset, mode, seed=seed)
            cell = (preset[1]//2)*preset[0] + preset[0]//2
            self.e.action('reveal', cell, 100)
            self.assertEqual(sum(c.mine != 0 for c in self.e.cells[:self.e.info.w*self.e.info.h]), preset[2])
            for j in [cell]+self.e.neighbors(cell):
                self.assertEqual(self.e.cells[j].mine, 0)
            self.assertTrue(self.e.cells[cell].blank)
            for i in range(self.e.info.w*self.e.info.h):
                self.assertIn(self.r.cell_sprite(i), self.r.slots)

    def test_seed_determinism(self):
        self.e.configure(30, 16, 99, 1, seed=987654)
        self.e.action('reveal', 250)
        first = bytes(self.e.cells)
        self.e.new(987654)
        self.e.action('reveal', 250)
        self.assertEqual(first, bytes(self.e.cells))

    def test_boundary_rejects_invalid_input_without_changing_game(self):
        before = bytes(self.e.info)
        for values in [(0, 9, 1, 0), (41, 9, 1, 0), (9, 31, 1, 0),
                       (9, 9, 73, 0), (9, 9, 0, 0), (9, 9, 1, 2)]:
            with self.assertRaises(ValueError):
                self.e.configure(*values)
            self.assertEqual(bytes(self.e.info), before)
        counts = (C.c_uint32*4)(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertEqual(self.e.lib.cs_configure(self.e.handle, 9, 9, 1, 0, counts, 1), 0)
        for cell in (-1, 81, 0xFFFFFFFF):
            self.assertFalse(self.e.action('flag', cell))
        self.assertEqual(self.e.lib.cs_reveal(self.e.handle, 0xFFFFFFFF, 0), 0)
        self.assertEqual(self.e.lib.cs_cells(self.e.handle, self.e.cells, 1), 0)

    def test_flags_preserved_before_start_and_protect_cells(self):
        for value in (1, 2, 3, 4, 0, 1):
            self.assertTrue(self.e.action('flag', 0))
            self.assertEqual(self.e.cells[0].flag, value)
        self.assertFalse(self.e.action('reveal', 0))
        self.assertFalse(self.e.info.started)
        self.e.action('reveal', 40)
        self.assertEqual(self.e.cells[0].flag, 1)
        self.assertFalse(self.e.cells[0].open)

    def test_timer_wrap_and_freeze_after_loss(self):
        self.e.configure(9, 9, 10, 0, seed=123)
        self.e.action('reveal', 40, 0xFFFFFF00)
        self.e.tick(0x00000100)
        self.assertEqual(self.e.info.elapsed_ms, 512)
        mine = next(i for i in range(81) if self.e.cells[i].mine)
        self.e.action('reveal', mine, 0x200)
        stopped = self.e.info.elapsed_ms
        self.e.tick(0xFFFF)
        self.assertEqual(self.e.info.elapsed_ms, stopped)
        self.assertTrue(self.e.info.over)
        self.assertFalse(self.e.info.win)
        self.assertEqual(self.r.cell_sprite(mine), self.r.typed('boom', self.e.cells[mine].mine))

    def test_exact_custom_counts_and_dense_first_click_win(self):
        self.e.configure(40, 30, 1191, 1, (300, 300, 300, 291), 5)
        self.e.action('reveal', 20*40+20)
        self.assertEqual(list(self.e.info.totals), [300, 300, 300, 291])
        self.assertTrue(self.e.info.over and self.e.info.win)

    def test_winning_requires_every_safe_cell_not_flags(self):
        self.e.configure(9, 9, 10, 0, seed=91)
        self.e.action('reveal', 40)
        for i in range(81):
            if self.e.cells[i].mine:
                for _ in range(self.e.cells[i].mine):
                    self.e.action('flag', i)
        self.assertFalse(self.e.info.win)
        for i in range(81):
            if not self.e.cells[i].mine:
                self.e.action('reveal', i, 1000)
        self.assertTrue(self.e.info.win)
        for i in range(81):
            if self.e.cells[i].mine:
                self.assertEqual(self.r.cell_sprite(i), self.r.typed('rightflag', self.e.cells[i].mine))

    def test_layout_large_signed_counters_and_screenshots(self):
        self.e.configure(40, 30, 1, 1, seed=77)
        self.e.action('reveal', 0)
        # Unlimited flags can exceed a three-digit negative counter.
        for i in range(1200):
            if not self.e.cells[i].open:
                self.e.action('flag', i)
                self.e.action('flag', i)
                self.e.action('flag', i)
        # Explicitly check the widest possible valid counter as well.
        self.e.info.totals[2], self.e.info.flags[2] = 0, 1200
        for z in (1, 2, 3):
            L = self.r.layout(z)
            self.assertGreater(L.fx, L.hx+4*z+(20+13*6)*z)
            self.assertLess(L.fx+24*z, L.tx)
            with tempfile.TemporaryDirectory() as d:
                p = Path(d)/'board.png'
                self.r.screenshot(p, z)
                self.assertGreater(p.stat().st_size, 1000)

    def test_mouse_cancel_flag_protection_reset_and_chord(self):
        changes, resets = [], []
        c = Controller(self.e, self.r, changes.append, lambda: resets.append(True), lambda: 1000)
        L = self.r.layout(2)
        x, y = L.bx+4*L.cell+4, L.by+4*L.cell+4
        c.down(1, x, y)
        self.assertFalse(self.e.info.started)
        c.move(-1, -1)
        c.up(1, -1, -1)
        self.assertFalse(self.e.info.started)
        c.down(3, x, y)
        c.up(3, x, y)
        c.down(1, x, y)
        c.up(1, x, y)
        self.assertFalse(self.e.info.started)
        for _ in range(4):
            c.down(3, x, y)
            c.up(3, x, y)
        c.down(1, x, y)
        c.up(1, x, y)
        self.assertTrue(self.e.info.started)
        self.assertEqual(changes[-1], 'reveal')
        c.down(1, L.fx+1, L.fy+1)
        c.up(1, L.fx+1, L.fy+1)
        self.assertTrue(resets)
        c.down(2, x, y)
        c.up(2, x, y)
        self.assertEqual(changes[-1], 'expand')
        c.down(1, x, y)
        c.down(3, x, y)
        c.up(3, x, y)
        self.assertEqual(changes[-1], 'expand')
        c.up(1, x, y)
        self.assertFalse(c.buttons)

    def test_scores_modes_corruption_and_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Preferences(directory)
            self.assertTrue(p.record(0, 0, 0))
            self.assertFalse(p.record(0, 0, 1))
            self.assertTrue(p.record(1, 0, 5))
            p.data['sound'], p.data['zoom'] = False, 3
            self.assertTrue(p.save())
            q = Preferences(directory)
            self.assertEqual(q.best(0, 0), 0)
            self.assertEqual(q.best(1, 0), 5)
            self.assertFalse(q.data['sound'])
            self.assertEqual(q.data['zoom'], 3)
            q.path.write_text('{invalid')
            self.assertEqual(Preferences(directory).data['scores'], {})
            q.path.write_text(json.dumps({'scores': {'0:0': -1}, 'zoom': 100, 'sound': 'false'}))
            self.assertEqual(Preferences(directory).data, {'scores': {}, 'zoom': 2, 'sound': True})


if __name__ == '__main__':
    unittest.main(verbosity=2)
