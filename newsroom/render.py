#!/usr/bin/env python3
"""Turn one edition (a JSON file) into the files the Kindle shows.

    python3 newsroom/render.py edition.json

Writes news/headlines.png, news/a1.png ..., news/quiz.txt, news/edition.txt
and adds the new quiz words to newsroom/words-used.txt.
It refuses to write anything if the edition breaks a rule, and says which rule.
"""
import json, os, re, sys, datetime
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "news")
USED = os.path.join(HERE, "words-used.txt")
W, H, M = 1072, 1448, 80
BODY_BOTTOM = 1095          # article text must end above the quiz box


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


def smiley(d, cx, cy, r, w=5):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=w)
    e = r * 0.13
    for sx in (-0.36, 0.36):
        d.ellipse((cx + sx * r - e, cy - 0.3 * r - e, cx + sx * r + e, cy - 0.3 * r + e), fill=0)
    d.arc((cx - 0.55 * r, cy - 0.5 * r, cx + 0.55 * r, cy + 0.6 * r), 25, 155, fill=0, width=w)


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
    used = set()
    if os.path.exists(USED):
        used = {l.strip().lower() for l in open(USED, encoding="utf-8") if l.strip() and not l.startswith("#")}
    seen = set()
    for n, a in enumerate(arts, 1):
        t = "article %d: " % n
        hl = a.get("headline", "")
        need(10 <= len(hl) <= 62, t + "headline must be 10 to 62 characters, a plain sentence")
        need("*" not in hl and "|" not in hl, t + "no * or | in the headline")
        body = a.get("body", [])
        need(len(body) == 2, t + "body is exactly two paragraphs")
        text = " ".join(body)
        words = len(plain(text).split())
        need(55 <= words <= 95, t + "body has %d words, wanted 55 to 95" % words)
        need(text.count("*") % 2 == 0, t + "unbalanced * in body")
        marked = [m.strip() for m in re.findall(r"\*([^*]+)\*", text)]
        need(len(marked) == 5, t + "exactly 5 marked words or phrases, found %d" % len(marked))
        src = a.get("sources", [])
        need(1 <= len(src) <= 3 and all(0 < len(s) <= 24 for s in src), t + "1 to 3 short source names")
        quiz = a.get("quiz", [])
        need(len(quiz) == 5, t + "exactly 5 quiz items")
        sentences = [plain(s) for s in re.split(r"(?<=[.!?])\s+", plain(text))]
        qmarked = []
        for k, q in enumerate(quiz, 1):
            u = t + "quiz %d: " % k
            for key in ("marked", "word", "right", "wrong", "sentence", "explain"):
                v = q.get(key, "")
                need(isinstance(v, str) and v.strip(), u + key + " is missing")
                need("|" not in v and "\n" not in v and "*" not in v, u + "no |, * or line break in " + key)
            need(q.get("marked", "") in marked, u + "'marked' must be one of the marked runs in the body, letter for letter")
            qmarked.append(q.get("marked", ""))
            need(plain(q.get("sentence", "")) in sentences, u + "'sentence' must be one whole sentence of the body, unchanged")
            need(q.get("marked", "\0") in q.get("sentence", ""), u + "the sentence must contain the marked word")
            need(q.get("right", "").lower() != q.get("wrong", "").lower(), u + "right and wrong are the same")
            need(len(q.get("right", "")) <= 30 and len(q.get("wrong", "")) <= 30, u + "answers are at most 30 characters")
            need(len(q.get("word", "")) <= 26, u + "word is at most 26 characters")
            need(len(q.get("sentence", "")) <= 170, u + "sentence is at most 170 characters")
            need(len(q.get("explain", "")) <= 170, u + "explanation is at most 170 characters")
            w = q.get("word", "").strip().lower()
            need(w not in used, u + "'%s' was used in an earlier edition, pick another word" % w)
            need(w not in seen, u + "'%s' appears twice in this edition" % w)
            seen.add(w)
        need(sorted(qmarked) == sorted(marked), t + "each marked run needs exactly one quiz item")
    return errs, seen


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
    # y 1240..1340 stays empty: the Kindle writes the score line there
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
    by = 1130
    d.rounded_rectangle((M, by, W - M, by + 180), radius=18, outline=0, width=4)
    smiley(d, M + 80, by + 90, 44)
    d.text((M + 160, by + 34), "Quiz", font=font("Bold", 50), fill=0)
    d.text((M + 160, by + 100), "5 words from this page. Tap here to play.", font=font("Regular", 38), fill=0)
    src = a["sources"]
    names = src[0] if len(src) == 1 else ", ".join(src[:-1]) + " and " + src[-1]
    d.text((M, 1352), "Written from today's reports by " + names + ".", font=font("Italic", 32), fill=110)
    d.text((M, 1394), "tap anywhere else to go back", font=font("Italic", 32), fill=110)
    return im


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    ed = json.load(open(sys.argv[1], encoding="utf-8"))
    errs, new_words = check(ed)
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
    with open(os.path.join(OUT, "quiz.txt"), "w", encoding="utf-8") as f:
        for n, a in enumerate(ed["articles"], 1):
            for q in a["quiz"]:
                f.write("|".join(["a%d" % n, q["word"].strip(), q["right"].strip(), q["wrong"].strip(),
                                  plain(q["sentence"]), plain(q["explain"])]) + "\n")
    with open(os.path.join(OUT, "edition.txt"), "w", encoding="utf-8") as f:
        f.write("id=%s\narticles=%d\nmade=%s\n" % (
            ed["id"], total, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    with open(USED, "a", encoding="utf-8") as f:
        for w in sorted(new_words): f.write(w + "\n")
    print("Rendered edition %s: %d articles, %d quiz words, files in news/" % (ed["id"], total, len(new_words)))


if __name__ == "__main__":
    main()
