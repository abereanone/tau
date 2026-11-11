"""Put a new post on every page that lists posts.

    python tools/add_post.py <slug>          # e.g. the-dorean-principle
    python tools/add_post.py <slug> --dry-run

Run from the repo root after the post folder (<slug>/index.html) exists. It reads the post's
title, date, featured image, author and categories from the post itself, then:

  1. builds the post card (same markup as every other card, root-absolute links)
  2. home page + /page/N/        card goes in by date, then generate_paginated_pages.py re-flows
  3. /category/<c>/ + page/N/    one listing per category the post is in (24 per page, re-flowed)
  4. /author/<a>/ + page/N/      the author's listing (same)
  5. search/index.json           tools/build_search_index.py
  6. sitemap.xml                 ONE <url> entry added by hand (gen-sitemap.mjs stamps every URL with
                                 today's file mtime, which would rewrite the whole file)

Not touched on purpose: assets/posts.json (stale for 150 posts; regenerating it is a separate cleanup)
and tag pages (not generated for new posts).

Safe to re-run: a post already in a listing is not added twice.
"""
import datetime
import html as htmllib
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER_PAGE = 24
START = '<div class="paginated_content">'
ENDS = ('<!-- /.paginated_content -->', '<!-- .paginated_content -->')  # category pages / author pages


def find_end(t):
    for e in ENDS:
        i = t.find(e)
        if i >= 0:
            return i
    return -1
ORIGIN = "https://thingsabove.us"
sys.path.insert(0, os.path.join(ROOT, "tools"))


def read(p):
    return io.open(p, encoding="utf-8-sig", newline="").read()


def write(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8-sig", newline="").write(t)


def parse_post(slug):
    s = read(os.path.join(ROOT, slug, "index.html"))
    title = htmllib.unescape(re.sub(r"<[^>]+>", "", re.search(r'<h1 class="entry-title">(.*?)</h1>', s, re.S).group(1))).strip()
    date = re.search(r'<span class="updated">([^<]+)</span>', s).group(1).strip()
    img = re.search(r'<div class="post-thumbnail header">\s*<img\s+src="([^"]+)"(?:[^>]*?width="(\d+)")?(?:[^>]*?height="(\d+)")?', s, re.S)
    meta = re.search(r'<div class="post-meta vcard">(.*?)</div>', s, re.S).group(1)
    author = re.search(r'href="\.\./author/([^/"]+)/index\.html"', meta).group(1)
    cats = re.findall(r'href="\.\./category/([^/"]+)/index\.html"', meta)
    return dict(slug=slug, title=title, date=date, img=img, author=author, cats=cats)


def card(p):
    e = htmllib.escape
    header = ""
    if p["img"]:
        src = "/" + re.sub(r"^(\.\./)+", "", p["img"].group(1))
        w, h = p["img"].group(2), p["img"].group(3)
        dims = f' width="{w}" height="{h}"' if w and h else ""
        header = (f'<div class="header"><a href="/{p["slug"]}/" class="featured-image"><img src="{src}" alt="{e(p["title"])}"{dims} />'
                  f'<span class="et_pb_extra_overlay"></span></a></div>')
    return (f'<article class="post">\n    {header}\n    <div class="post-content">\n'
            f'        <h2 class="post-title entry-title"><a href="/{p["slug"]}/">{e(p["title"])}</a></h2>\n'
            f'        <div class="post-meta vcard"><p><span class="updated">{e(p["date"])}</span></p></div>\n'
            f'        <div class="excerpt entry-summary"><a class="read-more-button" href="/{p["slug"]}/">Read More</a></div>\n'
            f'    </div>\n</article>')


def card_date(c):
    m = re.search(r'<span class="updated">([^<]+)</span>', c)
    try:
        return datetime.datetime.strptime(m.group(1).strip(), "%b %d, %Y")
    except Exception:
        return None


def insert_by_date(cards, new, p):
    nd = card_date(new)
    for i, c in enumerate(cards):
        cd = card_date(c)
        if cd and nd and cd < nd:
            return cards[:i] + [new] + cards[i:]
    return cards + [new]


def pagination(total, current, base):
    """Same markup the category/author listings already use: first, last, current +-2."""
    href = lambda n: f"{base}/" if n == 1 else f"{base}/page/{n}/"
    want = {1, total, current} | {current + d for d in (-2, -1, 1, 2)}
    pages = sorted(n for n in want if 1 <= n <= total)
    out = ['<div class="archive-pagination"><ul class="pagination">']
    if current > 1:
        out.append(f'<li class="prev static-arrow"><a class="prev static-arrow" href="{href(current-1)}" aria-label="Previous page"></a></li>')
    prev = 0
    for n in pages:
        if prev and n > prev + 1:
            out.append('<li class="gap"><span>&hellip;</span></li>')
        cls = ' class="current active"' if n == current else ""
        out.append(f'<li{cls}><a href="{href(n)}">{n}</a></li>')
        prev = n
    if current < total:
        out.append(f'<li class="next static-arrow"><a class="next static-arrow" href="{href(current+1)}" aria-label="Next page"></a></li>')
    out.append("</ul></div>")
    return "\n".join(out)


def retarget(html, base, page):
    url = f"{ORIGIN}{base}/page/{page}/"
    html = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), html, count=1)
    html = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), html, count=1)
    # titles of other pages already end "- Page N": rewrite that suffix instead of appending another
    html = re.sub(r"(<title>)(.*?)( - Page \d+)?(</title>)", lambda m: m.group(1) + m.group(2) + f" - Page {page}" + m.group(4), html, count=1, flags=re.S)
    html = re.sub(r'(<meta property="og:title" content=")([^"]*?)( - Page \d+)?(")', lambda m: m.group(1) + m.group(2) + f" - Page {page}" + m.group(4), html, count=1)
    return html


