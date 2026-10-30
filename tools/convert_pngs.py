"""Convert the heavy PNGs under wp-content/uploads to WebP and repoint every page at them.

    python tools/convert_pngs.py --dry-run   # report only
    python tools/convert_pngs.py             # convert, rewrite references, remove PNGs

Run from anywhere. A PNG is converted when it is at least MIN_BYTES and the WebP comes
out at most MAX_RATIO of its size. Flat graphics go lossless; photos and AI renders go
lossy at QUALITY. Each converted file keeps its folder and stem: foo.png -> foo.webp.

Every visitor-facing reference (src, srcset, href, search index JSON) is rewritten to
the .webp name.

Social scrapers and icon fetchers are the clients most likely to choke on WebP, so a
reference inside an og:image / twitter:image meta tag, a JSON-LD block or a
<link rel="icon"> is left pointing at the PNG, and a PNG that one of those names stays
on disk. Any other converted PNG is deleted and gets a 301 in _redirects, so old links
and cached pages do not 404.

Files are read and written byte-for-byte (utf-8 with surrogateescape, no newline
translation), so pages that carry stray non-UTF-8 bytes are not mangled.
"""

import argparse
import io
import os
import re
import sys
from urllib.parse import unquote

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.join(ROOT, "wp-content", "uploads")

MIN_BYTES = 50 * 1024
MAX_RATIO = 0.75
QUALITY = 82
GRAPHIC_COLORS = 2048  # at most this many distinct colors -> candidate for lossless
LOSSLESS_SLACK = 1.6   # ...and lossless may cost up to this much more than lossy

SKIP_DIRS = {".git", ".claude", "node_modules"}
TEXT_EXT = (".html", ".json", ".js", ".css", ".xml", ".txt", ".md")
REDIRECT_SAFE = re.compile(r"^[A-Za-z0-9._/\-]+$")

# wp-content/uploads/<path>.png as it appears in HTML, or in JSON with escaped slashes.
REF = re.compile(
    r"wp-content(?P<s>\\?/)uploads(?P=s)(?P<path>[^\s\"'()<>]+?)\.png"
    r"(?![\w])(?!\.(?:jpe?g|webp|avif|gif|png)\b)",
    re.I,
)

# Spans whose PNG references are left alone.
PROTECTED = re.compile(
    r"<meta\b[^>]*(?:og:image|twitter:image)[^>]*>"
    r"|<link\b[^>]*rel=\"[^\"]*(?:icon|image_src)[^\"]*\"[^>]*>"
    r"|<script[^>]*ld\+json[^>]*>.*?</script>",
    re.S,
)


def read(path):
    with io.open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def walk_text():
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(TEXT_EXT):
                yield os.path.join(d, f)


def rel_of(m):
    return unquote(m.group("path").replace("\\/", "/"))


def split_protected(text):
    """Yield (segment, is_protected) covering text."""
    pos = 0
    for m in PROTECTED.finditer(text):
        yield text[pos:m.start()], False
        yield m.group(0), True
        pos = m.end()
    yield text[pos:], False


def protected_refs(texts):
    """Lowercased upload paths (no extension) named inside protected spans."""
    out = set()
    for text in texts:
        for seg, prot in split_protected(text):
            if prot:
                out.update(rel_of(m).lower() for m in REF.finditer(seg))
    return out


