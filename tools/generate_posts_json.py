#!/usr/bin/env python3
import os
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
IGNORE_DIRS = {'wp-admin', 'wp-includes', 'wp-content', 'assets', 'page', 'author', '.git'}

def is_post_dir(path):
    # A post directory contains an index.html file
    return os.path.isfile(os.path.join(path, 'index.html'))

def read_title(index_path):
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '<title' in line.lower():
                    # crude title extraction
                    start = line.lower().find('<title')
                    start = line.find('>', start)
                    if start != -1:
                        end = line.find('</title>', start)
                        if end != -1:
                            return line[start+1:end].strip()
        return ''
    except Exception:
        return ''

def main():
    posts = []
    for entry in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, entry)
        if not os.path.isdir(p):
            continue
        if entry in IGNORE_DIRS:
            continue
        # skip numeric page folders like 'index'
        if entry.startswith('index'):
            continue
        if is_post_dir(p):
            index_path = os.path.join(p, 'index.html')
            title = read_title(index_path)
            posts.append({
                'slug': entry,
                'url': f"{entry}/index.html",
                'title': title,
            })

    out_dir = os.path.join(ROOT, 'assets')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'posts.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f'Wrote {len(posts)} posts to {out_path}')

if __name__ == '__main__':
    main()