def reflow_listing(kind, name, p, dry):
    """kind 'category' or 'author'. Harvest every card, add the new one, re-split into pages of 24."""
    base = f"/{kind}/{name}"
    folder = os.path.join(ROOT, kind, name)
    if not os.path.exists(os.path.join(folder, "index.html")):
        print(f"  skip {base}: no listing page"); return
    files = [os.path.join(folder, "index.html")]
    pdir = os.path.join(folder, "page")
    if os.path.isdir(pdir):
        files += [os.path.join(pdir, str(n), "index.html") for n in sorted(int(d) for d in os.listdir(pdir) if d.isdigit())]
    cards, seen = [], set()
    for f in files:
        for c in re.findall(r'<article class="post">.*?</article>', read(f), re.S):
            m = re.search(r'href="([^"]+)"', c)
            href = re.sub(r"^(\.\./)+", "/", m.group(1)) if m else c
            href = re.sub(r"index\.html$", "", href)
            if href in seen:
                continue
            seen.add(href); cards.append(c)
    if f'/{p["slug"]}/' in seen:
        print(f"  {base}: already listed"); return
    cards = insert_by_date(cards, card(p), p)
    total = -(-len(cards) // PER_PAGE)
    first = read(files[0])
    si, ei = first.find(START), find_end(first)
    if si < 0 or ei < 0:
        raise SystemExit(f"markers not found in {files[0]}")
    for page in range(1, total + 1):
        chunk = cards[(page - 1) * PER_PAGE: page * PER_PAGE]
        dest = files[0] if page == 1 else os.path.join(pdir, str(page), "index.html")
        # the page's own head/footer are kept; a page that does not exist yet is cloned from the last one
        template = read(dest) if os.path.exists(dest) else read(files[-1] if len(files) > 1 else files[0])
        a, b = template.find(START), find_end(template)
        block = f'{START}\n<div class="paginated_page paginated_page_{page} active" data-columns>\n' + "\n".join(chunk) + "\n</div>\n</div>\n" + pagination(total, page, base) + "\n\n\n                      "
        out = template[:a] + block + template[b:]
        if not os.path.exists(dest) and page > 1:
            out = retarget(out, base, page)
        if not dry:
            write(dest, out)
    print(f"  {base}: {len(cards)} posts, {total} pages")


def sitemap_entry(slug, dry):
    p = os.path.join(ROOT, "sitemap.xml")
    raw = io.open(p, encoding="utf-8", newline="").read()
    loc = f"{ORIGIN}/{slug}/"
    if loc in raw:
        print("  sitemap: already has", slug); return
    now = datetime.datetime.now().astimezone()
    z = now.strftime("%z")
    ts = now.strftime("%Y-%m-%dT%H:%M:%S") + z[:3] + ":" + z[3:]
    entry = f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{ts}</lastmod>\n  </url>\n"
    locs = list(re.finditer(r"  <url>\n    <loc>([^<]*)</loc>", raw))
    pos = next((m.start() for m in locs[1:] if m.group(1) > loc), None)
    raw = raw[:pos] + entry + raw[pos:] if pos is not None else raw.replace("</urlset>", entry + "</urlset>")
    if not dry:
        io.open(p, "w", encoding="utf-8", newline="").write(raw)
    print("  sitemap: added", loc)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    slug = args[0]
    p = parse_post(slug)
    print(f"{p['title']}  ({p['date']}) by {p['author']}; categories {p['cats']}; image {'yes' if p['img'] else 'no'}")

    # home: insert the card into index.html by date, then let the existing generator re-flow home + /page/N/
    idx = os.path.join(ROOT, "index.html")
    raw = read(idx)
    if f'href="/{slug}/"' not in raw:
        a = raw.find(START)
        b = raw.find('<ul class="pagination">', a)
        cards = re.findall(r'<article class="post">.*?</article>', raw[a:b], re.S)
        new_cards = insert_by_date(cards, card(p), p)
        if not dry:
            first_card = raw.find(cards[0], a)
            pos = first_card + sum(len(c) + 1 for c in cards[:new_cards.index(card(p))])
            raw = raw[:pos] + card(p) + "\n" + raw[pos:]
            write(idx, raw)
    if not dry:
        subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "generate_paginated_pages.py")], cwd=ROOT)

    for c in p["cats"]:
        reflow_listing("category", c, p, dry)
    reflow_listing("author", p["author"], p, dry)

    if not dry:
        subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "build_search_index.py")], cwd=ROOT)
    sitemap_entry(slug, dry)
    print("done" + (" (dry run, nothing written)" if dry else ""))


if __name__ == "__main__":
    main()