def encode(src, dst):
    """Write dst as WebP. Returns (lossless?, bytes, size)."""
    im = Image.open(src)
    im.load()
    icc = im.info.get("icc_profile")
    if im.mode in ("P", "PA", "LA", "La") or "transparency" in im.info:
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.mode == "RGBA" and im.getchannel("A").getextrema() == (255, 255):
        im = im.convert("RGB")
    kw = {"icc_profile": icc} if icc else {}
    lossy = io.BytesIO()
    im.save(lossy, "WEBP", quality=QUALITY, method=6, **kw)
    data, lossless = lossy.getvalue(), False
    # A flat graphic (few colors) stays crisp and costs about the same lossless. A photo
    # that was quantized to a palette also has few colors, but lossless is several times
    # the lossy size, so the size check keeps it lossy.
    if im.getcolors(maxcolors=GRAPHIC_COLORS) is not None:
        flat = io.BytesIO()
        im.save(flat, "WEBP", lossless=True, method=6, **kw)
        if flat.tell() <= len(data) * LOSSLESS_SLACK:
            data, lossless = flat.getvalue(), True
    with open(dst, "wb") as f:
        f.write(data)
    return lossless, len(data), im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = list(walk_text())
    texts = {p: read(p) for p in files}
    kept_png = protected_refs(texts.values())

    plan = []  # (rel without ext, ext, png path, png bytes, webp bytes, lossless)
    skipped = []
    for d, _, names in os.walk(UPLOADS):
        for name in sorted(names):
            if not name.lower().endswith(".png"):
                continue
            png = os.path.join(d, name)
            rel = os.path.relpath(png, UPLOADS).replace(os.sep, "/")
            size = os.path.getsize(png)
            webp = png[:-4] + ".webp"
            if size < MIN_BYTES:
                continue
            if not REDIRECT_SAFE.match(rel):
                skipped.append((rel, size, "filename needs escaping in _redirects"))
                continue
            if os.path.exists(webp):
                skipped.append((rel, size, "a .webp with that name already exists"))
                continue
            tmp = webp + ".tmp"
            lossless, out, dims = encode(png, tmp)
            if out > size * MAX_RATIO:
                os.remove(tmp)
                skipped.append((rel, size, "WebP only %d%% of PNG" % (100 * out // size)))
                continue
            with Image.open(tmp) as check:
                if check.size != dims:
                    os.remove(tmp)
                    raise SystemExit("size mismatch on " + rel)
            if args.dry_run:
                os.remove(tmp)
            else:
                os.replace(tmp, webp)
            plan.append((rel[:-4], rel[-4:], png, size, out, lossless))

    for rel, _, _, a, b, ll in plan:
        print("%9d -> %8d  %s  %s" % (a, b, "lossless" if ll else "lossy   ", rel))
    print("%d converted, %.1f MB less per full download" % (len(plan), sum(p[3] - p[4] for p in plan) / 1e6))
    for rel, size, why in skipped:
        print("kept   %9d  %s  (%s)" % (size, rel, why))
    if args.dry_run:
        return

    done = {p[0].lower() for p in plan}

    def sub(m):
        return m.group(0)[:-4] + ".webp" if rel_of(m).lower() in done else m.group(0)

    changed = 0
    for p, text in texts.items():
        new = "".join(seg if prot else REF.sub(sub, seg) for seg, prot in split_protected(text))
        if new != text:
            write(p, new)
            changed += 1
    print("rewrote references in %d files" % changed)

    # A visitor-facing reference that survived is a miss. Do not delete anything then.
    left = []
    for p in files:
        for seg, prot in split_protected(read(p)):
            if not prot:
                left += [(p, m.group(0)) for m in REF.finditer(seg) if rel_of(m).lower() in done]
    if left:
        for p, ref in left[:20]:
            print("STILL REFERENCED", p, ref)
        sys.exit("references remain; PNGs left in place")

    lines = []
    for rel, ext, png, _, _, _ in plan:
        if rel.lower() in kept_png:
            continue
        os.remove(png)
        lines.append("/wp-content/uploads/%s%s  /wp-content/uploads/%s.webp  301" % (rel, ext, rel))
    if lines:
        with io.open(os.path.join(ROOT, "_redirects"), "a", encoding="utf-8", newline="") as f:
            f.write("\n# Heavy PNGs converted to WebP by tools/convert_pngs.py\n")
            f.write("\n".join(lines) + "\n")
    print("removed %d PNGs (+ redirects); %d kept for og:image/JSON-LD" % (len(lines), len(plan) - len(lines)))


if __name__ == "__main__":
    main()
