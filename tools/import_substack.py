"""Copy a post from Allen Nelson's Substack (cuatronelson.substack.com) to thingsabove.us.

    python tools/import_substack.py <slug or post URL>             # builds <slug>/index.html, then runs add_post.py
    python tools/import_substack.py <slug or post URL> --no-list   # build the page only
    python tools/import_substack.py --list                         # Substack posts not on TAU yet, oldest first

The TAU slug is the Substack slug. The page is cloned from TEMPLATE (an Allen Nelson post with no comments),
dated with the Substack publish date (US Eastern), and marked canonical on thingsabove.us.

  - body: Substack's subscribe boxes, share/comment buttons and image-expand buttons are removed; the
    subtitle becomes an italic first line; links to his other Substack posts point at the TAU copy once it exists
  - featured image: the Substack cover, cropped by Substack's image CDN to 1280x640, saved as
    wp-content/uploads/YYYY/MM/<slug>-1280x640.webp (page) and .jpg (og:image); the copy of it at the
    top of the body is dropped. Other body images are saved beside it as <slug>-N.jpg
  - categories: Substack tags mapped by TAG_CATEGORIES, else "theology"
  - related posts: the four Allen Nelson posts nearest in date
"""
import argparse
import datetime
import html as htmllib
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from add_post import parse_post, read, write  # noqa: E402

PUB = "https://cuatronelson.substack.com"
AUTHOR = "anelson"
TEMPLATE = "lessons-from-acts-5"
ORIGIN = "https://thingsabove.us"
UA = {"User-Agent": "Mozilla/5.0"}
EASTERN = ZoneInfo("America/New_York")

CATEGORY_NAMES = {
    "evangelism": "Evangelism", "general": "General", "missions": "Missions", "parenting": "Parenting",
    "preaching": "Preaching", "theology": "Theology",
}
# substring of a lower-cased Substack tag -> TAU category
TAG_CATEGORIES = [("evangel", "evangelism"), ("preach", "preaching"), ("parent", "parenting"), ("mission", "missions")]


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def substack_slugs():
    xml = fetch(f"{PUB}/sitemap.xml").decode("utf-8")
    return re.findall(r"<loc>[^<]*/p/([^<]+)</loc>", xml)


def get_post(slug):
    return json.loads(fetch(f"{PUB}/api/v1/posts/{slug}").decode("utf-8"))


def original_image(url):
    """substackcdn fetch URL -> the original image URL inside it."""
    m = re.search(r"/(https?%3A%2F%2F.+)$", url)
    return urllib.parse.unquote(m.group(1)) if m else url


def cdn(url, opts):
    return f"https://substackcdn.com/image/fetch/{opts}/{urllib.parse.quote(original_image(url), safe='')}"


