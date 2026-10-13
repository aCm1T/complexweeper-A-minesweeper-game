"""Exercise a mapped GTK window, including its actual event callbacks and dialogs."""
import json
import time
import traceback
import cairo


def schedule(window, destination, Gtk, Gdk, GLib):
    destination.mkdir(parents=True, exist_ok=True)
    checks = []
    started = time.monotonic()
    audio_deadline = [0]

    def check(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(name)

    def flush():
        for _ in range(40):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration_do(False)

    def event(button, cell=None, release=False, coords=None, kind=None):
        L = window.renderer.layout(window.zoom)
        if coords is None:
            r, c = divmod(cell, window.engine.info.w)
            coords = (L.bx+c*L.cell+L.cell/2, L.by+r*L.cell+L.cell/2)
        typ = kind or (Gdk.EventType.BUTTON_RELEASE if release else Gdk.EventType.BUTTON_PRESS)
        e = Gdk.Event.new(typ)
        e.window = window.area.get_window()
        e.send_event = True
        e.time = Gdk.CURRENT_TIME
        e.x, e.y = coords
        e.button = button
        window.area.emit('button-release-event' if release else 'button-press-event', e)

    def click(button, cell):
        event(button, cell)
        event(button, cell, True)

    def snapshot(name):
        # Wait briefly for the frame clock to allocate widgets after a board resize.
        for _ in range(4):
            flush()
            time.sleep(0.02)
        window.check_resize()
        flush()
        width, height = window.get_allocated_width(), window.get_allocated_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        window.draw(cairo.Context(surface))
        surface.write_to_png(str(destination/f'{name}.png'))

    def close_next_dialog(response=Gtk.ResponseType.CLOSE):
        def close():
            for d in Gtk.Window.list_toplevels():
                if isinstance(d, Gtk.Dialog) and d.get_visible():
                    d.response(response)
                    return False
            return True
        GLib.timeout_add(50, close)

    def all_children(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from all_children(child)

    def finish(error=None):
        report = {'passed': not error, 'checks': checks, 'count': len(checks),
                  'seconds': round(time.monotonic()-started, 2),
                  'backend': window.get_display().get_name(), 'error': error}
        (destination/'smoke-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        window.test_exit_code = 1 if error else 0
        window.destroy()

    def run():
        try:
            check('GTK 窗口已创建并显示', window.get_realized() and window.get_mapped())
            snapshot('initial-window')
            for mode in (0, 1):
                for preset, size in enumerate(((9, 9), (16, 16), (30, 16))):
                    window.preset_items[mode, preset].set_active(True)
                    check(f'菜单切换模式 {mode} / 难度 {preset}',
                          window.engine.info.mode == mode and (window.engine.info.w, window.engine.info.h) == size)
            window.preset_items[0, 0].set_active(True)
            window.engine.new(42)
            for z in (1, 3, 2):
                window.zoom_items[z].set_active(True)
                check(f'{z} 倍缩放', window.zoom == z and window.controller.zoom == z)
            click(3, 40)
            check('右键设置第一面旗', window.engine.cells[40].flag == 1)
            event(3, 40, kind=Gdk.EventType.DOUBLE_BUTTON_PRESS)
            check('GDK 双击补充事件不会重复换旗', window.engine.cells[40].flag == 1)
            click(1, 40)
            check('左键保护旗帜，开局前不翻开', not window.engine.info.started)
            for _ in range(4):
                click(3, 40)
            click(1, 40)
            check('左键松开开始游戏', window.engine.info.started and window.engine.cells[40].open)
            snapshot('complex-playing')
            event(2, 40)
            event(2, 40, True)
            check('中键展开手势结束', not window.controller.buttons)
            event(1, 40)
            event(3, 40)
            event(1, 40, True)
            event(3, 40, True)
            check('左右键展开不残留按下状态', not window.controller.buttons)
            mine = next(i for i in range(81) if window.engine.cells[i].mine)
            click(1, mine)
            check('踩雷后显示失败状态', window.engine.info.over and not window.engine.info.win)
            snapshot('complex-loss')
            L = window.renderer.layout(window.zoom)
            event(1, coords=(L.fx+10, L.fy+10))
            event(1, coords=(L.fx+10, L.fy+10), release=True)
            check('笑脸按钮重开', not window.engine.info.started and not window.engine.info.over)
            event(1, 40)
            event(1, coords=(-10, -10), release=True)
            check('拖出棋盘松开取消翻格', not window.engine.info.started)
            key = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
            key.keyval, key.state = Gdk.KEY_F2, Gdk.ModifierType(0)
            window.emit('key-press-event', key)
            check('F2 重开', not window.engine.info.started)

            # Drive the real modal custom dialog through an invalid submission then a valid one.
            def valid_custom():
                for d in Gtk.Window.list_toplevels():
                    if isinstance(d, Gtk.Dialog) and '自定义' in (d.get_title() or ''):
                        fields = [c for c in all_children(d) if isinstance(c, Gtk.SpinButton)]
                        fields.sort(key=lambda c: c.get_parent().child_get_property(c, 'top-attach'))
                        for f, val in zip(fields, (12, 10, 4, 3, 2, 1)):
                            f.set_value(val)
                        d.response(Gtk.ResponseType.OK)
                        return False
                return True

            def invalid_custom():
                for d in Gtk.Window.list_toplevels():
                    if isinstance(d, Gtk.Dialog) and '自定义' in (d.get_title() or ''):
                        fields = [c for c in all_children(d) if isinstance(c, Gtk.SpinButton)]
                        fields.sort(key=lambda c: c.get_parent().child_get_property(c, 'top-attach'))
                        for f in fields[2:]:
                            f.set_value(0)
                        d.response(Gtk.ResponseType.OK)
                        GLib.timeout_add(50, valid_custom)
                        return False
                return True

            GLib.timeout_add(50, invalid_custom)
            window.custom_dialog(1)
            check('自定义对话框拒绝零雷后接受有效参数',
                  window.preset is None and (window.engine.info.w, window.engine.info.h) == (12, 10)
                  and window.engine.info.mode == 1 and window.counts == (4, 3, 2, 1))
            click(1, 4*12+4)
            check('自定义精确配比', list(window.engine.info.totals) == [4, 3, 2, 1])
            snapshot('hyper-custom-playing')
            before = (bytes(window.engine.cells), window.engine.info.seed,
                      window.engine.info.mode, window.engine.info.moves)
            close_next_dialog(Gtk.ResponseType.CANCEL)
            window.custom_dialog(0)
            check('取消自定义不改变局面', before == (bytes(window.engine.cells), window.engine.info.seed,
                  window.engine.info.mode, window.engine.info.moves))
            for name, show in [('help', window.help_dialog), ('about', window.about_dialog),
                               ('scores', lambda: window.scores_dialog(1))]:
                close_next_dialog()
                show()
                check(f'{name} 对话框可以打开与关闭', True)

            window.preset_items[1, 0].set_active(True)
            window.engine.new(42)
            click(1, 40)
            for i in range(81):
                if not window.engine.cells[i].mine:
                    click(1, i)
            check('双曲复数胜利', bool(window.engine.info.win))
            check('标准难度纪录保存', window.preferences.best(1, 0) is not None)
            snapshot('hyper-win')
            window.sound_item.set_active(False)
            check('声音偏好保存', not window.preferences.data['sound'])
            window.sound_item.set_active(True)
            check('音频播放器可创建', len(window.sound.players) == 6)
            window.sound.decoded.clear()
            for name in window.sound.players:
                window.sound.play(name)
            audio_deadline[0] = time.monotonic()+5
            GLib.timeout_add(100, audio_done)
        except Exception:
            finish(traceback.format_exc())
        return False

    def audio_done():
        try:
            if not window.sound.error and len(window.sound.decoded) < 6 and time.monotonic() < audio_deadline[0]:
                return True
            check('全部 6 段原版 WAV 完整解码到测试输出', window.sound.error is None and len(window.sound.decoded) == 6)
            window.preset_items[0, 0].set_active(True)
            snapshot('ready-to-play')
            finish()
        except Exception:
            finish(traceback.format_exc())
        return False

    GLib.timeout_add(300, run)
