"""Recompress oversized JPEGs under wp-content/uploads, in place.

    python tools/recompress_jpegs.py --dry-run   # report only
    python tools/recompress_jpegs.py             # rewrite the files

A JPEG at least MIN_BYTES is re-encoded at QUALITY (progressive, optimized Huffman
tables) and kept only if that saves at least MIN_SAVING. Name and pixel size do not
change, so no page needs editing and the width/height attributes stay correct. ICC
profile and EXIF are carried over, orientation included.
"""

import argparse
import io
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.join(ROOT, "wp-content", "uploads")

MIN_BYTES = 300 * 1024
QUALITY = 82
MIN_SAVING = 0.25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    done = kept = 0
    saved = 0
    for d, _, names in os.walk(UPLOADS):
        for name in sorted(names):
            if not name.lower().endswith((".jpg", ".jpeg")):
                continue
            path = os.path.join(d, name)
            size = os.path.getsize(path)
            if size < MIN_BYTES:
                continue
            with Image.open(path) as im:
                if im.format != "JPEG":
                    continue
                im.load()
                kw = {}
                for key in ("icc_profile", "exif"):
                    if im.info.get(key):
                        kw[key] = im.info[key]
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True, **kw)
                dims = im.size
            out = buf.getvalue()
            rel = os.path.relpath(path, UPLOADS).replace(os.sep, "/")
            if len(out) > size * (1 - MIN_SAVING):
                kept += 1
                continue
            with Image.open(io.BytesIO(out)) as check:
                if check.size != dims:
                    raise SystemExit("size mismatch on " + rel)
            print("%9d -> %8d  %s" % (size, len(out), rel))
            done += 1
            saved += size - len(out)
            if not args.dry_run:
                with open(path, "wb") as f:
                    f.write(out)
    print("%d recompressed, %.1f MB saved; %d left alone (already small enough)" % (done, saved / 1e6, kept))


if __name__ == "__main__":
    main()