def save(url, rel, dry):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    if dry:
        print(f"  would save {rel}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        open(path, "wb").write(fetch(url))
    print(f"  saved {rel}")


def categories(post):
    cats = []
    for t in post.get("postTags") or []:
        name = t["name"].lower()
        for sub, cat in TAG_CATEGORIES:
            if sub in name and cat not in cats:
                cats.append(cat)
    return cats or ["theology"]


def clean_body(post, slug, upload_dir, dry):
    soup = BeautifulSoup(post["body_html"], "html.parser")
    for sel in (".subscription-widget-wrap-editor", ".button-wrapper", ".image-link-expand", "form", "button", "svg"):
        for el in soup.select(sel):
            el.decompose()
    figs = soup.select(".captioned-image-container")
    if figs and "topImage&quot;:true" in str(figs[0]).replace('"', "&quot;"):
        figs.pop(0).decompose()
    for n, box in enumerate(figs, 1):
        img = box.find("img")
        caption = box.find("figcaption")
        rel = f"{upload_dir}/{slug}-{n}.jpg"
        save(cdn(img["src"], "w_1200,c_limit,f_jpg,q_auto:good,fl_progressive:steep"), rel, dry)
        w, h = int(img.get("width") or 0), int(img.get("height") or 0)
        if w > 1200:
            w, h = 1200, round(h * 1200 / w)
        fig = soup.new_tag("figure", attrs={"class": "wp-block-image"})
        attrs = {"src": f"../{rel}", "alt": img.get("alt") or "", "loading": "lazy", "decoding": "async"}
        if w and h:
            attrs.update(width=str(w), height=str(h))
        fig.append(soup.new_tag("img", attrs=attrs))
        if caption:
            fig.append(caption)
        box.replace_with(fig)
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True).lower() == post["title"].strip().lower():
        h1.decompose()
    for a in soup.find_all("a", href=True):
        m = re.match(re.escape(PUB) + r"/p/([^?#/]+)", a["href"])
        if m and os.path.exists(os.path.join(ROOT, m.group(1), "index.html")):
            a["href"] = f"../{m.group(1)}/index.html"
            a.attrs.pop("target", None)
            a.attrs.pop("rel", None)
    for el in soup.find_all(True):
        for attr in ("data-attrs", "data-component-name"):
            el.attrs.pop(attr, None)
    body = "\n\n".join(str(el) for el in soup.contents if str(el).strip())
    sub = (post.get("subtitle") or "").strip()
    if sub:
        body = f"<p><em>{htmllib.escape(sub, quote=False)}</em></p>\n\n" + body
    return body


def next_post_id():
    top = 0
    for name in os.listdir(ROOT):
        p = os.path.join(ROOT, name, "index.html")
        if os.path.isfile(p):
            m = re.search(r'<article\s+id="post-(\d+)"', read(p))
            if m:
                top = max(top, int(m.group(1)))
    return top + 1


def tau_date(d):
    return datetime.datetime.strptime(d, "%b %d, %Y")


def related(slug, when):
    """The four other Allen Nelson posts nearest in date."""
    out = []
    for name in os.listdir(ROOT):
        p = os.path.join(ROOT, name, "index.html")
        if name == slug or not os.path.isfile(p):
            continue
        s = read(p)
        if f'href="../author/{AUTHOR}/index.html"' not in s or '<div class="post-meta vcard">' not in s:
            continue
        try:
            info = parse_post(name)
            d = tau_date(info["date"])
        except Exception:
            continue
        if info["author"] != AUTHOR or not info["img"]:
            continue
        out.append((abs((d - when).days), info))
    out.sort(key=lambda x: x[0])
    return [i for _, i in out[:4]]


def related_html(posts):
    e = lambda t: htmllib.escape(t)
    blocks = []
    for p in posts:
        src, w, h = p["img"].group(1), p["img"].group(2), p["img"].group(3)
        dims = f' width="{w}" height="{h}"' if w and h else ""
        blocks.append(f"""                  <div class="related-post">
                    <div class="featured-image">
                      <a href="../{p['slug']}/index.html" title="{e(p['title'])}" class="post-thumbnail">
                        <img src="{src}" alt="{e(p['title'])}"{dims} loading="lazy" decoding="async" /><span class="et_pb_extra_overlay"></span>
                      </a>
                    </div>
                    <h4 class="title">
                      <a href="../{p['slug']}/index.html">{e(p['title'])}</a>
                    </h4>
                    <p class="date">
                      <span class="updated">{e(p['date'])}</span>
                    </p>
                  </div>""")
    return "\n".join(blocks)


