# Things Above Us

Static mirror of the thingsabove.us blog (originally WordPress, captured with HTTrack), served by Cloudflare Pages. There is no build step: pushing to `main` publishes the repo root as it is, so **anything at the top level is public**. Do not put notes, logs or exports there.

## Layout

- One folder per post at the top level (`<slug>/index.html`), plus `category/`, `author/`, `page/N/` (home-page archive pages) and `search/`.
- `assets/` - site scripts and data (below). `wp-content/`, `wp-includes/` - mirrored theme, plugin and upload files.
- `_redirects` - Cloudflare Pages redirects. `404.html` - not-found page. `sitemap.xml` - generated.
- `go/links.json` - outside-link list for click counting (see "Outside links" below). Public on purpose: the go-links Worker reads it.

## Preview locally

```bash
python serve.py        # http://localhost:8082, opens a browser; unknown paths redirect to /
```

## Adding a post (the process)

1. Make `<slug>/index.html` by cloning a recent post by the same author that has no comments (these are full WordPress pages), then change the title, slug, `post-NNNN` id (next unused number), date, categories, featured image (`wp-content/uploads/YYYY/MM/name-1280x640.jpg`, plus `og:image`) and the content.
2. Run `python tools/add_post.py <slug>`. It reads the post and puts it on **every page that lists posts**: the home page and `/page/N/`, each `/category/<c>/` listing it is in, the author's `/author/<a>/` listing (all re-flowed 24 per page), `search/index.json`, and one `sitemap.xml` entry. Last, it runs `tools/go-links.mjs` so the post's outside links and share buttons are counted. Use `--dry-run` to see what it would do. Safe to re-run.
3. Check it on `python -m http.server`, then commit. Pushing to `main` is what publishes.
4. **Purge the Cloudflare cache** (dashboard > thingsabove.us > Caching > Purge Everything). A zone cache rule ("Cache at edge", 2 hours, overriding the origin) keeps the old home page, listings and CSS at the edge after a deploy, so the new post is invisible for up to two hours, and a hard refresh in the browser cannot help.

`add_post.py` deliberately does not run `generate_posts_json.py` (the committed `assets/posts.json` is ~150 posts behind; regenerate it as its own cleanup) or `gen-sitemap.mjs` (it stamps every URL with today's file time). Tag pages are not updated for new posts.

## Allen Nelson's Substack (automatic)

Allen Nelson's posts at cuatronelson.substack.com are copied here every night. The Windows task "TAU Substack Import" (23:00) runs `tools/substack-nightly.ps1`: for each Substack post not yet here it runs `tools/import_substack.py <slug>` (page cloned from `lessons-from-acts-5`, Substack date, cover as featured image, Substack widgets removed, then `add_post.py`), commits and pushes. Pages show within 2 hours (edge cache). It skips the night if the repo has uncommitted or unpushed work. Log: `%LOCALAPPDATA%\tau-substack\nightly.log`, `last-run.txt`; problems also pop up a Windows notice. By hand: `python tools/import_substack.py --list`, then `python tools/import_substack.py <slug>`.

Quote cards are not automatic: each imported post is listed in `C:/code/quote-cards/tau/needs-quotes.md`, and a Claude session picks 1-2 quotes, gets Michael's OK, then renders, uploads and rebuilds `/quotes/` (see `C:/code/quote-cards/static-pages.py`).

## Tools (run from the repo root after adding, removing or editing a post)

| Script | What it does |
|---|---|
| `tools/add_post.py` | Adds one new post to every listing (home, category, author), search and sitemap. See "Adding a post". |
| `tools/generate_posts_json.py` | Rewrites `assets/posts.json` from the post folders (any folder with an `index.html`, ignoring `wp-*`, `assets`, `page`, `author`). |
| `tools/generate_paginated_pages.py` | Rebuilds the home page and `/page/N/` archives from the post cards already in them (so titles, dates and featured images are kept); rewrites card links to root-absolute paths. |
| `assets/build-pages.ps1` | The PowerShell version of the same pagination rebuild, from metadata read out of every post. Use one or the other. |
| `tools/build_search_index.py` | Builds `search/index.json` (title, date, author, categories, image, text of every post) for the client-side search. |
| `tools/go-links.mjs` | Points every outside link (and share button) at `https://go.thingsabove.us/<name>` and updates `go/links.json`. Run by `add_post.py`; safe to re-run. Copy of `C:/code/go-links/go-links.mjs`. |
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

## Outside links (click counting)

Every link to another site, including the share buttons, points at `https://go.thingsabove.us/<name>`. The go-links Worker (`C:/code/go-links`) looks the name up in this site's `go/links.json` and redirects to the real address; Cloudflare logs each click, `C:/code/site-stats` archives them, and the site report shows "Links people followed". TAU uses the Worker rather than `/go/` rules in `_redirects` because it has about 6,000 distinct outside links and Pages allows 2,000 redirect rules. Give a link `data-no-go` to leave it alone.
