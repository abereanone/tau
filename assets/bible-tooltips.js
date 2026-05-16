(function () {
  const scriptUrl = document.currentScript && document.currentScript.src
    ? document.currentScript.src
    : "";
  const metaUrl = new URL("bible-tooltips-meta.json", scriptUrl || window.location.href);
  const versesUrl = new URL("bible-tooltips-verses.json", scriptUrl || window.location.href);
  const skipTags = new Set(["A", "SCRIPT", "STYLE", "TEXTAREA", "INPUT", "SELECT", "OPTION", "CODE", "PRE"]);
  let metaPromise;
  let versesPromise;
  let referenceRegex;
  let bookMap = {};
  let singleChapterBooks = new Set();

  function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function normalizeLeadingRomanNumeral(value) {
    return value.replace(/^(iii|ii|i)\s+/i, (match) => {
      const numeral = match.trim().toLowerCase();
      if (numeral === "i") return "1 ";
      if (numeral === "ii") return "2 ";
      if (numeral === "iii") return "3 ";
      return match;
    });
  }

  function normalizeBookKey(book) {
    return normalizeLeadingRomanNumeral(String(book || ""))
      .replace(/\./g, "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function toBookPattern(book) {
    let pattern = escapeRegex(book).replace(/\s+/g, "\\s+");
    pattern = pattern
      .replace(/^1(?=\\s\+)/, "(?:1|i)")
      .replace(/^2(?=\\s\+)/, "(?:2|ii)")
      .replace(/^3(?=\\s\+)/, "(?:3|iii)")
      .replace(/^1(?=[a-z])/, "(?:1|i)")
      .replace(/^2(?=[a-z])/, "(?:2|ii)")
      .replace(/^3(?=[a-z])/, "(?:3|iii)");
    if (/[a-z]$/i.test(book)) pattern += "\\.?";
    return pattern;
  }

  function getMeta() {
    if (!metaPromise) {
      metaPromise = fetch(metaUrl)
        .then((response) => response.json())
        .then((data) => {
          bookMap = data.bookMap || {};
          singleChapterBooks = new Set(data.singleChapterBooks || []);
          const bookPattern = Object.keys(bookMap)
            .sort((a, b) => b.length - a.length)
            .map(toBookPattern)
            .join("|");
          referenceRegex = new RegExp(
            "\\b(" + bookPattern + ")\\s+(\\d+(?::\\d+(?:[-\\u2013\\u2014]\\d+)?(?:\\s*,\\s*(?:\\d+:)?\\d+(?:[-\\u2013\\u2014]\\d+)?)*)?|\\d+(?:[-\\u2013\\u2014]\\d+)?(?:\\s*,\\s*\\d+(?:[-\\u2013\\u2014]\\d+)?)*)\\b",
            "gi"
          );
          return data;
        });
    }
    return metaPromise;
  }

  function getVerses() {
    if (!versesPromise) {
      versesPromise = fetch(versesUrl).then((response) => response.json());
    }
    return versesPromise;
  }

  function normalizeReference(reference) {
    const match = String(reference || "")
      .trim()
      .replace(/\u2013|\u2014/g, "-")
      .match(/^((?:(?:[1-3]|iii|ii|i)\s+)?[a-z.]+(?:\s+[a-z.]+)*)\s+(.+)$/i);
    if (!match) return "";
    const bookCode = bookMap[normalizeBookKey(match[1])];
    if (!bookCode) return "";
    let chapterAndVerse = String(match[2] || "").trim();
    if (singleChapterBooks.has(bookCode) && !chapterAndVerse.includes(":")) {
      chapterAndVerse = "1:" + chapterAndVerse;
    }
    if (/^\d+$/.test(chapterAndVerse) && !singleChapterBooks.has(bookCode)) {
      return "";
    }
    return bookCode + " " + chapterAndVerse.toLowerCase();
  }

  function segmentKeys(bookCode, chapter, segment) {
    const qualified = String(segment).trim().match(/^(\d+):(.+)$/);
    if (qualified) {
      return segmentKeys(bookCode, Number(qualified[1]), qualified[2]);
    }
    const range = String(segment).trim().match(/^(\d+)(?:-(\d+))?$/);
    if (!range || !chapter) return [];
    const start = Number(range[1]);
    const end = Number(range[2] || range[1]);
    const low = Math.min(start, end);
    const high = Math.max(start, end);
    const keys = [];
    for (let verse = low; verse <= high && keys.length < 80; verse += 1) {
      keys.push(bookCode + " " + chapter + ":" + verse);
    }
    return keys;
  }

  function resolveVerseText(reference, data) {
    const normalized = normalizeReference(reference);
    const match = normalized.match(/^([1-3]?[a-z]+)\s+(\d+):(.+)$/);
    if (!match) return "Verse not found.";
    const bookCode = match[1];
    const chapter = Number(match[2]);
    const segments = match[3].split(",").map((part) => part.trim()).filter(Boolean);
    const parts = [];
    segments.forEach((segment) => {
      segmentKeys(bookCode, chapter, segment).forEach((key) => {
        const verse = data.verses && data.verses[key];
        if (verse) {
          parts.push(key.replace(/^[a-z0-9]+\s+/, "") + " " + verse);
        }
      });
    });
    return parts.length ? parts.join(" ") + " (" + (data.version || "BSB") + ")" : "Verse not found.";
  }

  function shouldSkip(node) {
    for (let current = node.parentElement; current; current = current.parentElement) {
      if (skipTags.has(current.tagName) || current.classList.contains("bible-ref")) return true;
    }
    return false;
  }

  function linkTextNode(node) {
    const text = node.nodeValue;
    if (!text || !referenceRegex.test(text)) {
      referenceRegex.lastIndex = 0;
      return;
    }
    referenceRegex.lastIndex = 0;
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    let match;
    while ((match = referenceRegex.exec(text))) {
      if (match.index > cursor) fragment.append(document.createTextNode(text.slice(cursor, match.index)));
      const span = document.createElement("span");
      span.className = "bible-ref";
      span.tabIndex = 0;
      span.dataset.ref = match[0];
      span.textContent = match[0];
      fragment.append(span);
      cursor = match.index + match[0].length;
    }
    if (cursor < text.length) fragment.append(document.createTextNode(text.slice(cursor)));
    node.parentNode.replaceChild(fragment, node);
  }

  function enhanceReference(element) {
    if (element.dataset.bibleTooltipState) return;
    element.dataset.bibleTooltipState = "ready";
    const show = () => {
      element.__bibleTooltipActive = true;
      ensureTooltip(element);
    };
    const hide = () => {
      element.__bibleTooltipActive = false;
      if (element.__bibleTooltip) element.__bibleTooltip.style.display = "none";
    };
    element.addEventListener("mouseenter", show);
    element.addEventListener("focus", show);
    element.addEventListener("mouseleave", hide);
    element.addEventListener("blur", hide);
  }

  function positionTooltip(anchor, tooltip) {
    const rect = anchor.getBoundingClientRect();
    tooltip.style.visibility = "hidden";
    tooltip.style.display = "block";
    let left = rect.left + window.scrollX;
    const width = tooltip.offsetWidth;
    if (left + width > window.innerWidth - 16) left = window.innerWidth - width - 16;
    if (left < 16) left = 16;
    tooltip.style.left = left + "px";
    tooltip.style.top = rect.bottom + window.scrollY + 8 + "px";
    tooltip.style.visibility = "visible";
    tooltip.style.display = anchor.__bibleTooltipActive ? "block" : "none";
  }

  function ensureTooltip(element) {
    if (element.__bibleTooltip) {
      positionTooltip(element, element.__bibleTooltip);
      return;
    }
    getVerses().then((data) => {
      const tooltip = document.createElement("div");
      tooltip.className = "bible-tooltip";
      tooltip.textContent = resolveVerseText(element.dataset.ref, data);
      document.body.appendChild(tooltip);
      element.__bibleTooltip = tooltip;
      positionTooltip(element, tooltip);
    }).catch(() => {});
  }

  function scanScope(scope) {
    if (scope.dataset.bibleProcessed === "true") return;
    scope.dataset.bibleProcessed = "true";
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return shouldSkip(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(linkTextNode);
    scope.querySelectorAll(".bible-ref").forEach(enhanceReference);
  }

  function init() {
    getMeta().then(() => {
      document
        .querySelectorAll(".post-content, .entry-content, article")
        .forEach(scanScope);
    }).catch(() => {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
