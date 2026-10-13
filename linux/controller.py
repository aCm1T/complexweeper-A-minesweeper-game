"""Mouse gestures, kept separate from GTK so cancelled drags can be tested."""


class Controller:
    def __init__(self, engine, renderer, changed, reset, clock, zoom=2):
        self.engine, self.renderer = engine, renderer
        self.changed, self.reset, self.clock, self.zoom = changed, reset, clock, zoom
        self.clear()

    def clear(self):
        self.buttons = set()
        self.press = self.chord = None
        self.chording = False
        self.face_armed = self.face_down = False

    def cell_at(self, x, y):
        L, s = self.renderer.layout(self.zoom), self.engine.info
        if L.bx <= x < L.bx+s.w*L.cell and L.by <= y < L.by+s.h*L.cell:
            return int((y-L.by)//L.cell)*s.w + int((x-L.bx)//L.cell)
        return None

    def in_face(self, x, y):
        L = self.renderer.layout(self.zoom)
        return L.fx <= x < L.fx+24*self.zoom and L.fy <= y < L.fy+24*self.zoom

    def down(self, button, x, y):
        if button not in (1, 2, 3):
            return
        self.buttons.add(button)
        c = self.cell_at(x, y)
        if button == 1:
            self.face_armed = self.in_face(x, y)
            self.face_down = self.face_armed
        if button == 2 or {1, 3}.issubset(self.buttons):
            self.chording = True
            self.chord, self.press = c, None
        elif button == 1:
            self.press = c if c is not None and not self.engine.info.over and not self.engine.cells[c].open else None
        elif button == 3 and c is not None:
            if self.engine.action('flag', c):
                self.changed('flag')

    def move(self, x, y):
        c = self.cell_at(x, y)
        if self.chording:
            self.chord = c
        elif 1 in self.buttons and not self.face_armed:
            self.press = c if c is not None and not self.engine.info.over and not self.engine.cells[c].open else None
        if self.face_armed:
            self.face_down = self.in_face(x, y)

    def up(self, button, x, y):
        if button not in self.buttons:
            return
        cell, held, chord = self.cell_at(x, y), self.press, self.chord
        was_face, chording = self.face_armed, self.chording
        self.clear()
        if button == 1 and was_face and self.in_face(x, y):
            self.reset()
        elif chording:
            if chord is not None and chord == cell and self.engine.action('expand', chord, self.clock()):
                self.changed('expand')
        elif button == 1 and held is not None and held == cell:
            if self.engine.action('reveal', held, self.clock()):
                self.changed('reveal')
