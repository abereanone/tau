"""Rebuild the home page and /page/N/ archives from the post cards already in them.

    python tools/generate_paginated_pages.py

Run from the repo root after adding or removing a post. Cards are harvested from the
existing listing pages rather than from assets/posts.json, because posts.json carries
only slugs and empty titles while the cards carry the title, date and featured image
the theme already chose for each post.

Every card's href and img src is rewritten to a root-absolute path, so the same card
markup works on the home page and under /page/N/ alike.
"""

import io
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
PAGE_DIR = os.path.join(ROOT, "page")

PER_PAGE = 24
ORIGIN = "https://thingsabove.us"
START = '<div class="paginated_content">'
END = "<!-- /.posts-blog-feed-module -->"

read = lambda p: io.open(p, encoding="utf-8-sig", newline="").read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8-sig", newline="").write(text)


def absolutise(card):
    """slug/index.html -> /slug/  ·  wp-content/x.jpg -> /wp-content/x.jpg

    Cards copied from a page under /page/N/ would otherwise resolve against that
    directory. Post links lose the index.html so they match the sitemap and the
    canonical each post declares.
    """
    def fix(m):
        attr, url = m.group(1), m.group(2)
        if url.startswith(("/", "http://", "https://", "#", "data:", "mailto:")):
            return m.group(0)
        url = re.sub(r"^(\.\./)+", "", url)
        if url.endswith("/index.html"):
            url = url[: -len("index.html")]
        return f'{attr}="/{url}"'

    return re.sub(r'\b(href|src)="([^"]+)"', fix, card)


def harvest():
    """Every post card, in the order the site already lists them, deduped by URL."""
    sources = [INDEX]
    if os.path.isdir(PAGE_DIR):
        nums = sorted((int(d) for d in os.listdir(PAGE_DIR) if d.isdigit()))
        sources += [os.path.join(PAGE_DIR, str(n), "index.html") for n in nums]

    cards, seen = [], set()
    for src in sources:
        if not os.path.exists(src):
            continue
        for card in re.findall(r"<article class=\"post\">.*?</article>", read(src), re.S):
            card = absolutise(card)
            m = re.search(r'href="([^"]+)"', card)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            cards.append(card)
    return cards


def pagination(total, current):
    """Windowed: first, last, and a couple either side of current. 27 numbers in a
    row is unreadable, which is what listing every page would give at 24 per page."""
    href = lambda n: "/" if n == 1 else f"/page/{n}/index.html"
    want = {1, total, current} | {current + d for d in (-2, -1, 1, 2)}
    pages = sorted(n for n in want if 1 <= n <= total)

    out = ['<ul class="pagination">']
    if current > 1:
        out.append(f'<li class="prev static-arrow"><a class="prev static-arrow" href="{href(current-1)}"></a></li>')
    prev = 0
    for n in pages:
        if prev and n > prev + 1:
            out.append('<li class="gap"><span>&hellip;</span></li>')
        cls = ' class="current"' if n == current else ""
        out.append(f'<li{cls}><a href="{href(n)}">{n}</a></li>')
        prev = n
    if current < total:
        out.append(f'<li class="next static-arrow"><a class="next static-arrow" href="{href(current+1)}"></a></li>')
    out.append("</ul>")
    return "\n".join(out)


def with_base(html):
    """Pages under /page/N/ need <base href="/"> for the theme's relative assets."""
    if re.search(r"<base\b", html):
        return html
    return re.sub(r"(<head[^>]*>)", r'\1\n    <base href="/" />', html, count=1)

def retarget(html, page):
    """Point a paged archive's head at itself.

    Everything before the card block is copied from index.html, so without this
    every /page/N/ would declare the home page as its canonical and its og:url,
    telling Google the archives are duplicates of the front page.
    """
    url = "%s/page/%d/" % (ORIGIN, page)
    html = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), html, count=1)
    html = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), html, count=1)
    html = re.sub(r'(<meta property="og:title" content=")([^"]*)(")',
                  lambda m: m.group(1) + m.group(2) + (" - Page %d" % page) + m.group(3), html, count=1)
    html = re.sub(r"(<title>)(.*?)(</title>)",
                  lambda m: m.group(1) + m.group(2) + (" - Page %d" % page) + m.group(3), html, count=1, flags=re.S)
    return html



def main():
    cards = harvest()
    total = max(1, -(-len(cards) // PER_PAGE))
    index_txt = read(INDEX)

    si, ei = index_txt.find(START), index_txt.find(END)
    if si == -1 or ei == -1:
        raise SystemExit("Could not find the paginated content markers in index.html")
    prefix, suffix = index_txt[:si], index_txt[ei + len(END):]

    for page in range(1, total + 1):
        chunk = cards[(page - 1) * PER_PAGE: page * PER_PAGE]
        block = (
            f'{START}\n<div class="paginated_page paginated_page_{page} active" data-columns>\n'
            + "\n".join(chunk)
            + "\n</div>\n</div>\n"
            + pagination(total, page)
            + "\n"
        )
        html = prefix + block + END + suffix
        if page == 1:
            write(INDEX, html)
        else:
            write(os.path.join(PAGE_DIR, str(page), "index.html"), retarget(with_base(html), page))

    for d in os.listdir(PAGE_DIR):
        if d.isdigit() and int(d) > total:
            shutil.rmtree(os.path.join(PAGE_DIR, d))
            print("removed stale", os.path.join("page", d))

    print(f"{len(cards)} posts -> {total} pages of {PER_PAGE} (home + page/2..{total})")


if __name__ == "__main__":
    main()
