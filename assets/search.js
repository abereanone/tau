// Site search: loads search/index.json (built by tools/build_search_index.py) and searches
// every post in the browser. No server, no outside service.
//
// The <script> tag carries two attributes:
//   data-index  URL of index.json
//   data-root   prefix from this page to the site root ("/" or "../")
(function () {
  var script = document.currentScript;
  var INDEX_URL = script.getAttribute("data-index");
  var ROOT = script.getAttribute("data-root") || "/";
  var PAGE = 24;

  var form = document.getElementById("site-search-form");
  var input = document.getElementById("site-search-q");
  var status = document.getElementById("site-search-status");
  var results = document.getElementById("site-search-results");
  var more = document.getElementById("site-search-more");
  if (!form || !input || !results) return;

  var posts = null; // [url, title, iso_date, author, categories, image, text, _haystack]
  var matches = [];
  var shown = 0;
  var terms = [];

  function fold(s) {
    return s.toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
  }

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  var STOP = { a: 1, an: 1, and: 1, the: 1, of: 1, to: 1, in: 1, is: 1, it: 1, on: 1, or: 1, for: 1, by: 1, at: 1 };

  // "exact phrase" stays together; other words must all appear somewhere in the post
  function parse(q) {
    var out = [];
    q = fold(q).replace(/"([^"]+)"/g, function (_, phrase) {
      phrase = phrase.trim();
      if (phrase) out.push(phrase);
      return " ";
    });
    q.split(/[^\w'À-ɏ-]+/).forEach(function (w) {
      w = w.replace(/^['-]+|['-]+$/g, "");
      if (w.length > 1 && !STOP[w]) out.push(w);
    });
    if (!out.length) {
      var w = fold(q).trim();
      if (w) out.push(w);
    }
    return out;
  }

  function count(hay, term) {
    var n = 0, i = hay.indexOf(term);
    while (i !== -1 && n < 20) { n++; i = hay.indexOf(term, i + term.length); }
    return n;
  }

  function search(q) {
    terms = parse(q);
    var whole = fold(q).replace(/"/g, "").trim();
    matches = [];
    if (!terms.length) return;
    posts.forEach(function (p) {
      var title = fold(p[1]), meta = fold(p[3] + " " + p[4].join(" ")), hay = p[7];
      var score = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i];
        var inTitle = title.indexOf(t) !== -1, inMeta = meta.indexOf(t) !== -1, n = count(hay, t);
        if (!inTitle && !inMeta && !n) return; // every term must match
        score += (inTitle ? 10 : 0) + (inMeta ? 4 : 0) + n;
      }
      if (whole.length > 3 && terms.length > 1) {
        if (title.indexOf(whole) !== -1) score += 20;
        else if (hay.indexOf(whole) !== -1) score += 5;
      }
      matches.push([score, p]);
    });
    matches.sort(function (a, b) { return b[0] - a[0] || (b[1][2] > a[1][2] ? 1 : b[1][2] < a[1][2] ? -1 : 0); });
  }

  function highlight(text) {
    var out = esc(text);
    terms.forEach(function (t) {
      var re = new RegExp("(" + esc(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
      out = out.replace(re, "<mark>$1</mark>");
    });
    return out;
  }

  function snippet(p) {
    var text = p[6], lower = text.toLowerCase(), at = -1;
    terms.forEach(function (t) {
      var i = lower.indexOf(t);
      if (i !== -1 && (at === -1 || i < at)) at = i;
    });
    var start = Math.max(0, at - 80);
    if (start > 0) start = text.indexOf(" ", start) + 1;
    var s = text.substr(start, 220);
    var cut = s.lastIndexOf(" ");
    if (start + 220 < text.length && cut > 150) s = s.slice(0, cut);
    return (start > 0 ? "…" : "") + highlight(s) + (start + s.length < text.length ? "…" : "");
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function date(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    return m ? MONTHS[+m[2] - 1] + " " + (+m[3]) + ", " + m[1] : "";
  }

  function card(p) {
    var href = ROOT + p[0] + (ROOT === "/" ? "" : "index.html");
    var img = p[5] ? '<div class="header"><a href="' + href + '" class="featured-image"><img src="' + ROOT + esc(p[5]) +
      '" alt="" loading="lazy" /><span class="et_pb_extra_overlay"></span></a></div>' : "";
    var byline = [date(p[2]), esc(p[3])].filter(Boolean).join(" · ");
    return '<article class="post">' + img + '<div class="post-content">' +
      '<h2 class="post-title entry-title"><a href="' + href + '">' + highlight(p[1]) + "</a></h2>" +
      '<div class="post-meta vcard"><p><span class="updated">' + byline + "</span></p></div>" +
      '<div class="excerpt entry-summary"><p class="site-search-snippet">' + snippet(p) + "</p></div></div></article>";
  }

  function render(reset) {
    if (reset) { results.innerHTML = ""; shown = 0; }
    var next = matches.slice(shown, shown + PAGE);
    results.insertAdjacentHTML("beforeend", next.map(function (m) { return card(m[1]); }).join(""));
    shown += next.length;
    if (more) more.hidden = shown >= matches.length;
  }

  function run(q, push) {
    q = q.trim();
    input.value = q;
    if (push !== false) {
      var url = location.pathname + (q ? "?q=" + encodeURIComponent(q) : "");
      history.replaceState(null, "", url);
    }
    if (!q) { results.innerHTML = ""; status.textContent = ""; if (more) more.hidden = true; return; }
    search(q);
    status.textContent = matches.length
      ? matches.length + (matches.length === 1 ? " post matches " : " posts match ") + "“" + q + "”"
      : "No posts match “" + q + "”. Try fewer or different words.";
    render(true);
  }

  function load() {
    if (posts) return Promise.resolve();
    status.textContent = "Loading the search index…";
    return fetch(INDEX_URL).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (data) {
      data.forEach(function (p) { p[7] = fold(p[6]); });
      posts = data;
    });
  }

  function start(q, push) {
    load().then(function () { run(q, push); }, function () {
      status.textContent = "Sorry, the search index could not be loaded.";
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    start(input.value);
  });
  if (more) more.addEventListener("click", function () { render(false); });

  var initial = new URLSearchParams(location.search).get("q") || "";
  if (initial) start(initial, false);
  else input.focus();
})();
