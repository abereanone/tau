import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_JSON = os.path.join(ROOT, 'assets', 'posts.json')
INDEX_HTML = os.path.join(ROOT, 'index.html')
OUT_DIR = os.path.join(ROOT, 'page')

def slug_to_path(url):
    return os.path.join(ROOT, url.replace('/', os.sep))

def extract_image_from_post(post_path):
        try:
                with open(post_path, 'r', encoding='utf-8') as f:
                        txt = f.read()
        except Exception:
                return ''
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', txt)
        if m:
                return m.group(1)
        return ''

def find_article_block_in_index(index_txt, post_url):
        # find anchor for post_url and then extract enclosing <article>...</article>
        href = f'href="{post_url}"'
        pos = index_txt.find(href)
        if pos == -1:
                return None
        # find the last '<article' before pos
        a_start = index_txt.rfind('<article', 0, pos)
        if a_start == -1:
                return None
        a_end = index_txt.find('</article>', pos)
        if a_end == -1:
                return None
        a_end += len('</article>')
        return index_txt[a_start:a_end]

def make_article_html(post, img_src, index_txt):
        # try to copy full article block from index.html to preserve classes and layout
        url = post.get('url')
        found = find_article_block_in_index(index_txt, url)
        if found:
                return found
        title = post.get('title') or post.get('slug')
        # fallback minimal article block resembling homepage
        return f'''<article class="post">
    <div class="header">
        <a href="{url}" class="featured-image">
            {f'<img src="{img_src}" alt="{title}" />' if img_src else ''}
            <span class="et_pb_extra_overlay"></span>
        </a>
    </div>
    <div class="post-content">
        <h2 class="post-title entry-title"><a href="{url}">{title}</a></h2>
        <div class="excerpt entry-summary"><a class="read-more-button" href="{url}">Read More</a></div>
    </div>
</article>'''

def build_pagination_ul(total_pages, current=None):
    parts = ['<ul class="pagination">']
    prev_target = current - 1 if current and current > 1 else 1
    next_target = current + 1 if current and current < total_pages else total_pages
    parts.append(f'<li class="prev static-arrow"><a class="prev static-arrow" href="../{prev_target}/index.html"></a></li>')
    for i in range(1, total_pages+1):
        cls = ' current' if current==i else ''
        parts.append(f'<li class="{cls}"><a href="../{i}/index.html" class="static-pagination-page pagination-page-{i}" data-page="{i}">{i}</a></li>')
    parts.append(f'<li class="next static-arrow"><a class="next static-arrow" href="../{next_target}/index.html"></a></li>')
    parts.append('</ul>')
    return '\n'.join(parts)

def main():
    with open(POSTS_JSON,'r',encoding='utf-8') as f:
        posts = json.load(f)

    # create 18 pages as requested by user
    total_pages = 18
    per_page = math.ceil(len(posts)/total_pages)

    with open(INDEX_HTML,'r',encoding='utf-8') as f:
        index_txt = f.read()

    start_marker = '<div class="paginated_content">'
    end_marker = '<!-- /.posts-blog-feed-module -->'
    si = index_txt.find(start_marker)
    ei = index_txt.find(end_marker)
    if si == -1 or ei == -1:
        print('Could not find paginated content markers in index.html')
        return

    prefix = index_txt[:si]
    suffix = index_txt[ei+len(end_marker):]

    os.makedirs(OUT_DIR, exist_ok=True)

    for page in range(1, total_pages+1):
        s = (page-1)*per_page
        page_posts = posts[s:s+per_page]
        articles = []
        for p in page_posts:
            post_index = slug_to_path(p['url'])
            if post_index.endswith(os.sep) or post_index.endswith('/'):
                post_index = os.path.join(post_index, 'index.html')
            if not os.path.isabs(post_index):
                post_index = os.path.join(ROOT, post_index)
            img = extract_image_from_post(post_index)
            articles.append(make_article_html(p, img, index_txt))

        # build paginated_page wrapper so layout JS/CSS finds expected classes
        paginated_block = start_marker + '\n'
        paginated_block += f'<div class="paginated_page paginated_page_{page} active" data-columns>\n'
        paginated_block += '\n'.join(articles)
        paginated_block += '\n</div>\n'  # close paginated_page
        paginated_block += '</div>\n'  # close paginated_content
        paginated_block += '                      <span class="loader"><img src="wp-content/themes/Extra/images/pagination-loading.gif" alt="Loading"/></span>\n'
        paginated_block += build_pagination_ul(total_pages, current=page)

        out_html = prefix + paginated_block + suffix

        out_dir = os.path.join(OUT_DIR, str(page))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'index.html')
        with open(out_path, 'w', encoding='utf-8') as out_f:
            out_f.write(out_html)
        print('Wrote', out_path)

if __name__ == '__main__':
    main()
