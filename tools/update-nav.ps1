$rootPath = "c:\temp\tau\thingsabove.us"
$files = Get-ChildItem -Path $rootPath -Recurse -Filter "index.html"
$updated = 0; $skipped = 0

# Sticky CSS injected before </head>
$stickyCSS = '<style id="tau-mods">#main-header-wrapper{position:sticky!important;top:0!important;z-index:99999!important;}</style>'

# Search box <li> - added as last item in nav
$searchLi = @'
                  <li class="menu-item tau-search-item" style="display:flex;align-items:center;">
                    <form style="display:flex;align-items:center;margin:0;" onsubmit="window.open('https://www.google.com/search?q=site%3Athingsabove.us+'+encodeURIComponent(this.querySelector('input').value),'_blank');return false;">
                      <input type="search" placeholder="Search&#x2026;" style="padding:3px 7px;border:1px solid rgba(255,255,255,0.4);border-right:none;border-radius:3px 0 0 3px;font-size:12px;height:26px;background:rgba(255,255,255,0.15);color:#fff;outline:none;width:110px;" />
                      <button type="submit" style="padding:0 8px;background:rgba(255,255,255,0.15);color:#fff;border:1px solid rgba(255,255,255,0.4);border-left:none;border-radius:0 3px 3px 0;height:26px;cursor:pointer;font-size:14px;">&#x1F50D;</button>
                    </form>
                  </li>
'@

# Abolition Resources <li> for inside Books sub-menu (indented one level deeper)
$abolitionSubLi = @'
                      <li
                        id="menu-item-16541"
                        class="menu-item menu-item-type-custom menu-item-object-custom menu-item-16541"
                      >
                        <a
                          href="https://heritagerestored.org/resources/"
                          target="_blank"
                          >Abolition Resources</a
                        >
                      </li>

'@

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)

    # Normalize CRLF → LF so all string matches work consistently
    $content = $content.Replace("`r`n", "`n")

    # Skip already-updated files
    if ($content.Contains('tau-search-item')) { $skipped++; continue }
    # Skip files with no nav
    if (-not $content.Contains('<ul id="et-menu" class="nav">')) { $skipped++; continue }

    # Determine path prefix: post pages use ../ for local links
    $prefix = if ($content.Contains('href="../beforethethrone/')) { '../' } else { '' }

    # ── 1. Add Home link before Books/Resources ──────────────────────────
    $homeTarget = "<ul id=`"et-menu`" class=`"nav`">`n                  <li`n                    id=`"menu-item-14772`""
    $homeReplacement = "<ul id=`"et-menu`" class=`"nav`">`n                  <li`n                    class=`"menu-item menu-item-type-custom menu-item-object-custom`"`n                  >`n                    <a href=`"${prefix}index.html`">Home</a>`n                  </li>`n                  <li`n                    id=`"menu-item-14772`""
    $content = $content.Replace($homeTarget, $homeReplacement)

    # ── 2. Add Abolition Resources into Books sub-menu (after Our Tract) ─
    # Root variant: <a href="our-tract/index.html">Our Tract</a>
    # Post variant: <a href="../our-tract/index.html">Our Tract</a>
    $ourTractClose = "href=`"${prefix}our-tract/index.html`">Our Tract</a>`n                      </li>`n                    </ul>"
    $ourTractWithAbolition = "href=`"${prefix}our-tract/index.html`">Our Tract</a>`n                      </li>`n" + $abolitionSubLi + "                    </ul>"
    $content = $content.Replace($ourTractClose, $ourTractWithAbolition)

    # ── 3. Remove Abolition Resources from top-level nav ─────────────────
    # This block is identical in both variants (uses absolute URL)
    $topAbolition = "                  <li`n                    id=`"menu-item-16541`"`n                    class=`"menu-item menu-item-type-custom menu-item-object-custom menu-item-16541`"`n                  >`n                    <a`n                      href=`"https://heritagerestored.org/resources/`"`n                      target=`"_blank`"`n                      >Abolition Resources</a`n                    >`n                  </li>`n"
    $content = $content.Replace($topAbolition, "")

    # ── 4. Add search box before the closing </ul> of the main nav ───────
    # Target the mobile nav div which immediately follows the nav </ul>
    $navCloseTarget = "                </ul>`n                <div id=`"et-mobile-navigation`""
    $navCloseReplacement = $searchLi + "                </ul>`n                <div id=`"et-mobile-navigation`""
    $content = $content.Replace($navCloseTarget, $navCloseReplacement)

    # ── 5. Make header sticky (inject CSS before </head>) ────────────────
    $content = $content.Replace('</head>', $stickyCSS + "`n  </head>")

    [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.Encoding]::UTF8)
    $updated++
}

Write-Host "Done. Updated: $updated | Skipped: $skipped"
