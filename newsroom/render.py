#!/usr/bin/env python3
"""Turn one edition (a JSON file) into the files the Kindle shows.

    python3 newsroom/render.py edition.json

Writes news/headlines.png, news/a1.png ... and news/edition.txt.
It refuses to write anything if the edition breaks a rule, and says which rule.
"""
import json, os, re, sys, datetime
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "news")
W, H, M = 1072, 1448, 80
BODY_BOTTOM = 1290          # article text must end above the source line


def font(style, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", "Caladea-%s.ttf" % style), size)


# ---------- text with *marked* words ----------

def tokens(text):
    """-> list of (word, bold, space_before)"""
    out, bold, cur, space = [], False, "", False
    def flush():
        nonlocal cur, space
        if cur:
            out.append((cur, bold, space)); cur = ""; space = False
    for ch in text:
        if ch == "*":
            flush(); bold = not bold
        elif ch.isspace():
            flush(); space = True
        else:
            cur += ch
    flush()
    if out:
        out[0] = (out[0][0], out[0][1], False)
    return out


def layout(d, text, size, width, base="Regular"):
    reg, bold = font(base, size), font("Bold", size)
    sp = d.textlength(" ", font=reg)
    # glue tokens that have no space between them into unbreakable groups
    groups = []
    for w, b, s in tokens(text):
        f = bold if b else reg
        if s or not groups:
            groups.append([(w, f)])
        else:
            groups[-1].append((w, f))
    lines, x = [[]], 0
    for g in groups:
        gw = sum(d.textlength(w, font=f) for w, f in g)
        add = gw if not lines[-1] else sp + gw
        if x + add > width and lines[-1]:
            lines.append([]); x = 0; add = gw
        lines[-1].append(g); x += add
    return lines, sp


def draw_text(d, x0, y, text, size, width, lead=1.32, fill=0, base="Regular", dry=False):
    lines, sp = layout(d, text, size, width, base)
    for ln in lines:
        x = x0
        for i, g in enumerate(ln):
            if i: x += sp
            for w, f in g:
                if not dry: d.text((x, y), w, font=f, fill=fill)
                x += d.textlength(w, font=f)
        y += int(size * lead)
    return y, len(lines)


# ---------- the rules ----------

def plain(s):
    return re.sub(r"\s+", " ", s.replace("*", "")).strip()


def check(ed):
    errs = []
    def need(cond, msg):
        if not cond: errs.append(msg)
    need(re.fullmatch(r"\d{4}-\d{2}-\d{2}-(am|pm)", ed.get("id", "")), "id must look like 2026-11-16-am")
    need(0 < len(ed.get("date_line", "")) <= 28, "date_line missing or longer than 28 characters")
    arts = ed.get("articles", [])
    need(3 <= len(arts) <= 5, "an edition has 3 to 5 articles (5 unless the news is thin)")
    for n, a in enumerate(arts, 1):
        t = "article %d: " % n
        hl = a.get("headline", "")
        need(10 <= len(hl) <= 62, t + "headline must be 10 to 62 characters, a plain sentence")
        need("*" not in hl and "|" not in hl, t + "no * or | in the headline")
        body = a.get("body", [])
        need(isinstance(body, list) and len(body) == 2, t + "body is exactly two paragraphs")
        text = " ".join(body) if isinstance(body, list) else ""
        need("*" not in text, t + "no * in the body")
        words = len(plain(text).split())
        need(55 <= words <= 110, t + "body has %d words, wanted 55 to 110" % words)
        src = a.get("sources", [])
        need(1 <= len(src) <= 3 and all(0 < len(s) <= 24 for s in src), t + "1 to 3 short source names")
    return errs


# ---------- the pictures ----------

def page_headlines(ed):
    im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((M, 34), "The real world", font=font("Italic", 50), fill=0)
    f = font("Regular", 40); t = ed["date_line"]
    d.text((W - M - d.textlength(t, font=f), 44), t, font=f, fill=90)
    d.line((M, 118, W - M, 118), fill=150, width=2)
    y, rowh = 118, 222
    for i, a in enumerate(ed["articles"]):
        d.text((M, y + 52), str(i + 1), font=font("Bold", 64), fill=150)
        size = 48
        while draw_text(d, 0, 0, a["headline"], size, W - 2 * M - 70, 1.25, dry=True)[1] > 2 and size > 38:
            size -= 2
        _, n = draw_text(d, 0, 0, a["headline"], size, W - 2 * M - 70, 1.25, dry=True)
        top = y + (rowh - n * int(size * 1.25)) // 2
        draw_text(d, M + 70, top, a["headline"], size, W - 2 * M - 70, 1.25)
        y += rowh
        d.line((M, y, W - M, y), fill=190, width=2)
    t = "tap a headline to read it  ·  swipe right for the good side"; f = font("Italic", 34)
    d.text((M, 1370), t, font=f, fill=110)
    return im


def page_article(a, n, total):
    for hsize, bsize in ((66, 44), (60, 44), (60, 42), (56, 40), (52, 38)):
        im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
        d.text((M, 34), "German politics", font=font("Italic", 40), fill=90)
        f = font("Regular", 40); t = "%d of %d" % (n, total)
        d.text((W - M - d.textlength(t, font=f), 34), t, font=f, fill=90)
        d.line((M, 98, W - M, 98), fill=150, width=2)
        y, _ = draw_text(d, M, 136, a["headline"], hsize, W - 2 * M, 1.15, base="Bold")
        y += 36
        y, _ = draw_text(d, M, y, a["body"][0], bsize, W - 2 * M)
        y, _ = draw_text(d, M, y + 26, a["body"][1], bsize, W - 2 * M)
        if y <= BODY_BOTTOM:
            break
    else:
        raise SystemExit("article %d does not fit on the screen even at the smallest size: shorten it" % n)
    src = a["sources"]
    names = src[0] if len(src) == 1 else ", ".join(src[:-1]) + " and " + src[-1]
    d.text((M, 1352), "Written from today's reports by " + names + ".", font=font("Italic", 32), fill=110)
    d.text((M, 1394), "tap to go back  \u00b7  swipe left for the next article", font=font("Italic", 32), fill=110)
    return im


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    ed = json.load(open(sys.argv[1], encoding="utf-8"))
    errs = check(ed)
    if errs:
        print("NOT RENDERED. Fix these and run again:")
        for e in errs: print(" -", e)
        raise SystemExit(1)
    pages = [("headlines.png", page_headlines(ed))]
    total = len(ed["articles"])
    for n, a in enumerate(ed["articles"], 1):
        pages.append(("a%d.png" % n, page_article(a, n, total)))
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        os.remove(os.path.join(OUT, name))
    for name, im in pages:
        im.save(os.path.join(OUT, name), optimize=True)
    with open(os.path.join(OUT, "edition.txt"), "w", encoding="utf-8") as f:
        f.write("id=%s\narticles=%d\nmade=%s\n" % (
            ed["id"], total, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    print("Rendered edition %s: %d articles, files in news/" % (ed["id"], total))


if __name__ == "__main__":
    main()
