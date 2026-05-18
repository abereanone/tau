# Rebuild all paginated listing pages from actual post metadata.
# Run from any directory. Outputs page/2..N/index.html and updates index.html.

param()
Set-StrictMode -Off
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Web

$root    = "C:\code\thingsabove.us"
$perPage = 90

# ── 1. Extract metadata from every post ──────────────────────────────────────
$postsJson = Get-Content "$root\assets\posts.json" -Raw | ConvertFrom-Json
Write-Host "Scanning $($postsJson.Count) post files..."

$posts = [System.Collections.Generic.List[object]]::new()

foreach ($p in $postsJson) {
    $file = Join-Path $root $p.url
    if (-not (Test-Path $file)) { continue }

    $html = [System.IO.File]::ReadAllText($file)

    # Title: h1.entry-title (may contain child tags — strip them)
    $m = [regex]::Match($html, '<h1[^>]*class="entry-title"[^>]*>([\s\S]*?)</h1>')
    $rawTitle = if ($m.Success) { $m.Groups[1].Value } else { $p.title }
    $title = [System.Web.HttpUtility]::HtmlDecode(([regex]::Replace($rawTitle, '<[^>]+>', '')).Trim())
    if (-not $title) { $title = $p.slug -replace '-', ' ' }

    # Date: first span.updated
    $m = [regex]::Match($html, '<span class="updated">([^<]+)</span>')
    $dateStr = if ($m.Success) { $m.Groups[1].Value.Trim() } else { '' }

    $date = [datetime]::MinValue
    if ($dateStr) { try { $date = [datetime]::Parse($dateStr) } catch {} }

    # Featured image: post-thumbnail header img
    $m = [regex]::Match($html, '<div class="post-thumbnail header">\s*<img\s+src="([^"]+)"', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    $img = if ($m.Success) { $m.Groups[1].Value -replace '^\.\.\/', '' } else { '' }

    $posts.Add([pscustomobject]@{
        slug    = $p.slug
        title   = $title
        date    = $date
        dateStr = $dateStr
        img     = $img
    })
}

$sorted = @($posts | Sort-Object -Property date -Descending)
$total  = $sorted.Count
$totalPages = [math]::Ceiling($total / $perPage)
Write-Host "  $total posts → $totalPages pages (newest: $($sorted[0].dateStr))"

# ── 2. Helper: article card HTML ──────────────────────────────────────────────
function Make-Card($post) {
    $href  = "$($post.slug)/index.html"
    $tenc  = [System.Web.HttpUtility]::HtmlEncode($post.title)

    $imgBlock = ''
    if ($post.img) {
        $imgBlock = "    <div class=`"header`"><a href=`"$href`" class=`"featured-image`"><img src=`"$($post.img)`" alt=`"$tenc`" /><span class=`"et_pb_extra_overlay`"></span></a></div>`n"
    }

    $dateBlock = ''
    if ($post.dateStr) {
        $dateBlock = "        <div class=`"post-meta vcard`"><p><span class=`"updated`">$($post.dateStr)</span></p></div>`n"
    }

    return "<article class=`"post`">`n${imgBlock}    <div class=`"post-content`">`n        <h2 class=`"post-title entry-title`"><a href=`"$href`">$tenc</a></h2>`n${dateBlock}        <div class=`"excerpt entry-summary`"><a class=`"read-more-button`" href=`"$href`">Read More</a></div>`n    </div>`n</article>"
}

# ── 3. Helper: pagination HTML ────────────────────────────────────────────────
function Make-Pagination($cur, $total) {
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine('<ul class="pagination">')
    if ($cur -gt 1) {
        $ph = if ($cur -eq 2) { '/' } else { "/page/$($cur-1)/index.html" }
        [void]$sb.AppendLine("<li class=`"prev static-arrow`"><a class=`"prev static-arrow`" href=`"$ph`"></a></li>")
    }
    for ($i = 1; $i -le $total; $i++) {
        $h   = if ($i -eq 1) { '/' } else { "/page/$i/index.html" }
        $cls = if ($i -eq $cur) { ' class="current"' } else { '' }
        [void]$sb.AppendLine("<li$cls><a href=`"$h`">$i</a></li>")
    }
    if ($cur -lt $total) {
        $nh = "/page/$($cur+1)/index.html"
        [void]$sb.AppendLine("<li class=`"next static-arrow`"><a class=`"next static-arrow`" href=`"$nh`"></a></li>")
    }
    [void]$sb.Append('</ul>')
    return $sb.ToString()
}

# ── 4. Helper: splice new content into template HTML ─────────────────────────
function Splice-Page($templateHtml, $pageNum, $articlesHtml, $paginationHtml) {
    $startMarker = '<div class="paginated_content">'
    $loaderMarker = '<span class="loader"'
    $ulMarker = '<ul class="pagination">'
    $ulEnd = '</ul>'

    $s1 = $templateHtml.IndexOf($startMarker)
    if ($s1 -lt 0) { throw "paginated_content not found" }

    $s2 = $templateHtml.IndexOf($loaderMarker, $s1)
    if ($s2 -lt 0) { throw "loader not found" }

    $s3 = $templateHtml.IndexOf($ulMarker, $s2)
    if ($s3 -lt 0) { throw "pagination ul not found" }

    $s4 = $templateHtml.IndexOf($ulEnd, $s3) + $ulEnd.Length

    $before = $templateHtml.Substring(0, $s1)
    $after  = $templateHtml.Substring($s4)

    $block = @"
<div class="paginated_content">
<div class="paginated_page paginated_page_${pageNum} active" data-columns>
$articlesHtml
</div>
</div>
<!-- /.paginated_content -->

<span class="loader"><img src="wp-content/themes/Extra/images/pagination-loading.gif" alt="Loading"/></span>

$paginationHtml
"@

    return $before + $block + $after
}

# ── 5. Load templates ─────────────────────────────────────────────────────────
$homeTpl  = [System.IO.File]::ReadAllText("$root\index.html")
$page2Tpl = [System.IO.File]::ReadAllText("$root\page\2\index.html")

# ── 6. Build each page ────────────────────────────────────────────────────────
for ($pg = 1; $pg -le $totalPages; $pg++) {
    $s       = ($pg - 1) * $perPage
    $e       = [math]::Min($s + $perPage - 1, $total - 1)
    $pagePosts = $sorted[$s..$e]

    $cards      = ($pagePosts | ForEach-Object { Make-Card $_ }) -join "`n"
    $pagination = Make-Pagination $pg $totalPages

    if ($pg -eq 1) {
        $html = Splice-Page $homeTpl 1 $cards $pagination
        [System.IO.File]::WriteAllText("$root\index.html", $html, [System.Text.Encoding]::UTF8)
        Write-Host "  page 1 → index.html ($($pagePosts.Count) posts)"
    } else {
        $dir = "$root\page\$pg"
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

        $tpl  = $page2Tpl -replace 'data-current_page="[^"]*"', "data-current_page=`"$pg`""
        $html = Splice-Page $tpl $pg $cards $pagination
        [System.IO.File]::WriteAllText("$dir\index.html", $html, [System.Text.Encoding]::UTF8)
        Write-Host "  page $pg → page\$pg\index.html ($($pagePosts.Count) posts)"
    }
}

# ── 7. Update fix-pagination.js ───────────────────────────────────────────────
$jsLines = @("    { label: '1', href: '/' },")
for ($i = 2; $i -le $totalPages; $i++) {
    $jsLines += "    { label: '$i', href: '/page/$i/index.html' },"
}
$pagesBlock = $jsLines -join "`n"

$fixPag = [System.IO.File]::ReadAllText("$root\assets\fix-pagination.js")
$fixPag = [regex]::Replace($fixPag, '(?s)var pages = \[.*?\];', "var pages = [`n$pagesBlock`n  ];")
[System.IO.File]::WriteAllText("$root\assets\fix-pagination.js", $fixPag, [System.Text.Encoding]::UTF8)
Write-Host "  fix-pagination.js updated with $totalPages pages"

Write-Host "`nDone. $totalPages pages built."
