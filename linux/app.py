#!/usr/bin/env python3
"""Linux GTK frontend for Complexweeper 1.2.0."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from engine import Engine, PRESETS, ROOT


def now_ms():
    return int(time.monotonic()*1000) & 0xFFFFFFFF


def main():
    parser = argparse.ArgumentParser(description='复扫雷 · Linux 原生版')
    parser.add_argument('--selftest', action='store_true', help='运行原版规则自检及 Linux 回归测试')
    parser.add_argument('--smoke-test', type=Path, help='在真实 GTK 窗口内测试操作并保存报告')
    parser.add_argument('--screenshot', type=Path, help='保存棋盘 PNG，不需要桌面会话')
    parser.add_argument('--seed', type=int, help='使用固定棋盘种子')
    parser.add_argument('--mode', choices=['complex', 'hyper'], default='complex')
    parser.add_argument('--preset', type=int, choices=[0, 1, 2], default=0)
    parser.add_argument('--config-dir', type=Path, help='指定设置与纪录目录')
    parser.add_argument('--mute', action='store_true', help='本次运行静音，不修改设置')
    args = parser.parse_args()
    if args.selftest:
        result = subprocess.run([str(ROOT/'linux'/'rules-selftest')])
        if result.returncode:
            return result.returncode
        return subprocess.run([sys.executable, str(ROOT/'linux'/'test_port.py')]).returncode

    from render import Renderer
    if args.screenshot:
        engine = Engine()
        engine.configure(*PRESETS[args.preset], int(args.mode == 'hyper'), seed=args.seed or 1)
        if args.seed is not None:
            engine.action('reveal', 4*engine.info.w+4)
        Renderer(engine).screenshot(args.screenshot)
        engine.close()
        return 0

    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
    except (ImportError, ValueError):
        print('缺少 GTK/Python 依赖，请查看 README-Linux.md 中的安装说明。', file=sys.stderr)
        return 1
    ok, _ = Gtk.init_check(None)
    if not ok:
        print('无法连接桌面会话，请在 Linux 桌面的终端或文件管理器中启动。', file=sys.stderr)
        return 1

    from preferences import Preferences
    from controller import Controller
    from sound import Sound
    hint = '左键翻开 · 右键换旗\n中键 / 左右键展开 · F2 重开'

    class GameWindow(Gtk.Window):
        def __init__(self):
            super().__init__(title='复扫雷 Complexweeper · Linux')
            self.engine = Engine()
            self.renderer = Renderer(self.engine)
            self.preferences = Preferences(args.config_dir)
            self.sound = Sound(fake=bool(args.smoke_test))
            self.preset = args.preset
            self.counts = (0, 0, 0, 0)
            self.zoom = self.preferences.data['zoom']
            self.flash_until = 0
            self.last_second = -1
            self.finished = False
            self.closed = False
            self.updating_menu = False
            self.engine.configure(*PRESETS[self.preset], int(args.mode == 'hyper'),
                                  seed=args.seed if args.seed is not None else secrets.randbits(32))
            self.controller = Controller(self.engine, self.renderer, self.after_action,
                                         self.new_game, now_ms, self.zoom)
            atlas = GdkPixbuf.Pixbuf.new_from_file(str(ROOT/'素材'/'图集.png'))
            icon = self.renderer.slots['icon']
            self.set_icon(atlas.new_subpixbuf(icon['x'], icon['y'], icon['w'], icon['h']))
            self.connect('destroy', self.close)
            self.connect('key-press-event', self.key)
            self.connect('focus-out-event', self.focus_out)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.add(outer)
            self.menus = Gtk.MenuBar()
            outer.pack_start(self.menus, False, False, 0)
            self.build_menus()
            self.scroll = Gtk.ScrolledWindow()
            self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            outer.pack_start(self.scroll, True, True, 0)
            self.area = Gtk.DrawingArea()
            self.area.set_halign(Gtk.Align.CENTER)
            self.area.set_valign(Gtk.Align.START)
            self.area.set_can_focus(True)
            self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                                 Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
            self.area.connect('draw', self.draw_board)
            self.area.connect('button-press-event', self.mouse_down)
            self.area.connect('button-release-event', self.mouse_up)
            self.area.connect('motion-notify-event', self.mouse_move)
            self.area.connect('leave-notify-event', self.mouse_leave)
            self.area.connect('grab-broken-event', self.grab_broken)
            self.scroll.add(self.area)
            self.status = Gtk.Label(label=hint)
            self.status.set_line_wrap(True)
            self.status.set_max_width_chars(34)
            self.status.set_justify(Gtk.Justification.CENTER)
            self.status.set_margin_start(8)
            self.status.set_margin_end(8)
            self.status.set_margin_top(5)
            self.status.set_margin_bottom(5)
            outer.pack_end(self.status, False, False, 0)
            self.fit()
            self.sync_menu()
            self.timer = GLib.timeout_add(100, self.tick)

        def menu(self, title):
            item, menu = Gtk.MenuItem(label=title), Gtk.Menu()
            item.set_submenu(menu)
            self.menus.append(item)
            return menu

        @staticmethod
        def item(menu, title, callback):
            item = Gtk.MenuItem(label=title)
            item.connect('activate', lambda *_: callback())
            menu.append(item)
            return item

        def build_menus(self):
            game_menu = self.menu('游戏')
            self.item(game_menu, '新游戏  F2', self.new_game)
            self.sound_item = Gtk.CheckMenuItem(label='声音')
            self.sound_item.set_active(self.preferences.data['sound'])
            self.sound_item.connect('toggled', self.toggle_sound)
            game_menu.append(self.sound_item)
            self.item(game_menu, '退出  Ctrl+Q', self.destroy)
            self.preset_items = {}
            group = None
            for mode, name in enumerate(('圆复数', '双曲复数')):
                menu = self.menu(name)
                for idx, (w, h, mines) in enumerate(PRESETS):
                    item = Gtk.RadioMenuItem.new_with_label_from_widget(group, f'{("初级", "中级", "高级")[idx]} {w}×{h} · {mines} 雷')
                    if group is None:
                        group = item
                    item.connect('toggled', self.preset_toggled, mode, idx)
                    menu.append(item)
                    self.preset_items[mode, idx] = item
                self.item(menu, '自定义…', lambda m=mode: self.custom_dialog(m))
                self.item(menu, '最佳纪录…', lambda m=mode: self.scores_dialog(m))
            # An invisible member represents a custom board, so no preset is falsely selected.
            self.custom_radio = Gtk.RadioMenuItem.new_with_label_from_widget(group, '自定义')
            view = self.menu('显示')
            self.zoom_items = {}
            group = None
            for z in (1, 2, 3):
                item = Gtk.RadioMenuItem.new_with_label_from_widget(group, f'{z} 倍')
                if group is None:
                    group = item
                item.connect('toggled', self.zoom_toggled, z)
                view.append(item)
                self.zoom_items[z] = item
            help_menu = self.menu('帮助')
            self.item(help_menu, '怎么玩  F1', self.help_dialog)
            self.item(help_menu, '关于', self.about_dialog)

        def sync_menu(self):
            self.updating_menu = True
            if self.preset is None:
                self.custom_radio.set_active(True)
            else:
                self.preset_items[self.engine.info.mode, self.preset].set_active(True)
            self.zoom_items[self.zoom].set_active(True)
            self.updating_menu = False

        def preset_toggled(self, item, mode, idx):
            if item.get_active() and not self.updating_menu:
                self.set_preset(mode, idx)

        def set_preset(self, mode, idx):
            self.preset, self.counts = idx, (0, 0, 0, 0)
            self.engine.configure(*PRESETS[idx], mode, seed=secrets.randbits(32))
            self.reset_ui()
            self.fit()
            self.sync_menu()

        def zoom_toggled(self, item, z):
            if item.get_active() and not self.updating_menu:
                self.zoom = self.controller.zoom = z
                self.controller.clear()
                self.preferences.data['zoom'] = z
                self.preferences.save()
                self.fit()

        def fit(self):
            L = self.renderer.layout(self.zoom)
            self.area.set_size_request(L.width, L.height)
            display = self.get_display()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            rect = monitor.get_workarea()
            width = min(max(430, L.width+2), max(320, rect.width-100))
            height = min(L.height+110, max(320, rect.height-100))
            self.scroll.set_min_content_width(min(width, 380))
            self.scroll.set_min_content_height(min(height-66, 300))
            self.resize(width, height)

        def reset_ui(self):
            self.controller.clear()
            self.finished = False
            self.last_second = -1
            self.flash_until = 0
            self.status.set_text(hint)
            for p in self.sound.players.values():
                p.set_state(self.sound.Gst.State.NULL)
            self.area.queue_draw()

        def new_game(self):
            self.engine.new(secrets.randbits(32))
            self.reset_ui()

        def after_action(self, action):
            s = self.engine.info
            if s.over and not self.finished:
                self.finished = True
                self.play('win' if s.win else f'mine_{self.engine.cells[s.boom].mine}')
                if s.win:
                    message = f'胜利！用时 {s.elapsed_ms//1000} 秒。点击笑脸或按 F2 再来一局。'
                    if self.preset is not None and self.preferences.record(s.mode, self.preset, s.elapsed_ms//1000):
                        message += ' 新纪录！' if self.preferences.error is None else ' 纪录暂未保存。'
                    self.status.set_text(message)
                else:
                    self.status.set_text('踩雷了。棋盘已显示正确答案；点击笑脸或按 F2 重开。')
            elif not s.over:
                self.flash_until = time.monotonic()+0.2
            self.area.queue_draw()

        def play(self, name):
            if not args.mute and self.preferences.data['sound']:
                self.sound.play(name)

        def toggle_sound(self, item):
            self.preferences.data['sound'] = item.get_active()
            self.preferences.save()
            if not item.get_active():
                for p in self.sound.players.values():
                    p.set_state(self.sound.Gst.State.NULL)

        def tick(self):
            self.engine.tick(now_ms())
            s = self.engine.info
            sec = s.elapsed_ms//1000
            if s.started and not s.over and sec != self.last_second:
                if sec > 0:
                    self.play('tick')
                self.last_second = sec
            self.area.queue_draw()
            return True

        def draw_board(self, _, ctx):
            c = self.controller
            self.renderer.paint(ctx, self.zoom, c.press, c.chord, c.face_down,
                                time.monotonic() < self.flash_until)
            return False

        def mouse_down(self, _, event):
            # GDK emits a normal press AND an additional double/triple-click event.
            if event.type == Gdk.EventType.BUTTON_PRESS:
                self.area.grab_focus()
                self.controller.down(event.button, event.x, event.y)
                self.area.queue_draw()
            return True

        def mouse_up(self, _, event):
            self.controller.up(event.button, event.x, event.y)
            self.area.queue_draw()
            return True

        def mouse_move(self, _, event):
            self.controller.move(event.x, event.y)
            self.area.queue_draw()
            return True

        def mouse_leave(self, *_):
            self.controller.move(-1, -1)
            self.area.queue_draw()
            return False

        def grab_broken(self, *_):
            self.controller.clear()
            self.area.queue_draw()
            return False

        def focus_out(self, *_):
            self.grab_broken()
            return False

        def key(self, _, event):
            if event.keyval == Gdk.KEY_F2:
                self.new_game()
            elif event.keyval == Gdk.KEY_F1:
                self.help_dialog()
            elif event.keyval in (Gdk.KEY_q, Gdk.KEY_Q) and event.state & Gdk.ModifierType.CONTROL_MASK:
                self.destroy()
            elif event.keyval == Gdk.KEY_Escape:
                self.grab_broken()
            else:
                return False
            return True

        def message(self, title, text):
            dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                       message_type=Gtk.MessageType.INFO,
                                       buttons=Gtk.ButtonsType.CLOSE, text=title)
            dialog.format_secondary_text(text)
            dialog.run()
            dialog.destroy()

        def help_dialog(self):
            self.message('怎么玩',
                '左键翻开；右键循环 空 → +1 → −1 → +i/＋j → −i/−j → 空。\n'
                '中键或左右键同时按住已翻开的数字格，松开后尝试展开。\n'
                '第一次翻开的位置及周围八格安全。翻开所有非雷格才算胜利。\n\n'
                '圆复数：数字是 √(a²+b²)。空白表示周围没有雷；0 表示正负抵消。'
                '展开要求旗数等于真实邻雷数，实虚类型的数量匹配，或整体交换。\n\n'
                '双曲复数：数字是 √(a²−b²)，负值显示为根式加 i。'
                '雷的单位是 j（j²=1）；展开要求旗数一致，且 |a|、|b| 分别匹配。\n\n'
                '展开判据通过仍可能踩雷：旗帜的位置也必须正确。\n'
                'F2 / 笑脸：重开。大棋盘可以滚动，显示菜单可切换 1–3 倍。')

        def about_dialog(self):
            self.message('复扫雷 Complexweeper 1.2.0 · Linux 移植版',
                '原作者：青月晓（Yueqing-Chen）。\nLinux 界面：GTK 3 / Python；规则：原版 Zig。\n'
                '代码遵循 GPL-3.0，源码与 LICENSE 随包提供。\n'
                '原版扫雷图像来自 Microsoft，新增素材来自青月晓。\n'
                '本程序与 Microsoft 公司无隶属关系。')

        def scores_dialog(self, mode):
            rows = []
            for idx, name in enumerate(('初级', '中级', '高级')):
                best = self.preferences.best(mode, idx)
                rows.append(f'{name}：{best} 秒' if best is not None else f'{name}：暂无纪录')
            self.message(('圆复数' if mode == 0 else '双曲复数')+' · 最佳纪录', '\n'.join(rows))

        def custom_dialog(self, mode):
            dialog = Gtk.Dialog(title=('圆复数' if mode == 0 else '双曲复数')+' · 自定义',
                                transient_for=self, modal=True)
            dialog.add_buttons('取消', Gtk.ResponseType.CANCEL, '开始', Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.OK)
            grid = Gtk.Grid(column_spacing=12, row_spacing=10)
            grid.set_border_width(16)
            dialog.get_content_area().add(grid)
            unit = 'j' if mode else 'i'
            values = [self.engine.info.w, self.engine.info.h]
            total = self.engine.info.mines
            values += list(self.counts) if any(self.counts) else [total//4 + int(i < total%4) for i in range(4)]
            fields = []
            for i, (label, value, low, high) in enumerate(zip(
                ['宽度', '高度', '+1 雷', '−1 雷', f'+{unit} 雷', f'−{unit} 雷'],
                values, [9, 9, 0, 0, 0, 0], [40, 30, 1191, 1191, 1191, 1191])):
                grid.attach(Gtk.Label(label=label, xalign=0), 0, i, 1, 1)
                field = Gtk.SpinButton.new_with_range(low, high, 1)
                field.set_value(value)
                field.set_numeric(True)
                field.set_activates_default(True)
                grid.attach(field, 1, i, 1, 1)
                fields.append(field)
            even = Gtk.Button(label='将当前总雷数均分给四种雷')
            def split(*_):
                total = sum(f.get_value_as_int() for f in fields[2:])
                for i, f in enumerate(fields[2:]):
                    f.set_value(total//4+int(i < total%4))
            even.connect('clicked', split)
            grid.attach(even, 0, 6, 2, 1)
            error = Gtk.Label(label='雷数总和需为 1 到宽×高−9；首击周围保留安全区。')
            error.set_line_wrap(True)
            grid.attach(error, 0, 7, 2, 1)
            dialog.show_all()
            while dialog.run() == Gtk.ResponseType.OK:
                for f in fields:
                    f.update()
                w, h = [f.get_value_as_int() for f in fields[:2]]
                counts = tuple(f.get_value_as_int() for f in fields[2:])
                try:
                    if not sum(counts):
                        raise ValueError('至少需要一颗雷。')
                    self.engine.configure(w, h, sum(counts), mode, counts, secrets.randbits(32))
                except ValueError as e:
                    error.set_text(str(e))
                    continue
                self.preset, self.counts = None, counts
                self.reset_ui()
                self.fit()
                self.sync_menu()
                break
            dialog.destroy()

        def close(self, *_):
            if self.closed:
                return
            self.closed = True
            GLib.source_remove(self.timer)
            self.sound.close()
            self.engine.close()
            Gtk.main_quit()

    window = GameWindow()
    window.show_all()
    if args.smoke_test:
        from smoke_test import schedule
        schedule(window, args.smoke_test, Gtk, Gdk, GLib)
    Gtk.main()
    return getattr(window, 'test_exit_code', 0)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OSError as e:
        print(f'启动失败：{e}\n请查看 README-Linux.md；重新构建可运行 ./build-linux.sh。', file=sys.stderr)
        sys.exit(1)