def share_html(title, url, image):
    q = lambda t: urllib.parse.quote(t, safe="")
    t = q(title)
    nets = [
        ("facebook", "Facebook", f"http://www.facebook.com/sharer.php?u={url}&amp;t={t}"),
        ("twitter", "Twitter", f"http://twitter.com/intent/tweet?text={t}%20{url}"),
        ("tumblr", "Tumblr", f"https://www.tumblr.com/widgets/share/tool?canonicalUrl={q(url)}"),
        ("pinterest", "Pinterest", f"http://www.pinterest.com/pin/create/button/?url={url}&amp;description={t}&amp;media={image}"),
        ("linkedin", "LinkedIn", f"http://www.linkedin.com/shareArticle?mini=true&amp;url={url}&amp;title={t}"),
        ("buffer", "Buffer", f"https://buffer.com/add?url={q(url)}&amp;text={t}"),
        ("basic_email", "Email", "#"),
        ("basic_print", "Print", "#"),
    ]
    et = htmllib.escape(title)
    links = []
    for key, label, href in nets:
        target = ' target="_blank" rel="noopener"' if href != "#" else ""
        links.append(f"""<a{target}
                      href="{href}"
                      class="social-share-link"
                      title='Share "{et}" via {label}'
                      data-network-name="{key}"
                      data-share-title="{et}"
                      data-share-url="{url}"
                    >
                      <span
                        class="et-extra-icon et-extra-icon-{key} et-extra-icon-background-hover"
                      ></span> </a
                    >""")
    return '<p class="share-title">Share:</p>\n\n                    ' + "".join(links)


