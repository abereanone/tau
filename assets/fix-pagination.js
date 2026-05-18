// Static pagination — only links to pages that actually exist in the crawl.
// Uses absolute paths so this works from any directory depth.
(function(){
  var pages = [
    { label: '1', href: '/' },
    { label: '2', href: '/page/2/index.html' },
    { label: '3', href: '/page/3/index.html' },
    { label: '4', href: '/page/4/index.html' },
    { label: '5', href: '/page/5/index.html' },
    { label: '6', href: '/page/6/index.html' },
    { label: '7', href: '/page/7/index.html' },
    { label: '8', href: '/page/8/index.html' },
  ];

  function currentPage() {
    var p = window.location.pathname.replace(/\/+$/, '') || '/';
    for (var i = 0; i < pages.length; i++) {
      var h = pages[i].href.replace(/\/+$/, '') || '/';
      if (p === h || p + '/index.html' === h || p === h.replace('/index.html','')) return i;
    }
    return -1;
  }

  function buildHtml() {
    var cur = currentPage();
    var html = '';
    var prev = cur > 0 ? pages[cur - 1] : null;
    var next = cur >= 0 && cur < pages.length - 1 ? pages[cur + 1] : null;
    if (prev) html += '<li class="prev static-arrow"><a class="prev static-arrow" href="' + prev.href + '"></a></li>';
    for (var i = 0; i < pages.length; i++) {
      var cls = (i === cur) ? ' class="current"' : '';
      html += '<li' + cls + '><a href="' + pages[i].href + '">' + pages[i].label + '</a></li>';
    }
    if (next) html += '<li class="next static-arrow"><a class="next static-arrow" href="' + next.href + '"></a></li>';
    return html;
  }

  function replaceAll() {
    document.querySelectorAll('ul.pagination').forEach(function(ul) {
      var fresh = buildHtml();
      if (ul.dataset.tau !== fresh) {
        ul.innerHTML = fresh;
        ul.dataset.tau = fresh;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ replaceAll(); setTimeout(replaceAll, 500); });
  } else {
    replaceAll(); setTimeout(replaceAll, 500);
  }

  var mo = new MutationObserver(replaceAll);
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
