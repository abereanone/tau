"""Build search/index.json: every post's title, date, author, categories, image and text.

    python tools/build_search_index.py

Run from the repo root after adding, removing or editing a post. The search page
(search/index.html + assets/search.js) loads this file and searches it in the browser,
so every post is searchable immediately, with no server and no outside service.

A post is any top-level folder whose index.html has the single-post body class.
Each entry is [url, title, iso_date, author, categories, image, text].
"""

import datetime
import html
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "search", "index.json")
SKIP = {"wp-content", "wp-includes", "assets", "page", "author", "category", "tag", "search", "tools", ".git", ".claude"}


def block(s, opener):
    """(start, end) of the balanced element whose opening tag begins with `opener`."""
    i = s.find(opener)
    if i < 0:
        return None
    tag = re.match(r"<(\w+)", opener).group(1)
    depth = 0
    for m in re.finditer(r"<(/?)%s\b[^>]*>" % tag, s[i:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return i, i + m.end()
    return None


def text_of(fragment):
    fragment = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    fragment = re.sub(r"<(br|/p|/div|/li|/h\d|/blockquote)\b[^>]*>", " ", fragment, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def iso(date_text):
    t = re.sub(r"\s+", " ", date_text.strip())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def entry(slug, s):
    h = block(s, '<div class="post-header">')
    if not h:
        return None
    hdr = s[h[0]:h[1]]
    title = re.search(r'<h1 class="entry-title">(.*?)</h1>', hdr, re.S)
    date = re.search(r'class="updated">([^<]+)<', hdr)
    author = re.search(r'href="\.\./author/[\w-]+/index\.html"[^>]*>\s*([^<]+?)\s*</a', hdr)
    cats = [text_of(c) for c in re.findall(r'href="\.\./category/[\w/-]+/index\.html"[^>]*>(.*?)</a', hdr, re.S)]
    body = block(s, '<div class="post-content entry-content">')
    text = text_of(s[body[0]:body[1]]) if body else ""
    th = block(s, '<div class="post-thumbnail header">')
    img = re.search(r'<img\b[^>]*\bsrc="\.\./(wp-content/[^"]+\.(?:jpe?g|png|gif|webp))"', s[th[0]:th[1]] if th else "", re.I)
    if not img and body:
        img = re.search(r'<img\b[^>]*\bsrc="\.\./(wp-content/uploads/[^"]+\.(?:jpe?g|png|gif|webp))"', s[body[0]:body[1]], re.I)
    image = img.group(1) if img and os.path.exists(os.path.join(ROOT, img.group(1))) else ""
    return [slug + "/", text_of(title.group(1)) if title else slug, iso(date.group(1)) if date else "",
            html.unescape(author.group(1)) if author else "", cats, image, text]


def main():
    posts = []
    for d in sorted(os.listdir(ROOT)):
        f = os.path.join(ROOT, d, "index.html")
        if d in SKIP or d.startswith(".") or not os.path.isfile(f):
            continue
        s = io.open(f, encoding="utf-8-sig", errors="replace").read()
        if re.search(r"<body\b[^>]*\bsingle-post\b", s):
            e = entry(d, s)
            if e:
                posts.append(e)
    posts.sort(key=lambda p: p[2], reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as o:
        json.dump(posts, o, ensure_ascii=False, separators=(",", ":"))
    print("%d posts -> %s (%.1f MB)" % (len(posts), os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
