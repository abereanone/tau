// Force navigation for pagination links to static page files.
document.addEventListener('click', function (e) {
  const a = e.target.closest && e.target.closest('a');
  if (!a) return;

  // handle anchors that were left as '#' or have pagination classes
  const pageAttr = a.getAttribute('data-page');
  const cls = a.className || '';

  let page = null;
  if (pageAttr && /\d+/.test(pageAttr)) page = parseInt(pageAttr, 10);
  else {
    const m = cls.match(/pagination-page-(\d+)/) || cls.match(/page-(\d+)/);
    if (m) page = parseInt(m[1], 10);
  }

  if (page) {
    const target = 'page/' + page + '/index.html';
    // navigate directly, stop other handlers
    e.preventDefault();
    e.stopImmediatePropagation();
    window.location.href = target;
  }
}, true);
