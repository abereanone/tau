"""Create search/index.html from a category archive, so it keeps the site's header, footer and card grid.

    python tools/make_search_page.py [category/<name>]

Only needed once, or after the site's page chrome changes. The index itself is rebuilt with
tools/build_search_index.py.
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = {"thingsabove.us": ("https://thingsabove.us", "assets"),
        "michaelcoughlin.net": ("https://michaelcoughlin.net", "mnet-shared")}
NAME = next(k for k in SITE if k in ROOT.replace("\\", "/"))
ORIGIN, ASSETS = SITE[NAME]
SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "category/sports" if NAME == "thingsabove.us" else "category/c"
DST_DIR = "search"


def block(s, start):
    """(start, end) of the balanced element whose opening tag starts at `start`."""
    tag = re.match(r"<(\w+)", s[start:]).group(1)
    depth = 0
    for m in re.finditer(r"<(/?)%s\b[^>]*>" % tag, s[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start, start + m.end()
    raise ValueError("unbalanced <%s>" % tag)


def relocate(text):
    """Relative href/src URLs written for SRC_DIR, rewritten for DST_DIR."""
    def fix(m):
        url = m.group(3)
        if not url or re.match(r"(/|#|[a-z][a-z0-9+.-]*:)", url, re.I):
            return m.group(0)
        path, rest = re.match(r"([^?#]*)(.*)", url).groups()
        new = os.path.relpath(os.path.normpath(os.path.join(SRC_DIR, path)), DST_DIR).replace(os.sep, "/")
        if path.endswith("/") and not new.endswith("/"):
            new += "/"
        return "%s=%s%s%s" % (m.group(1), m.group(2), new + rest, m.group(2))
    return re.sub(r"""\b(href|src)=(["'])(.*?)\2""", fix, text)


def main():
    raw = open(os.path.join(ROOT, SRC_DIR, "index.html"), "rb").read()
    s = relocate(raw.decode("utf-8-sig"))
    root = "/" if NAME == "thingsabove.us" else "../"

    s = re.sub(r"<title>.*?</title>", "<title>Search | %s</title>" % s[s.find("<title>") + 7:s.find("</title>")].split("|")[-1].strip(),
               s, count=1, flags=re.S)
    s = re.sub(r'(<link rel="canonical" href=")[^"]*', r"\g<1>%s/search/" % ORIGIN, s, count=1)
    s = re.sub(r'(<meta property="og:url" content=")[^"]*', r"\g<1>%s/search/" % ORIGIN, s, count=1)
    s = re.sub(r'(<meta property="og:title" content=")[^"]*', r"\g<1>Search", s, count=1)
    s = re.sub(r"<h1>Category: <span>.*?</span></h1>", "<h1>Search</h1>", s, count=1, flags=re.S)

    feed = re.search(r'<div\s+class="posts-blog-feed-module', s)
    b = block(s, feed.start())
    ui = """<div class="site-search">
                      <form id="site-search-form" class="site-search-form" role="search" action="./" method="get">
                        <input type="search" id="site-search-q" name="q" placeholder="Search every post" aria-label="Search every post" autocomplete="off" />
                        <button type="submit">Search</button>
                      </form>
                      <p id="site-search-status" class="site-search-status" aria-live="polite"></p>
                      <div class="paginated_content">
                        <div id="site-search-results" class="paginated_page site-search-results"></div>
                      </div>
                      <button type="button" id="site-search-more" class="site-search-more" hidden>Show more results</button>
                      <noscript><p>Search needs JavaScript turned on. You can also browse posts by category.</p></noscript>
                    </div>"""
    s = s[:b[0]] + ui + s[b[1]:]

    grid = "%s%s/post-grid.css" % ("../" if root == "../" else "/", ASSETS)
    head = ""
    if "post-grid.css" not in s:
        head += '    <link rel="stylesheet" href="%s" />\n' % grid
    head += '    <link rel="stylesheet" href="%s%s/search.css" />\n  ' % (root, ASSETS)
    s = s.replace("</head>", head + "</head>", 1)
    s = s.replace("</body>", '    <script src="%s%s/search.js" data-index="%ssearch/index.json" data-root="%s"></script>\n  </body>'
                  % (root, ASSETS, root, root), 1)

    out = os.path.join(ROOT, DST_DIR, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="").write(s)
    print("wrote", os.path.relpath(out, ROOT), "from", SRC_DIR)


if __name__ == "__main__":
    main()
