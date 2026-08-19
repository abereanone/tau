#!/usr/bin/env node
// Generates sitemap.xml for thingsabove.us.
//
// Run it locally from the repo root and commit the result:
//     node tools/gen-sitemap.mjs
//
// Deliberately NOT wired to a Cloudflare Pages build command. This project has no build
// step, so a deploy is a plain file copy and cannot fail; adding a build command would
// introduce a new way for the live site to break. Running locally also guarantees full
// git history for lastmod.
//
// Re-run whenever posts are added or removed.

import { readdirSync, statSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join, relative, sep } from "node:path";

const ORIGIN = "https://thingsabove.us";
const ROOT = process.cwd();
const OUT = join(ROOT, "sitemap.xml");

// Content pages only. WordPress taxonomy archives (category/tag/author) and the paged
// /page/N/ archives are thin, near-duplicate listings of content that is already in the
// sitemap through its own post URL, so they are skipped wholesale rather than filtered
// later. Matched by directory NAME at any depth, not just at the root.
const SKIP_DIRS = new Set([
  ".git",
  ".claude",       // worktrees here hold a second full copy of the site
  "node_modules",
  "tools",
  "wp-content",    // theme assets and attachment pages
  "wp-includes",   // js/css only
  "assets",
  "book",          // separate project, kept on its own branch — never part of the site
  "category",
  "tag",
  "author",
  "page",          // /page/2/ … paged archives
  "feed",          // RSS, not a page
  "comments",
]);

// Only directory indexes are real pages on this mirror. Every other .html at any depth is
// an HTTrack artifact of a query-string URL (index0a2a.html, index40d5-2.html, …), plus
// 404.html and all-posts.html — the latter has no canonical and nothing links to it.
const isPage = (name) => name === "index.html";

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(full, out);
    } else if (isPage(entry.name)) {
      out.push(relative(ROOT, full).split(sep).join("/"));
    }
  }
  return out;
}

// index.html -> /  ·  how-to-pray/index.html -> /how-to-pray/
// Trailing slash, matching how Cloudflare Pages serves a directory index: a request for
// /how-to-pray/index.html 308-redirects to /how-to-pray/, so listing the .html form would
// put a redirect in the sitemap.
function toUrl(rel) {
  if (rel === "index.html") return ORIGIN + "/";
  if (!rel.endsWith("/index.html")) {
    throw new Error(`unexpected page layout: ${rel} (expected <dir>/index.html)`);
  }
  return ORIGIN + "/" + rel.slice(0, -"index.html".length);
}

// Real per-file commit date. A sitemap where every lastmod is identical to the run time
// gets discounted by Google, so never fall back to "now" for a tracked file.
function lastmod(rel) {
  try {
    const out = execFileSync("git", ["log", "-1", "--format=%cI", "--", rel], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    if (out) return out;
  } catch {
    // git missing or not a repo; fall through to mtime
  }
  return statSync(join(ROOT, rel)).mtime.toISOString(); // uncommitted file
}

const xmlEscape = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
   .replace(/"/g, "&quot;").replace(/'/g, "&apos;");

const pages = walk(ROOT)
  .map((rel) => ({ rel, loc: toUrl(rel), lastmod: lastmod(rel) }))
  .sort((a, b) => a.loc.localeCompare(b.loc));

const seen = new Map();
for (const p of pages) {
  if (seen.has(p.loc)) throw new Error(`duplicate URL: ${p.loc} (${seen.get(p.loc)} and ${p.rel})`);
  seen.set(p.loc, p.rel);
}

const body = pages
  .map((p) => `  <url>\n    <loc>${xmlEscape(p.loc)}</loc>\n    <lastmod>${p.lastmod}</lastmod>\n  </url>`)
  .join("\n");

writeFileSync(
  OUT,
  `<?xml version="1.0" encoding="UTF-8"?>\n` +
  `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`,
  "utf8"
);

console.log(`sitemap.xml: ${pages.length} URLs`);
