document.addEventListener('DOMContentLoaded', function () {
  const perPage = 20;
  const listEl = document.getElementById('posts-list');
  const pagerEl = document.getElementById('pagination');

  function getPageFromLocation() {
    // Check hash like #p=2 or #page=2
    const h = window.location.hash || '';
    const m = h.match(/p=(\d+)/) || h.match(/page=(\d+)/);
    if (m) return parseInt(m[1], 10);
    const params = new URLSearchParams(window.location.search);
    if (params.has('p')) return parseInt(params.get('p'), 10);
    if (params.has('page')) return parseInt(params.get('page'), 10);
    return 1;
  }

  function renderPage(posts, page) {
    listEl.innerHTML = '';
    const start = (page - 1) * perPage;
    const pagePosts = posts.slice(start, start + perPage);
    pagePosts.forEach(p => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = p.url;
      a.textContent = p.title || p.slug;
      li.appendChild(a);
      listEl.appendChild(li);
    });
    // update hash without adding history entries
    try { window.location.replace(window.location.pathname + window.location.search + '#p=' + page); } catch (e) {}
    // highlight active button
    Array.from(pagerEl.children).forEach(btn => {
      if (btn.dataset && parseInt(btn.dataset.page, 10) === page) btn.classList.add('active');
      else btn.classList.remove('active');
    });
  }

  function renderPager(posts) {
    pagerEl.innerHTML = '';
    const total = Math.ceil(posts.length / perPage) || 1;
    for (let i = 1; i <= total; i++) {
      const btn = document.createElement('button');
      btn.textContent = i;
      btn.dataset.page = i;
      btn.addEventListener('click', () => renderPage(posts, i));
      pagerEl.appendChild(btn);
    }
  }

  fetch('assets/posts.json')
    .then(r => r.json())
    .then(posts => {
      if (!Array.isArray(posts)) posts = [];
      renderPager(posts);
      const initial = getPageFromLocation() || 1;
      renderPage(posts, initial);
    })
    .catch(err => {
      listEl.innerHTML = '<li>Failed to load posts.json</li>';
      console.error(err);
    });
});
