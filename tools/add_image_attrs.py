"""Give every local <img> its intrinsic size and lazy loading.

    python tools/add_image_attrs.py            # rewrite pages in place
    python tools/add_image_attrs.py --dry-run  # just count

width/height come from the image file itself, so the browser reserves the box before
the file arrives (no layout shift). The theme sets img{height:auto;max-width:100%}, so
the attributes only supply the aspect ratio.

loading="lazy" decoding="async" goes on every image except the ones likely to be on
screen at load: the header logo, and the first EAGER_LISTING cards on a post listing
(first EAGER_PAGE images elsewhere). The very first card also gets fetchpriority="high"
as the probable LCP image. Attributes that are already present are never changed.

Safe to re-run. generate_paginated_pages.py calls process_html() on each page it writes,
so new posts get the same treatment.

Files are read and written byte-for-byte (utf-8 with surrogateescape, no newline
translation), so pages that carry stray non-UTF-8 bytes are not mangled.
"""

import argparse
import html
import io
import os
import posixpath
import re
from urllib.parse import unquote

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".claude", "node_modules", "tools", "assets"}

EAGER_LISTING = 3
EAGER_PAGE = 1

IMG = re.compile(r"<img\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>", re.S)
ATTR = re.compile(r"""\s([^\s=/>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?""")
TRAIL = re.compile(r"\s*/?>\Z")
ORIGIN = re.compile(r"^https?://(?:www\.)?thingsabove\.us", re.I)

_dims = {}


def read(path):
    with io.open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def local_file(src, page_rel, base_root):
    """Map an <img src> to a file under ROOT, or None if it is remote or missing."""
    src = html.unescape(src).strip()
    if src.startswith(("data:", "//")) or src == "#":
        return None
    src = ORIGIN.sub("", src)
    if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
        return None
    src = unquote(re.split(r"[?#]", src)[0])
    if not src:
        return None
    if src.startswith("/"):
        rel = src.lstrip("/")
    elif base_root:
        rel = posixpath.normpath(src)
    else:
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(page_rel), src))
    if rel.startswith(".."):
        return None
    path = os.path.join(ROOT, *rel.split("/"))
    return path if os.path.isfile(path) else None


def dimensions(path):
    if path not in _dims:
        try:
            with Image.open(path) as im:
                _dims[path] = im.size
        except Exception:
            _dims[path] = None
    return _dims[path]


def fix_tag(tag, page_rel, base_root, eager, first):
    attrs = {}
    for m in ATTR.finditer(tag[len("<img"):]):
        attrs[m.group(1).lower()] = m.group(2)
    if "src" not in attrs:
        return tag
    add = []
    if "width" not in attrs and "height" not in attrs:
        path = local_file(attrs["src"].strip("\"'"), page_rel, base_root)
        size = dimensions(path) if path else None
        if size and size[0] > 0 and size[1] > 0:
            add += ['width="%d"' % size[0], 'height="%d"' % size[1]]
    if not eager and "loading" not in attrs:
        add.append('loading="lazy"')
        if "decoding" not in attrs:
            add.append('decoding="async"')
    if first and "fetchpriority" not in attrs:
        add.append('fetchpriority="high"')
    if not add:
        return tag

    trail = TRAIL.search(tag).group(0)
    body = tag[: len(tag) - len(trail)]
    if "\n" in tag:
        indent = re.search(r"\n([ \t]*)\S", tag).group(1)
        sep = "\n" + indent
    else:
        sep = " "
    return body + "".join(sep + a for a in add) + trail


def process_html(text, page_rel):
    """page_rel is the page's path under ROOT with forward slashes."""
    if "/embed/" in "/" + page_rel:
        return text
    base_root = re.search(r'<base\s+href="/"', text) is not None
    listing = 'class="paginated_content"' in text
    limit = EAGER_LISTING if listing else EAGER_PAGE
    content_at = text.find('id="main-content"')

    out, pos, n = [], 0, 0
    for m in IMG.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        if content_at != -1 and m.start() < content_at:
            out.append(m.group(0))  # header logo
            continue
        eager = n < limit
        out.append(fix_tag(m.group(0), page_rel, base_root, eager, listing and n == 0))
        n += 1
    out.append(text[pos:])
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = total = 0
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(d, f)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            text = read(path)
            new = process_html(text, rel)
            total += 1
            if new != text:
                changed += 1
                if not args.dry_run:
                    write(path, new)
    print("%d of %d pages %s" % (changed, total, "would change" if args.dry_run else "updated"))


if __name__ == "__main__":
    main()
