"""Icons, drawn with PIL: no icon library to install and no font to ship."""

import math
from PIL import Image, ImageColor, ImageDraw



# Drawn here with PIL (already imported for PNG export), so there is no icon library to install
# and no font to ship: one function, one 18x18 design grid, one line weight for every glyph.
def draw_icon(name, fg, px=18):
    """Monochrome icon `name` on a transparent `px` square."""
    S = 4  # supersample: keeps curves readable on a 150% DPI screen
    g = 18 * S
    im = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = tuple(ImageColor.getrgb(fg)[:3])
    w = max(2, int(round(1.7 * S)))

    def line(x0, y0, x1, y1, width=w):
        d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=ink + (255,), width=width)

    def ring(x, y, r, width=w):
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], outline=ink + (255,), width=width)

    def dot(x, y, r):
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=ink + (255,))

    if name in ("zoom_in", "zoom_out"):        # magnifying glass + handle
        ring(7.4, 7.4, 5.2, width=int(w * 0.72))
        line(11.6, 11.6, 15.2, 15.2, int(w * 1.15))
        # The sign is the ONLY thing that tells these two apart, so both arms run the full width
        # of the lens: a short plus would clear the horizontal bar by a couple of pixels only.
        gx = int(w * 1.45)
        d.line([3.1 * S, 7.4 * S, 11.7 * S, 7.4 * S], fill=ink + (255,), width=gx)
        if name == "zoom_in":
            d.line([7.4 * S, 3.1 * S, 7.4 * S, 11.7 * S], fill=ink + (255,), width=gx)
    elif name == "fit":                        # four corner brackets = fit to screen
        for cx, cy, sx, sy in ((3.0, 3.0, 1, 1), (15.0, 3.0, -1, 1),
                               (3.0, 15.0, 1, -1), (15.0, 15.0, -1, -1)):
            line(cx, cy, cx + 5.0 * sx, cy)
            line(cx, cy, cx, cy + 5.0 * sy)
    elif name == "sun":                        # disc + 8 rays
        dot(9, 9, 3.3)
        for k in range(8):
            a = k * math.pi / 4
            line(9 + 5.0 * math.cos(a), 9 + 5.0 * math.sin(a),
                 9 + 7.4 * math.cos(a), 9 + 7.4 * math.sin(a))
    elif name == "moon":                       # crescent = disc with a bite punched out
        mask = Image.new("L", (g, g), 0)       # L-mode fill=0 genuinely erases (RGBA may blend)
        md = ImageDraw.Draw(mask)
        md.ellipse([2.8 * S, 2.8 * S, 15.2 * S, 15.2 * S], fill=255)
        md.ellipse([7.8 * S, 1.0 * S, 17.4 * S, 10.6 * S], fill=0)
        im.paste(ink + (255,), (0, 0), mask)
    elif name == "save":                       # floppy disk
        d.rectangle([3.0 * S, 3.0 * S, 15.0 * S, 15.0 * S], outline=ink + (255,), width=w)
        d.rectangle([5.8 * S, 3.0 * S, 12.2 * S, 7.6 * S], fill=ink + (255,))
        d.rectangle([10.0 * S, 10.2 * S, 13.4 * S, 14.0 * S], fill=ink + (255,))
    elif name == "open":                       # folder with a tab
        d.polygon([(3.0 * S, 4.8 * S), (6.9 * S, 4.8 * S), (8.4 * S, 6.9 * S),
                   (15.0 * S, 6.9 * S), (15.0 * S, 14.4 * S), (3.0 * S, 14.4 * S)],
                  outline=ink + (255,), width=w)
    elif name == "image":                      # picture frame with a mountain and a sun
        d.rounded_rectangle([3.0 * S, 3.8 * S, 15.0 * S, 14.2 * S], radius=int(1.5 * S),
                            outline=ink + (255,), width=w)
        dot(6.4, 7.0, 1.3)
        d.line([(4.2 * S, 12.6 * S), (7.6 * S, 9.6 * S), (10.0 * S, 11.7 * S),
                (13.8 * S, 8.7 * S)], fill=ink + (255,), width=int(w * 0.8), joint="curve")
    elif name == "help":                       # a bold question mark - no badge ring to crowd it
        d.arc([(9 - 4.6) * S, (7.5 - 4.6) * S, (9 + 4.6) * S, (7.5 + 4.6) * S],
              start=150, end=30, fill=ink + (255,), width=w)
        line(12.9, 9.9, 9.8, 12.8, int(w * 1.1))
        dot(9.4, 15.3, 1.2)
    elif name == "panel_min":                  # a box with a heavy floor - collapse to a strip
        d.rectangle([3.6 * S, 3.6 * S, 14.4 * S, 14.4 * S], outline=ink + (255,), width=w)
        line(3.2, 12.2, 14.8, 12.2, int(w * 1.3))
    elif name == "panel_max":                  # four corner brackets - take the whole area
        for x0, y0, dx, dy in ((3.6, 3.6, 1, 1), (14.4, 3.6, -1, 1),
                               (3.6, 14.4, 1, -1), (14.4, 14.4, -1, -1)):
            line(x0, y0, x0 + 4.2 * dx, y0, int(w * 1.3))
            line(x0, y0, x0, y0 + 4.2 * dy, int(w * 1.3))
    elif name == "error":                      # circled cross - the "this did not work" badge
        ring(9, 9, 6.4)
        line(6.4, 6.4, 11.6, 11.6, int(w * 1.2))
        line(11.6, 6.4, 6.4, 11.6, int(w * 1.2))
    elif name == "warn":                       # triangle with a bar and a dot
        d.polygon([(9 * S, 2.6 * S), (16.4 * S, 15.2 * S), (1.6 * S, 15.2 * S)],
                  outline=ink + (255,), width=w)
        line(9, 7.6, 9, 11.2, int(w * 1.2))
        dot(9, 13.6, 1.0)
    elif name == "ok":                         # circled tick
        ring(9, 9, 6.4)
        line(5.9, 9.3, 8.3, 11.8, int(w * 1.2))
        line(8.3, 11.8, 12.4, 6.7, int(w * 1.2))
    else:
        raise ValueError("no icon named %r" % name)
    return im.resize((px, px), Image.BILINEAR)  # bilinear: Lanczos rings onto the transparent edge
