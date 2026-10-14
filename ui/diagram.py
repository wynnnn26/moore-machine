"""The machine diagram: view control (zoom, pan, drag, export) and drawing."""

import math
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

from PIL import ImageGrab


class DiagramMixin:
    """measure / radius / draw / highlight, plus the view around them."""

    def zfont(self):
        """Bold font scaled to the current zoom, cached per size."""
        size = max(8, int(round(12 * self.zoom)))
        if size not in self._fonts:
            self._fonts[size] = tkfont.Font(size=size, weight="bold")
        return self._fonts[size]

    def set_zoom(self, z, follow=True):
        self.zoom = max(0.35, min(3.0, round(z, 3)))
        self.zoomlbl.configure(text=f"{int(round(self.zoom * 100))}%")
        # a wheel zoom must not also re-centre on the current state - that is the jump the
        # spec asks to avoid. follow=False leaves the view exactly where the caller put it.
        self._no_follow = not follow
        try:
            self.draw()
        finally:
            self._no_follow = False

    def zoom_in(self, *_):
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self, *_):
        self.set_zoom(self.zoom / 1.25)

    def zoom_at(self, factor, e=None):
        """Zoom by `factor`, keeping whatever is under the pointer in the same screen spot.
        The picture is laid out about the centre of the scroll region, so the anchor moves
        with that centre and scales with the zoom - close enough that the diagram does not
        slide out from under the cursor."""
        try:
            ax, ay = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        except (AttributeError, tk.TclError):
            return self.set_zoom(self.zoom * factor)
        z0, (W0, H0) = self.zoom, self._diag
        self.set_zoom(self.zoom * factor, follow=False)
        if self.zoom == z0 or not W0 or not H0:
            return
        W, H = self._diag
        k = self.zoom / z0   # how far the content moved away from the centre
        self._moveto((W / 2 + (ax - W0 / 2) * k - e.x) / max(W, 1),
                     (H / 2 + (ay - H0 / 2) * k - e.y) / max(H, 1))

    def _moveto(self, fx, fy):
        """Scroll so the world point fx*W lands at the left edge, clamped to the region."""
        self.cv.xview_moveto(max(0.0, min(1.0, fx)))
        self.cv.yview_moveto(max(0.0, min(1.0, fy)))

    def on_wheel(self, e):
        """Ctrl + wheel zooms at the pointer, Shift + wheel pans sideways, plain wheel pans up
        and down. Bound on the diagram canvas only, so a wheel over a table or the sidebar
        scrolls that widget and never zooms the picture."""
        step = -3 if (getattr(e, "delta", 0) or 0) > 0 else 3
        if e.state & 0x0004:                       # Control -> zoom in towards the cursor
            self.zoom_at(1.2 if step < 0 else 1 / 1.2, e)
        elif e.state & 0x0001:                     # Shift -> sideways
            self.cv.xview_scroll(step, "units")
        else:
            self.cv.yview_scroll(step, "units")
        return "break"

    def fit_diagram(self, *_):
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        W, H = self._diag
        if w > 50 and h > 50 and W and H:
            self.set_zoom(min(1.0, self.zoom * min(w / W, h / H)))  # fit: never zoom past 100%

    def export_png(self, *_):
        if not self.states:
            return self.err("⚠️ Nothing to export\nThe diagram is empty - it has no states to draw.\n"
                            "Fix: add a state first, or press 'Load Example' to load a working machine.",
                            "Could not export")
        path = filedialog.asksaveasfilename(defaultextension=".png", initialfile="moore-machine.png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        keep = self.zoom  # fit so the whole machine lands in frame, then put the zoom back
        try:
            self.fit_diagram()
            # ponytail: grab() copies whatever is on screen, so lift first - but this still loses
            # to another window covering us; capture the canvas offscreen (Win32 PrintWindow) if it bites
            self.root.lift()
            self.root.focus_force()
            self.root.update()
            time.sleep(0.1)
            x, y = self.cv.winfo_rootx(), self.cv.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + self.cv.winfo_width(), y + self.cv.winfo_height())).save(path)
        except (OSError, ValueError) as e:
            self.set_zoom(keep)
            self.msg.set("")  # do not leave the last "Saved the diagram to ..." banner standing
            return self.err(f"⚠️ Could not export\n{e}\n"
                            "Fix: choose a folder you can write to, such as Documents or Downloads.",
                            "Could not export")
        self.set_zoom(keep)
        self.msg.set(f"Saved the diagram to {path}")

    def drag_start(self, e):
        self.dragging, self._pan = None, None
        for item in self.cv.find_withtag("current"):  # topmost state circle / label under the cursor
            for t in self.cv.gettags(item):
                if t.startswith("s:"):
                    self.dragging = t[2:]
                    # remember where the grab happened so the circle does not jump to the cursor
                    self._press = (self.cv.canvasx(e.x), self.cv.canvasy(e.y))
                    self._base = self.off.get(self.dragging, (0, 0))
                    self.cv.configure(cursor="fleur")
                    return
        # no state under the pointer: drag the view instead, so a big machine can be panned
        self._pan = (e.x, e.y, self.cv.xview()[0], self.cv.yview()[0])
        self.cv.configure(cursor="fleur")

    def drag_move(self, e):
        if self.dragging:
            px, py = self._press
            bx, by = self._base
            self.off[self.dragging] = (bx + self.cv.canvasx(e.x) - px, by + self.cv.canvasy(e.y) - py)
            self.draw()
        elif self._pan:
            x0, y0, fx, fy = self._pan
            W, H = self._diag
            self._moveto(fx - (e.x - x0) / max(W, 1), fy - (e.y - y0) / max(H, 1))

    def drag_end(self, _):
        if self.dragging or self._pan:
            self.dragging, self._pan = None, None
            self.cv.configure(cursor="")

    # ----- diagram -----
    def measure(self, text):
        """Pixel width of `text` in the state font.

        Asking Tk is a round-trip, and draw() asks for every state on every repaint - on a big
        machine that was most of what a repaint cost. The answers cannot change unless the font
        does, so they are remembered by string."""
        got = self._meas.get(text)
        if got is None:
            if len(self._meas) > 400:  # bounded: a machine only ever has a handful of names
                self._meas.clear()
            got = self._meas[text] = self.font.measure(text)
        return got

    def radius(self, s):
        """Circle radius that fits the state's name and output."""
        w = max(self.measure(s), self.measure(self.states[s]))
        return max(28, math.hypot(w / 2, 19) + 5)

    def draw(self):
        c = self.cv
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        z, fz, dk = self.zoom, self.zfont(), self.dark()
        ink = "#d0d0d0" if dk else "black"  # outlines and ordinary arrows
        paper = "#141414" if dk else "white"  # canvas colour: label boxes blend into it
        green = "#66bb6a" if dk else "#2e7d32"
        c.configure(bg=paper)
        if not self.states:
            c.configure(scrollregion=(0, 0, w, h))
            self._diag = (max(w, 1), max(h, 1))
            c.create_text(w / 2, h / 2, font=fz, fill="#9aa7b3" if dk else "gray",
                          text="No states yet - Load the example, or add your first state.")
            return
        n = len(self.states)
        rs = {s: self.radius(s) * z for s in self.states}  # circles scale with the zoom
        rm = max(rs.values())

        def reach(s):
            """How far outside its centre this state's own drawing can stick out.

            A self-loop and the label beside it reach about 2.75r; the start state's arrow
            reaches r + 70z with a "start" box about 28px wide past it. Everything has to land
            inside the scroll region - outside it the scrollbars cannot reach it, the canvas
            clips it, and the arrow reads as detached from the state it points at."""
            r = rs[s]
            far = max(3 * r + 30 * z, 2.75 * r + 28)
            return max(far, r + 70 * z + 28) if s == self.initial else far

        margin = max(3 * rm + 30 * z,          # self-loop plus its label
                     reach(self.initial) if self.initial in rs else 0)   # ...and the start arrow
        need = (2 * rm + 90 * z) / (2 * math.sin(math.pi / n)) if n > 1 else 0  # keeps neighbours apart
        # compact when the machine is small, filling the canvas when it is big (never below `need`)
        rx = max(need, min(w / 2 - margin, need * 1.6)) if n > 1 else 0
        ry = max(need, min(h / 2 - margin, need * 1.6)) if n > 1 else 0
        W, H = max(w, 2 * (rx + margin)), max(h, 2 * (ry + margin))
        # A state dragged sideways has to stay INSIDE the scroll region: outside it the scrollbars
        # cannot reach the circle and Fit Diagram cannot get it back. pos = centre + rx*cos(a) + drag,
        # so the worst case on each axis is |rx*cos(a) + drag| plus that state's own reach.
        if self.off:
            ang = [math.pi + 2 * math.pi * i / n for i in range(n)]
            W = max(W, 2 * max(abs(rx * math.cos(a) + self.off.get(s, (0, 0))[0]) + reach(s)
                               for a, s in zip(ang, self.states)))
            H = max(H, 2 * max(abs(ry * math.sin(a) + self.off.get(s, (0, 0))[1]) + reach(s)
                               for a, s in zip(ang, self.states)))
        cx, cy = W / 2, H / 2
        c.configure(scrollregion=(0, 0, W, H))  # bigger than the window -> scrollbars work
        self._diag = (W, H)  # remembered so Fit Diagram knows the natural size
        self.layout = {s: (cx + rx * math.cos(math.pi + 2 * math.pi * i / n),
                           cy + ry * math.sin(math.pi + 2 * math.pi * i / n)) for i, s in enumerate(self.states)}
        pos = {}  # layout position + wherever the user has dragged the state
        for s, (lx, ly) in self.layout.items():
            dx, dy = self.off.get(s, (0, 0))
            pos[s] = (lx + dx, ly + dy)

        def outward(x, y):  # unit vector pointing away from the diagram centre
            L = math.hypot(x - cx, y - cy)
            return ((x - cx) / L, (y - cy) / L) if L > 1 else (0, -1)

        def toward(p, q, dist):  # point `dist` px from p in the direction of q
            L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1
            return p[0] + dist * (q[0] - p[0]) / L, p[1] + dist * (q[1] - p[1]) / L

        def tag(x, y, text, bg, fg, extra=""):  # label on a small box so it stays readable over lines
            kw = {"tags": (extra,)} if extra else {}
            t = c.create_text(x, y, text=text, font=fz, fill=fg, **kw)
            b = c.bbox(t)
            c.create_rectangle(b[0] - 2, b[1], b[2] + 2, b[3], fill=bg, outline="", **kw)
            c.tag_raise(t)

        ARROW = (max(6, 13 * z), max(7, 15 * z), max(2, 5 * z))
        act = self.active
        edges = {}  # parallel edges share one arrow and one label: q0 -"0, 1"-> q1
        for (s, a), d in self.trans.items():
            edges.setdefault((s, d), []).append(a)
        self._edge_tag = {}  # so highlight() can find one arrow again without redrawing them all
        for i, ((s, d), syms) in enumerate(edges.items()):
            etag = "e%d" % i
            self._edge_tag[(s, d)] = etag
            on = bool(act) and (s, d) == (act[0], act[2])  # the transition being processed
            col, bg = ("#e65100", "#ffe0b2") if on else (ink, paper)
            wd = max(1, (4 if on else 2) * z)
            lab = "#e65100" if on else ("#ef5350" if dk else "#c62828")
            label = ", ".join(sorted(syms))
            (x1, y1), (x2, y2) = pos[s], pos[d]
            if s == d:  # self-loop, drawn outside the circle
                r = rs[s]
                ux, uy = outward(x1, y1)
                if s == self.initial and ux < 0:
                    # The start arrow always comes straight in from the left, so a loop on that
                    # side would draw through it. Turn the loop a quarter away, staying on the
                    # vertical side the state was already leaning towards.
                    ux, uy = 0.0, -1.0 if uy <= 0 else 1.0
                pts = []
                for k, t in ((-.75, 1), (-.5, 2.3), (.5, 2.3), (.75, 1)):
                    vx, vy = ux * math.cos(k) - uy * math.sin(k), ux * math.sin(k) + uy * math.cos(k)
                    pts += [x1 + vx * r * t, y1 + vy * r * t]
                c.create_line(*pts, smooth=True, arrow="last", arrowshape=ARROW, width=wd,
                              fill=col, tags=(etag,))
                tag(x1 + ux * r * 2.75, y1 + uy * r * 2.75, label, bg, lab, etag)
            else:
                L = math.hypot(x2 - x1, y2 - y1) or 1
                nx, ny = -(y2 - y1) / L, (x2 - x1) / L
                bend = max(70 * z, .3 * L) if (d, s) in edges else 0  # arrows in both directions curve apart
                q = ((x1 + x2) / 2 + nx * bend, (y1 + y2) / 2 + ny * bend)
                # ponytail: straight arrows may cross a third state in dense layouts; route around it if that bites
                a0, a1 = toward((x1, y1), q, rs[s]), toward((x2, y2), q, rs[d])
                c.create_line(*a0, *q, *a1, smooth=True, arrow="last", arrowshape=ARROW, width=wd,
                              fill=col, tags=(etag,))
                mx, my = .25 * a0[0] + .5 * q[0] + .25 * a1[0], .25 * a0[1] + .5 * q[1] + .25 * a1[1]
                tag(mx + nx * 14 * z, my + ny * 14 * z, label, bg, lab, etag)

        prev = act[0] if act else None
        for s, (x, y) in pos.items():
            r, now = rs[s], s == self.cur
            st = ("s:" + s,)  # tag so the whole state can be dragged
            if s == self.initial:  # prominent start ring, outside the circle
                c.create_oval(x - r - 7 * z, y - r - 7 * z, x + r + 7 * z, y + r + 7 * z,
                              outline=green, width=max(2, 3 * z), dash=(6, 4), tags=st + ("ring",))
            # "circ" separates the circle itself from the ring and the text, so highlight()
            # can re-colour it in place instead of repainting the whole picture.
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill="#ffd54f" if now else "#e3f2fd" if s == prev else "white",
                          outline="#e65100" if now else ink, width=4 if now else 2,
                          tags=st + ("circ",))
            c.create_line(x - r + 6 * z, y, x + r - 6 * z, y, fill="gray", tags=st)
            c.create_text(x, y - 9 * z, text=s, font=fz, tags=st)
            c.create_text(x, y + 10 * z, text=self.states[s], font=fz, fill="#1565c0", tags=st)
        # The start arrow is drawn LAST: it is the one thing a beginner looks for, and drawing
        # it inside the state loop let a state added later bury the arrow and its "start" label.
        if self.initial in pos:
            x, y = pos[self.initial]
            r = rs[self.initial]
            # Always the same arrow in the same place: straight in from the left, tip on the rim,
            # label at the tail. It used to be aimed along the state's bearing around the diagram
            # centre, so dragging a state swung it round to another side of the circle and it
            # stopped reading as "this is where it starts".
            c.create_line(x - r - 55 * z, y, x - r, y,
                          arrow="last", arrowshape=(max(8, 15 * z), max(9, 17 * z), max(3, 6 * z)),
                          width=max(2, 3 * z), fill=green)
            tag(x - r - 70 * z, y, "start", paper, green)
        if self.cur in pos and self.rows and self.dragging is None and not self._no_follow:
            # follow the current state when the diagram scrolls (not while the user is dragging)
            c.xview_moveto(max(0, pos[self.cur][0] - w / 2) / W)
            c.yview_moveto(max(0, pos[self.cur][1] - h / 2) / H)

    def highlight(self, prev_cur=None, prev_act=None):
        """Re-colour the three things a step or a reset actually changes - the current state,
        the state the active arrow came from, and that arrow - and leave the rest alone.

        draw() repaints every circle and label on the canvas. That is right when the machine
        itself has changed, but far too expensive to pay once per animation frame: a repaint of
        a 100-state machine cost about 150 ms, so a Run could not keep up with itself."""
        c, dk, z = self.cv, self.dark(), self.zoom
        ink = "#d0d0d0" if dk else "black"
        paper = "#141414" if dk else "white"
        orange, back = "#e65100", "#e3f2fd"

        def circle(s, fill, width=2, outline=None):
            if s is None or s not in self.states:
                return
            for i in c.find_withtag("s:" + s):
                if "circ" in c.gettags(i):  # the circle itself, never the start ring
                    c.itemconfig(i, fill=fill, width=width,
                                 outline=ink if outline is None else outline)

        def edge(e, on):
            t = self._edge_tag.get(e)
            if not t:
                return
            lab = orange if on else ("#ef5350" if dk else "#c62828")
            for i in c.find_withtag(t):
                kind = c.type(i)
                if kind == "line":
                    c.itemconfig(i, fill=orange if on else ink, width=max(1, (4 if on else 2) * z))
                elif kind == "text":
                    c.itemconfig(i, fill=lab)
                elif kind == "rectangle":
                    c.itemconfig(i, fill="#ffe0b2" if on else paper)

        def as_edge(a):  # an active tuple (from, symbol, to) as the edge that was drawn for it
            return (a[0], a[2]) if a else None

        circle(prev_cur, "white")  # take the previous step off the picture...
        if prev_act:
            circle(prev_act[0], "white")
            edge(as_edge(prev_act), False)
        # ...then put this one on. Being the arrow's source never outranks being current, which
        # is the same order draw() uses when it picks a fill.
        cur = self.cur
        circle(cur, "#ffd54f", 4, orange)
        if self.active:
            src = self.active[0]
            circle(src, "#ffd54f" if src == cur else back, 4 if src == cur else 2,
                   orange if src == cur else None)
            edge(as_edge(self.active), True)
        # keep following the current state while a run plays, exactly as draw() does
        if cur in self.layout and self.rows and self.dragging is None and not self._no_follow:
            x, y = self.layout[cur]
            dx, dy = self.off.get(cur, (0, 0))
            W, H = self._diag
            c.xview_moveto(max(0, x + dx - c.winfo_width() / 2) / max(W, 1))
            c.yview_moveto(max(0, y + dy - c.winfo_height() / 2) / max(H, 1))
