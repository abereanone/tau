# Sitemap Activity

Working notes for this repo, part of a sitemap + Google Search Console rollout across all of
the owner's sites. **The master checklist lives at `c:\code\sitemaptasks.md`** — this file
covers only this repo.

> This file is intentionally **untracked**. It's working notes, not part of the site. Watch out
> for `git add -A` sweeping it into a commit; add it deliberately if you decide you want it in
> the repo.

_Last updated 2026-08-18._

## This repo

**Site:** https://thingsabove.us · static HTML (HTTrack mirror of the old WordPress site), Cloudflare Pages via GitHub. No build step.

## Status: soft-404 fix done, sitemap still to build

Branch **`fix-soft-404`**, 1 commit `d98fd29` — "Add a 404 page so missing paths return a 404".

### What changed and why
Cloudflare Pages serves the root `index.html` **with a 200** for any unmatched path when a project
has no `404.html`. This repo had none, so **every missing URL answered 200 with the home page**.

That misreports the site to crawlers: Search Console can't tell a missing page from a real one, a
mistyped sitemap URL reports as a parse error rather than "not found", and junk URLs become
indexable. Added a self-contained, `noindex` `404.html` styled to the site. No dashboard change —
Pages picks it up automatically.

### Verify after pushing
`curl -sI https://thingsabove.us/definitely-missing-xyz` → **404**, not 200.

## ⬜ Remaining work: the sitemap (Tier 3)

Not built yet. The agreed approach — **option (a)** — is:

- Add `tools/gen-sitemap.mjs` to this repo. It walks the folder for `.html` files, skips the junk
  (`404.html`, HTTrack leftovers, pagination stubs), and writes `sitemap.xml`.
- **The owner runs it locally and commits the result.** Deliberately *not* wired to a Cloudflare
  Pages build command: these projects currently have no build step, so a deploy is just a file
  copy and **cannot fail**. Adding a build command would introduce a new way for a live site to
  break. Running locally also guarantees full git history for `lastmod`.
- `lastmod` comes from `git log -1 --format=%cI <file>` — real per-file commit dates.
- Add a `Sitemap:` line to `robots.txt`.

This replaces `c:\code\makeSiteMap.py`, which is hardcoded to `C:\temp\FTS\…`, stamps every URL
with the same run-time `lastmod` (Google discounts a sitemap where every date is identical), emits
`.html` URLs where the canonicals are extensionless, and filters nothing.

**Once built, this site needs the script run manually whenever pages are added.**

## ⚠️ Note on the working tree
There is an untracked **`book/`** directory here that is not mine. I committed only `404.html`.
Don't let `git add -A` sweep it in unintentionally.

---

## Project-wide conventions (apply here too)

- **Never push.** Changes are committed on a branch; the owner reviews and pushes.
- Search Console uses **domain properties** (11 total across all sites), verified by DNS TXT.
- Every site gets a `robots.txt` with a `Sitemap:` line. Confirmed that a repo `public/robots.txt`
  surfaces live even though Cloudflare serves a managed Content Signals robots.txt on these zones.
- Cloudflare Pages serves the root `index.html` **with a 200** for unmatched paths when a project
  has no `404.html`. Several sites had this soft-404 problem; the fix is simply adding `404.html`.
