// In-page find overlay injected by PlaywrightEnvironment on Ctrl+F.
// The input is focused so the agent's follow-up type() + keypress(["Enter"])
// flow into it naturally. Enter walks text nodes, highlights all matches,
// scrolls to the current one, and shows N/M. Repeated Enter advances and
// wraps. Esc removes the overlay and clears highlights.
(() => {
  const ID = '__mui_find__';
  const HL_CLASS = '__mui_find_hl__';
  const HL_ACTIVE = '__mui_find_hl_active__';

  const EXISTING = document.getElementById(ID);
  if (EXISTING) { EXISTING.querySelector('input').focus(); return; }

  // Inject highlight styles once.
  if (!document.getElementById(ID + '_style')) {
    const style = document.createElement('style');
    style.id = ID + '_style';
    style.textContent =
      '.' + HL_CLASS + '{background:#ffe066;color:#000;border-radius:2px;'
        + 'box-shadow:0 0 0 1px #f59f00}'
      + '.' + HL_ACTIVE + '{background:#ff922b;color:#000;'
        + 'box-shadow:0 0 0 2px #d9480f}'
      + '#' + ID + ' input::placeholder{color:#e8eaed;opacity:1}'
      + '@keyframes __mui_find_caret_blink{50%{opacity:0}}'
      + '#' + ID + ' input::placeholder{'
        + 'animation:__mui_find_caret_blink 1s step-end infinite}';
    document.head.appendChild(style);
  }

  const wrap = document.createElement('div');
  wrap.id = ID;
  wrap.style.cssText = [
    'position:fixed', 'top:4px', 'right:8px', 'z-index:2147483647',
    'background:#3c4043', 'color:#e8eaed',
    'border-radius:4px', 'padding:4px 8px',
    'font:13px system-ui,-apple-system,Segoe UI,sans-serif',
    'box-shadow:0 2px 6px rgba(0,0,0,.25)',
    'display:flex', 'align-items:center', 'gap:8px',
  ].join(';');

  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = '|';
  input.style.cssText = [
    'width:180px', 'border:none', 'outline:none',
    'background:transparent', 'color:#e8eaed',
    'font:inherit', 'padding:2px 0',
  ].join(';');
  wrap.appendChild(input);

  const status = document.createElement('span');
  status.style.cssText = 'color:#9aa0a6;font-size:12px;min-width:32px;text-align:right';
  wrap.appendChild(status);

  const btnStyle = [
    'background:rgba(255,255,255,0.08)', 'border:1px solid rgba(255,255,255,0.15)',
    'color:#e8eaed', 'font:14px system-ui', 'cursor:pointer',
    'padding:6px 10px', 'border-radius:4px', 'line-height:1',
    'min-width:30px', 'min-height:28px', 'display:inline-flex',
    'align-items:center', 'justify-content:center',
  ].join(';');
  const prevBtn = document.createElement('button');
  prevBtn.type = 'button';
  prevBtn.textContent = '\u25B2';  // up triangle
  prevBtn.title = 'Previous match (Shift+Enter)';
  prevBtn.style.cssText = btnStyle;
  wrap.appendChild(prevBtn);
  const nextBtn = document.createElement('button');
  nextBtn.type = 'button';
  nextBtn.textContent = '\u25BC';  // down triangle
  nextBtn.title = 'Next match (Enter)';
  nextBtn.style.cssText = btnStyle;
  wrap.appendChild(nextBtn);
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.textContent = '\u2715';  // x
  closeBtn.title = 'Close (Escape)';
  closeBtn.style.cssText = btnStyle;
  wrap.appendChild(closeBtn);

  document.body.appendChild(wrap);
  input.focus();

  let lastQuery = null;
  let ranges = [];      // Range objects for all matches
  let spans = [];       // highlight <span> elements matching ranges
  let cursor = -1;

  function clearHighlights() {
    for (const span of spans) {
      const parent = span.parentNode;
      if (!parent) continue;
      while (span.firstChild) parent.insertBefore(span.firstChild, span);
      parent.removeChild(span);
      parent.normalize();
    }
    spans = [];
    ranges = [];
  }

  function collectMatches(q) {
    const needle = q.toLowerCase();
    const hits = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        if (!n.nodeValue) return NodeFilter.FILTER_REJECT;
        if (n.parentElement && n.parentElement.closest('#' + ID))
          return NodeFilter.FILTER_REJECT;
        if (n.parentElement && n.parentElement.closest('.' + HL_CLASS))
          return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let node;
    while ((node = walker.nextNode())) {
      const hay = node.nodeValue.toLowerCase();
      let i = 0;
      while ((i = hay.indexOf(needle, i)) !== -1) {
        hits.push({ node, offset: i });
        i += needle.length;
      }
    }
    return hits;
  }

  function highlightAll(hits, q) {
    // Process bottom-up per text node so earlier offsets remain valid.
    const byNode = new Map();
    for (const h of hits) {
      if (!byNode.has(h.node)) byNode.set(h.node, []);
      byNode.get(h.node).push(h.offset);
    }
    const newSpans = [];
    for (const [node, offsets] of byNode) {
      offsets.sort((a, b) => b - a);
      for (const off of offsets) {
        const range = document.createRange();
        range.setStart(node, off);
        range.setEnd(node, off + q.length);
        const span = document.createElement('span');
        span.className = HL_CLASS;
        range.surroundContents(span);
        newSpans.push(span);
      }
    }
    // Reorder in document order so cursor-advance matches visual reading.
    newSpans.sort((a, b) => {
      if (a === b) return 0;
      const pos = a.compareDocumentPosition(b);
      return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
    return newSpans;
  }

  function setActive(idx) {
    for (const s of spans) s.classList.remove(HL_ACTIVE);
    if (idx < 0 || idx >= spans.length) return;
    const span = spans[idx];
    span.classList.add(HL_ACTIVE);
    span.scrollIntoView({ block: 'center' });
  }

  function advance(direction) {
    const q = input.value;
    if (!q) {
      status.textContent = '';
      clearHighlights();
      return;
    }
    if (q !== lastQuery) {
      clearHighlights();
      lastQuery = q;
      const hits = collectMatches(q);
      if (hits.length === 0) {
        status.textContent = '0/0';
        return;
      }
      spans = highlightAll(hits, q);
      cursor = -1;
    }
    if (spans.length === 0) return;
    cursor = (cursor + direction + spans.length) % spans.length;
    setActive(cursor);
    status.textContent = (cursor + 1) + '/' + spans.length;
  }

  function close() {
    clearHighlights();
    wrap.remove();
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      advance(e.shiftKey ? -1 : 1);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  });
  prevBtn.addEventListener('click', () => { advance(-1); input.focus(); });
  nextBtn.addEventListener('click', () => { advance(1); input.focus(); });
  closeBtn.addEventListener('click', close);
})();
