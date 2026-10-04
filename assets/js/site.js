/* Progressive enhancements; research content remains readable without JavaScript. */
(() => {
  "use strict";

  const normalize = (value) => String(value || "")
    .normalize("NFKC")
    .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/\s+/g, " ")
    .toLocaleLowerCase("ar")
    .trim();

  // Collapsing applies on small screens only. Desktop contents stay visible.
  const tocToggle = document.querySelector(".toc-toggle");
  const tocItems = document.getElementById(tocToggle?.getAttribute("aria-controls") || "toc-items");
  if (tocToggle && tocItems) {
    const mobileQuery = window.matchMedia("(max-width: 780px)");
    let expandedOnMobile = false;
    const updateToc = () => {
      const expanded = !mobileQuery.matches || expandedOnMobile;
      tocItems.hidden = !expanded;
      tocToggle.setAttribute("aria-expanded", String(expanded));
    };
    tocToggle.addEventListener("click", () => {
      expandedOnMobile = !expandedOnMobile;
      updateToc();
    });
    mobileQuery.addEventListener?.("change", updateToc);
    tocItems.addEventListener("click", (event) => {
      if (event.target.closest("a[href*='#']") && mobileQuery.matches) {
        expandedOnMobile = false;
        updateToc();
      }
    });
    updateToc();
  }

  // Indicate the section occupying the top reading area, without changing URLs.
  const tocLinks = [...document.querySelectorAll(".toc a[href*='#']")];
  const targetLinks = new Map();
  for (const link of tocLinks) {
    try {
      const url = new URL(link.href, location.href);
      if (url.pathname !== location.pathname) continue;
      const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (target) {
        targetLinks.set(target, link);
        if (target.matches("h3, h4")) link.classList.add("toc-subsection");
      }
    } catch (_) { /* An invalid optional anchor must not prevent other features. */ }
  }
  const markCurrent = (target) => {
    for (const link of targetLinks.values()) link.removeAttribute("aria-current");
    targetLinks.get(target)?.setAttribute("aria-current", "location");
  };
  if (targetLinks.size && "IntersectionObserver" in window) {
    const visible = new Set();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) visible.add(entry.target);
        else visible.delete(entry.target);
      }
      const nearest = [...visible].sort((a, b) =>
        Math.abs(a.getBoundingClientRect().top - 80) - Math.abs(b.getBoundingClientRect().top - 80))[0];
      if (nearest) markCurrent(nearest);
    }, { rootMargin: "-5% 0px -65% 0px", threshold: 0 });
    for (const target of targetLinks.keys()) observer.observe(target);
  }

  // Optional long inventory table filtering preserves every original record.
  const inventorySearch = document.getElementById("inventory-search");
  const inventoryTable = document.getElementById("inventory-table");
  if (inventorySearch && inventoryTable) {
    const rows = [...inventoryTable.querySelectorAll("tbody tr")];
    const prepared = rows.map((row) => ({ row, haystack: normalize(row.textContent) }));
    let count = document.getElementById("inventory-count");
    if (!count) {
      count = document.createElement("p");
      count.id = "inventory-count";
      count.className = "inventory-count";
      inventorySearch.closest(".inventory-controls")?.append(count);
    }
    count.setAttribute("role", "status");
    const filter = () => {
      const words = normalize(inventorySearch.value).split(" ").filter(Boolean);
      let visibleCount = 0;
      for (const entry of prepared) {
        const shown = words.every((word) => entry.haystack.includes(word));
        entry.row.hidden = !shown;
        if (shown) visibleCount++;
      }
      count.textContent = `المعروض: ${visibleCount.toLocaleString("ar")} من ${rows.length.toLocaleString("ar")} سجلًا`;
    };
    inventorySearch.addEventListener("input", filter);
    filter();
  }

  // Search-index records: {title, url, text|excerpt|content, type?}.
  // Relative record URLs are resolved relative to the JSON index URL.
  const search = document.getElementById("site-search");
  const results = document.getElementById("search-results");
  const indexPath = document.body.dataset.searchIndex;
  if (search && results && indexPath) {
    results.setAttribute("aria-live", "polite");
    results.setAttribute("aria-atomic", "true");
    let timer;
    let indexPromise;
    let requestNumber = 0;
    const indexUrl = new URL(indexPath, location.href);
    const message = (text) => {
      results.replaceChildren();
      const paragraph = document.createElement("p");
      paragraph.className = "search-message";
      paragraph.textContent = text;
      results.append(paragraph);
    };
    const getIndex = () => {
      if (!indexPromise) {
        indexPromise = fetch(indexUrl.href, { credentials: "same-origin" })
          .then((response) => {
            if (!response.ok) throw new Error("Search index unavailable");
            return response.json();
          })
          .then((data) => {
            const source = Array.isArray(data) ? data : (data.items || data.entries || []);
            return source.filter((item) => item?.title && item?.url).map((item) => {
              const body = item.text || item.excerpt || item.content || "";
              return { ...item, body: String(body), normalizedTitle: normalize(item.title), haystack: normalize(`${item.title} ${body}`) };
            });
          })
          .catch((error) => { indexPromise = null; throw error; });
      }
      return indexPromise;
    };
    const excerpt = (entry, words) => {
      const plain = entry.body.replace(/\s+/g, " ").trim();
      const normalized = normalize(plain);
      const position = normalized.indexOf(words[0]);
      // Normalization shifts offsets slightly; retain generous context.
      const start = Math.max(0, position > 0 ? position - 65 : 0);
      const text = plain.slice(start, start + 200);
      return `${start ? "… " : ""}${text}${start + 200 < plain.length ? " …" : ""}`;
    };
    const runSearch = async () => {
      const thisRequest = ++requestNumber;
      const query = normalize(search.value);
      if (query.length < 2) {
        results.replaceChildren();
        return;
      }
      const words = query.split(" ").filter(Boolean);
      message("جارٍ البحث في الفصول والملاحق…");
      try {
        const index = await getIndex();
        if (thisRequest !== requestNumber) return;
        const matches = index
          .filter((entry) => words.every((word) => entry.haystack.includes(word)))
          .map((entry) => ({ entry, score: (entry.normalizedTitle.includes(query) ? 5 : 0) + words.filter((word) => entry.normalizedTitle.includes(word)).length * 2 }))
          .sort((a, b) => b.score - a.score);
        results.replaceChildren();
        if (!matches.length) { message("لم تظهر نتائج لهذه الكلمات. جرّب كلمة أخرى أو عبارة أقصر."); return; }
        const total = document.createElement("p");
        total.className = "search-count";
        total.textContent = matches.length > 12
          ? `عُثر على ${matches.length.toLocaleString("ar")} نتيجة؛ تُعرض أول ١٢ نتيجة.`
          : `عُثر على ${matches.length.toLocaleString("ar")} نتيجة.`;
        results.append(total);
        const list = document.createElement("ul");
        for (const { entry } of matches.slice(0, 12)) {
          const url = new URL(entry.url, indexUrl);
          if (!["http:", "https:"].includes(url.protocol) || url.origin !== location.origin) continue;
          const item = document.createElement("li");
          if (entry.type) {
            const type = document.createElement("span");
            type.className = "result-type";
            type.textContent = entry.type;
            item.append(type);
          }
          const link = document.createElement("a");
          link.href = url.href;
          link.textContent = entry.title;
          item.append(link);
          if (entry.body) {
            const paragraph = document.createElement("p");
            paragraph.textContent = excerpt(entry, words);
            item.append(paragraph);
          }
          list.append(item);
        }
        results.append(list);
      } catch (_) {
        if (thisRequest === requestNumber) message("تعذّر تحميل فهرس البحث. يمكنك متابعة القراءة من فهرس الفصول.");
      }
    };
    search.addEventListener("input", () => {
      ++requestNumber;
      clearTimeout(timer);
      timer = setTimeout(runSearch, 180);
    });
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        search.value = "";
        ++requestNumber;
        results.replaceChildren();
      }
    });
    search.closest("form")?.addEventListener("submit", (event) => { event.preventDefault(); runSearch(); });
  }

  // Labels come from table captions or headers; keyboard users can scroll tables.
  for (const wrapper of document.querySelectorAll(".table-wrap")) {
    if (wrapper.scrollWidth <= wrapper.clientWidth) continue;
    if (!wrapper.hasAttribute("tabindex")) wrapper.tabIndex = 0;
    if (!wrapper.hasAttribute("role")) wrapper.setAttribute("role", "region");
    if (!wrapper.hasAttribute("aria-label") && !wrapper.hasAttribute("aria-labelledby")) {
      const caption = wrapper.querySelector("caption")?.textContent.trim();
      wrapper.setAttribute("aria-label", caption || "جدول قابل للتمرير الأفقي");
    }
  }
})();
