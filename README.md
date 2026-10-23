# Things Above Us

Static mirror of the thingsabove.us blog (originally WordPress, captured with HTTrack), served by Cloudflare Pages. There is no build step: pushing to `main` publishes the repo root as it is, so **anything at the top level is public**. Do not put notes, logs or exports there.

## Layout

- One folder per post at the top level (`<slug>/index.html`), plus `category/`, `author/`, `page/N/` (home-page archive pages) and `search/`.
- `assets/` - site scripts and data (below). `wp-content/`, `wp-includes/` - mirrored theme, plugin and upload files.
- `_redirects` - Cloudflare Pages redirects. `404.html` - not-found page. `sitemap.xml` - generated.

## Preview locally

```bash
python serve.py        # http://localhost:8082, opens a browser; unknown paths redirect to /
```

## Tools (run from the repo root after adding, removing or editing a post)

| Script | What it does |
|---|---|
| `tools/generate_posts_json.py` | Rewrites `assets/posts.json` from the post folders (any folder with an `index.html`, ignoring `wp-*`, `assets`, `page`, `author`). |
| `tools/generate_paginated_pages.py` | Rebuilds the home page and `/page/N/` archives from the post cards already in them (so titles, dates and featured images are kept); rewrites card links to root-absolute paths. |
| `assets/build-pages.ps1` | The PowerShell version of the same pagination rebuild, from metadata read out of every post. Use one or the other. |
| `tools/build_search_index.py` | Builds `search/index.json` (title, date, author, categories, image, text of every post) for the client-side search. |
| `tools/gen-sitemap.mjs` | Regenerates `sitemap.xml` (`node tools/gen-sitemap.mjs`), skipping HTTrack query-string artifacts and the 404 page. Not part of the Pages build, on purpose: a deploy stays a plain file copy. |

## Browser scripts in `assets/`

| File | Purpose |
|---|---|
| `bible-tooltips.js`, `.css`, `bible-tooltips-meta.json`, `bible-tooltips-verses.json` | Hover tooltips for Bible references in posts (not in headings). |
| `search.js`, `search.css` | The search page. Same files as `mnet-shared/` in `michaelcoughlin.net`. |
| `post-grid.css` | Post card grid. Same file as in `michaelcoughlin.net`. |
| `pagination.js` | Client-side paging of the post list (20 per page, page taken from `#p=N` or `?p=N`). |
| `fix-pagination.js` | Draws a static pager that links only to `/page/N/` pages that exist in the crawl. |
| `force-pagination.js` | Forces pagination links that were left as `#` to navigate to the static page files. |
| `mobile-menu.js` | Mobile navigation toggle. |