def build(slug, dry):
    post = get_post(slug)
    if post.get("audience") != "everyone":
        sys.exit(f"{slug}: not a free post ({post.get('audience')})")
    title = post["title"].strip()
    when = datetime.datetime.fromisoformat(post["post_date"].replace("Z", "+00:00")).astimezone(EASTERN)
    date = f"{when:%b} {when.day}, {when.year}"
    upload_dir = f"wp-content/uploads/{when:%Y}/{when:%m}"
    url = f"{ORIGIN}/{slug}/"
    cats = categories(post)
    pid = next_post_id()
    print(f"{slug}: '{title}', {date}, categories {cats}, post-{pid}")

    if post.get("cover_image"):
        crop = "w_1280,h_640,c_fill,{f},q_auto:good,fl_progressive:steep"
        save(cdn(post["cover_image"], crop.format(f="f_webp")), f"{upload_dir}/{slug}-1280x640.webp", dry)
        save(cdn(post["cover_image"], crop.format(f="f_jpg")), f"{upload_dir}/{slug}-1280x640.jpg", dry)
        thumb = (f'<div class="post-thumbnail header">\n                  <img\n                    src="../{upload_dir}/{slug}-1280x640.webp"\n'
                 f'                    alt="{htmllib.escape(title)}"\n                    width="1280"\n                    height="640"\n                  />\n'
                 f'                </div>\n\n')
        og_image = f"{ORIGIN}/{upload_dir}/{slug}-1280x640.jpg"
    else:
        thumb = ""
        og_image = f"{ORIGIN}/wp-content/uploads/2022/05/thingsaboveus.png.jpg"

    body = clean_body(post, slug, upload_dir, dry)
    desc = (post.get("description") or post.get("subtitle") or "").strip() or BeautifulSoup(body, "html.parser").get_text(" ", strip=True)[:200]

    s = read(os.path.join(ROOT, TEMPLATE, "index.html"))
    e = htmllib.escape
    sub = lambda pat, rep, flags=0: re.sub(pat, lambda m: rep, s, count=1, flags=flags)
    s = sub(r"<title>.*?</title>", f"<title>{e(title)} | Things Above Us</title>", re.S)
    s = sub(r'<link rel="canonical" href="[^"]*" />', f'<link rel="canonical" href="{url}" />')
    s = sub(r'<meta property="og:title" content="[^"]*" />', f'<meta property="og:title" content="{e(title)}" />')
    s = sub(r'<meta property="og:description" content="[^"]*" />', f'<meta property="og:description" content="{e(desc)}" />')
    s = sub(r'<meta property="og:url" content="[^"]*" />', f'<meta property="og:url" content="{url}" />')
    s = sub(r'<meta property="og:image" content="[^"]*" />', f'<meta property="og:image" content="{og_image}" />')
    s = s.replace("postid-16617", f"postid-{pid}")
    cat_classes = " ".join(f"category-{c}" for c in cats)
    s = sub(r'<article\s+id="post-16617"\s+class="[^"]*"',
            f'<article\n                id="post-{pid}"\n                class="module single-post-module post-{pid} post type-post status-publish '
            f'format-standard{" has-post-thumbnail" if thumb else ""} hentry {cat_classes} et-has-post-format-content et_post_format-et-post-format-standard"')
    s = sub(r'<h1 class="entry-title">.*?</h1>', f'<h1 class="entry-title">{e(title)}</h1>', re.S)
    cat_links = ",\n                      ".join(
        f'<a href="../category/{c}/index.html" rel="tag"\n                        >{CATEGORY_NAMES[c]}</a\n                      >' for c in cats)
    s = sub(r'<span class="updated">[^<]*</span> \|\s*<a href="\.\./category/.*?</a\s*>',
            f'<span class="updated">{date}</span> |\n                      {cat_links}', re.S)
    s = sub(r'<div class="post-thumbnail header">.*?</div>\s*', thumb, re.S)
    s = re.sub(
        r'(<div class="post-content entry-content">).*?(</div>\s*</div>\s*<div class="post-footer">)',
        lambda m: m.group(1) + "\n" + body + "\n                  " + m.group(2), s, count=1, flags=re.S)
    s = re.sub(r'<p class="share-title">Share:</p>.*?</a>\s*(?=</div>\s*<style type="text/css" id="rating-stars">)',
               lambda m: share_html(title, url, og_image) + "\n                  ", s, count=1, flags=re.S)
    s = re.sub(r'\s*<nav class="post-nav">.*?</nav>', "", s, count=1, flags=re.S)
    s = re.sub(r'(<div class="related-posts-content clearfix">).*?(</div>\s*</div>\s*</div>\s*<!-- /\.et_pb_extra_column)',
               lambda m: m.group(1) + "\n" + related_html(related(slug, when.replace(tzinfo=None))) + "\n                " + m.group(2),
               s, count=1, flags=re.S)

    s = re.sub(r"[ \t]*<!-- Mirrored from [^>]*-->\n?", "", s)
    s = s.replace('page_id: "16617"', f'page_id: "{pid}"')

    marks = (TEMPLATE, "5 Lessons from Acts 5", "16617", "YouTube-Thumbnail-Format-7")
    rel = re.search(r'<div class="related-posts-content clearfix">.*?<!-- /\.et_pb_extra_column', s, re.S)
    check = s[:rel.start()] + s[rel.end():] if rel else s  # the template post may be a related post, rightly
    left = [line.strip()[:120] for line in check.split("\n") if any(t in line for t in marks)]
    if left:
        sys.exit("template text left in the page:\n  " + "\n  ".join(left))
    out = os.path.join(ROOT, slug, "index.html")
    if dry:
        print(f"  would write {slug}/index.html ({len(s)} chars)")
    else:
        write(out, s)
        print(f"  wrote {slug}/index.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-list", action="store_true", help="build the page but do not run add_post.py")
    ap.add_argument("--list", action="store_true", help="show Substack posts not on TAU yet")
    a = ap.parse_args()
    if a.list:
        missing = [s for s in substack_slugs() if not os.path.exists(os.path.join(ROOT, s, "index.html"))]
        for s in reversed(missing):
            print(s)
        return
    if not a.post:
        ap.error("give a slug or post URL, or --list")
    slug = re.sub(r"^.*/p/", "", a.post.strip()).split("?")[0].strip("/")
    if os.path.exists(os.path.join(ROOT, slug, "index.html")):
        sys.exit(f"{slug}/index.html already exists")
    build(slug, a.dry_run)
    if not a.no_list and not a.dry_run:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "add_post.py"), slug], check=True)


if __name__ == "__main__":
    main()
