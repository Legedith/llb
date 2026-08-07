(() => {
  'use strict';
  const PREFIX = '/llb/';
  const STORE = 'du-llb-case-catalogue-v2';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const norm = value => String(value || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, ' ').replace(/[^a-z0-9§. -]+/g, ' ').replace(/\s+/g, ' ').trim();
  let local = { bookmarks: [], compare: [] };
  try { local = { ...local, ...JSON.parse(localStorage.getItem(STORE) || '{}') }; } catch (_) {}
  const save = () => localStorage.setItem(STORE, JSON.stringify(local));
  const toggle = (list, id, max = Infinity) => {
    const at = list.indexOf(id);
    if (at >= 0) { list.splice(at, 1); return false; }
    if (list.length >= max) list.shift();
    list.push(id); return true;
  };
  const toast = message => {
    const el = $('caseToast'); if (!el) return;
    el.textContent = message; el.classList.add('show');
    clearTimeout(window.__caseToast); window.__caseToast = setTimeout(() => el.classList.remove('show'), 2200);
  };
  const statusLabel = value => String(value || 'verification-needed').replace(/-/g, ' ');
  const caseUrl = id => `${PREFIX}cases/${encodeURIComponent(id)}/`;
  const subjectUrl = id => `${PREFIX}subjects/${encodeURIComponent(id)}/cases/`;
  const nodeUrl = id => `${PREFIX}nodes/${encodeURIComponent(id)}/`;

  async function loadCases() {
    const response = await fetch(`${PREFIX}data/cases-full.json`, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`Case data returned ${response.status}`);
    return response.json();
  }

  function card(c) {
    const subjects = (c.subjects || []).slice(0, 3).map(s => `<a href="${subjectUrl(s.id)}">${esc(s.code)}</a>`).join('');
    const roles = (c.roles || []).slice(0, 2).map(r => `<span>${esc(statusLabel(r))}</span>`).join('');
    return `<article class="catalogue-case-card">
      <div class="badges"><span class="badge treatment">${esc(statusLabel(c.treatment?.status))}</span><span class="badge source">${esc(c.sourceStatusLabel)}</span></div>
      <span class="meta">${esc(c.year || 'Year to verify')} · ${esc(c.court)} · ${esc(c.citation || 'Citation to verify')}</span>
      <h3><a href="${caseUrl(c.id)}">${esc(c.title)}</a></h3>
      <p class="holding">${esc(c.holding)}</p><p>${esc(c.significance)}</p>
      <div class="chip-row">${subjects}${roles}</div>
      <div class="card-actions"><a href="${caseUrl(c.id)}">Open case guide</a><button type="button" data-compare="${esc(c.id)}">${local.compare.includes(c.id) ? 'Remove' : 'Compare'}</button></div>
    </article>`;
  }

  async function initCatalogue() {
    const all = await loadCases();
    let shown = 48, filtered = [];
    const ids = ['caseSearch','courtFilter','subjectFilter','roleFilter','treatmentFilter','decadeFilter','caseSort'];
    const render = reset => {
      const q = norm($('caseSearch')?.value); const terms = q.split(' ').filter(Boolean);
      const court = $('courtFilter')?.value || '', subject = $('subjectFilter')?.value || '';
      const role = $('roleFilter')?.value || '', treatment = $('treatmentFilter')?.value || '';
      const decade = Number($('decadeFilter')?.value || 0), sort = $('caseSort')?.value || 'relevance';
      filtered = all.map(c => {
        if (court && c.court !== court) return null;
        if (subject && !(c.subjects || []).some(s => s.id === subject)) return null;
        if (role && !(c.roles || []).includes(role)) return null;
        if (treatment && c.treatment?.status !== treatment) return null;
        if (decade && (Number(c.year) < decade || Number(c.year) >= decade + 10)) return null;
        const hay = norm(c.search); if (terms.length && !terms.every(t => hay.includes(t))) return null;
        let score = 0;
        if (q) { if (norm(c.title) === q) score += 100; if (norm(c.title).startsWith(q)) score += 50;
          terms.forEach(t => { if (norm(c.title).includes(t)) score += 12; if (norm(c.holding).includes(t)) score += 8; if ((c.links || []).some(l => norm(l.nodeTitle).includes(t))) score += 6; }); }
        return { c, score };
      }).filter(Boolean);
      filtered.sort((a,b) => sort === 'newest' ? Number(b.c.year)-Number(a.c.year) || a.c.title.localeCompare(b.c.title)
        : sort === 'oldest' ? Number(a.c.year)-Number(b.c.year) || a.c.title.localeCompare(b.c.title)
        : sort === 'title' ? a.c.title.localeCompare(b.c.title)
        : b.score-a.score || Number(b.c.year)-Number(a.c.year) || a.c.title.localeCompare(b.c.title));
      if (reset) shown = 48;
      paint();
    };
    const paint = () => {
      $('caseResults').innerHTML = filtered.slice(0, shown).map(({c}) => card(c)).join('') || '<div class="empty-state">No case matches these filters.</div>';
      $('caseResultCount').textContent = `${filtered.length.toLocaleString('en-IN')} result${filtered.length === 1 ? '' : 's'}`;
      const more = $('loadMoreCases'); if (more) { more.hidden = shown >= filtered.length; more.textContent = `Load more (${Math.min(48, Math.max(0, filtered.length-shown))})`; }
      if ($('compareCount')) $('compareCount').textContent = local.compare.length;
      document.querySelectorAll('[data-compare]').forEach(btn => btn.addEventListener('click', () => { const on = toggle(local.compare, btn.dataset.compare, 4); save(); paint(); toast(on ? 'Added to comparison' : 'Removed from comparison'); }));
    };
    ids.forEach(id => $(id)?.addEventListener(id === 'caseSearch' ? 'input' : 'change', () => render(true)));
    $('resetCaseFilters')?.addEventListener('click', () => { ids.forEach(id => { const el=$(id); if(el) el.value = id === 'caseSort' ? 'relevance' : ''; }); render(true); });
    $('loadMoreCases')?.addEventListener('click', () => { shown += 48; paint(); });
    $('openCompare')?.addEventListener('click', event => { event.currentTarget.href = `${PREFIX}cases/compare/?cases=${local.compare.map(encodeURIComponent).join(',')}`; });
    render(true);
  }

  function initCase() {
    const id = document.documentElement.dataset.caseId;
    const sync = () => {
      const bookmark = $('bookmarkCase'), compare = $('compareCase');
      if (bookmark) { const on=local.bookmarks.includes(id); bookmark.textContent=on?'Bookmarked':'Bookmark'; bookmark.setAttribute('aria-pressed',on); }
      if (compare) { const on=local.compare.includes(id); compare.textContent=on?'Remove from compare':'Add to compare'; compare.setAttribute('aria-pressed',on); }
    };
    $('bookmarkCase')?.addEventListener('click', () => { const on=toggle(local.bookmarks,id); save(); sync(); toast(on?'Case bookmarked':'Bookmark removed'); });
    $('compareCase')?.addEventListener('click', () => { const on=toggle(local.compare,id,4); save(); sync(); toast(on?'Added to comparison':'Removed from comparison'); });
    $('copyCaseLink')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText(location.href); toast('Link copied'); } catch (_) { toast('Copy the address from your browser'); } });
    $('printCase')?.addEventListener('click', () => window.print()); sync();
  }

  async function initCompare() {
    const all = await loadCases(); const byId = Object.fromEntries(all.map(c => [c.id,c]));
    const query = new URLSearchParams(location.search).get('cases');
    const ids = (query ? query.split(',').map(decodeURIComponent) : local.compare).filter(Boolean).slice(0,4);
    const selected = ids.map(id => byId[id]).filter(Boolean);
    $('compareEmpty').hidden = selected.length > 0;
    $('compareGrid').innerHTML = selected.map(c => `<article class="compare-card"><div class="badges"><span class="badge treatment">${esc(statusLabel(c.treatment?.status))}</span></div>
      <span class="case-kicker">${esc(c.year)} · ${esc(c.court)}</span><h2><a href="${caseUrl(c.id)}">${esc(c.title)}</a></h2>
      <dl><dt>Facts</dt><dd>${esc(c.facts)}</dd><dt>Issue</dt><dd>${esc(c.issue)}</dd><dt>Holding</dt><dd>${esc(c.holding)}</dd><dt>Significance</dt><dd>${esc(c.significance)}</dd><dt>Treatment</dt><dd>${esc(c.treatment?.note || statusLabel(c.treatment?.status))}</dd><dt>Mapped nodes</dt><dd>${(c.links||[]).slice(0,10).map(l=>`<a href="${nodeUrl(l.nodeId)}">${esc(l.nodeTitle)}</a>`).join('<br>')}</dd></dl></article>`).join('');
  }

  const page = document.documentElement.dataset.page || '';
  if (page === 'catalogue') initCatalogue().catch(err => { if ($('caseResults')) $('caseResults').innerHTML = `<div class="empty-state">${esc(err.message)}</div>`; });
  if (page === 'case') initCase();
  if (page === 'compare') initCompare().catch(err => { if ($('compareEmpty')) $('compareEmpty').textContent = err.message; });
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register(`${PREFIX}sw.js`).catch(() => {});
})();
