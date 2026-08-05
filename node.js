
(() => {
  'use strict';
  const KEY = 'du-llb-graph-v1';
  const root = document.documentElement;
  const id = root.dataset.nodeId;
  const prerequisites = (root.dataset.prerequisites || '').split(',').filter(Boolean);
  const complete = document.getElementById('completeToggle');
  const bookmark = document.getElementById('bookmarkToggle');
  const badge = document.getElementById('statusBadge');
  const readiness = document.getElementById('readinessText');
  const toast = document.getElementById('toast');
  let timer;

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (_) { return {}; }
  }
  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (_) {}
  }
  function arraySet(value) { return new Set(Array.isArray(value) ? value : []); }
  function saveSet(state, name, set) { state[name] = [...set]; write(state); }
  function show(message) {
    toast.textContent = message; toast.classList.add('show'); clearTimeout(timer);
    timer = setTimeout(() => toast.classList.remove('show'), 1800);
  }
  function refresh() {
    const state = read();
    const done = arraySet(state.completed);
    const marks = arraySet(state.bookmarks);
    const isDone = done.has(id);
    const missing = prerequisites.filter(x => !done.has(x));
    badge.className = isDone ? 'complete' : missing.length ? '' : 'ready';
    badge.textContent = isDone ? 'Complete' : missing.length ? 'Sequence locked' : 'Ready';
    readiness.textContent = isDone
      ? 'Recorded as complete in this browser.'
      : missing.length
        ? `${missing.length} strict prerequisite${missing.length === 1 ? '' : 's'} not marked complete. The study page remains fully readable.`
        : 'All strict prerequisites are marked complete. This node is ready in the learning sequence.';
    complete.setAttribute('aria-pressed', String(isDone));
    complete.textContent = isDone ? 'Mark incomplete' : 'Mark complete';
    bookmark.setAttribute('aria-pressed', String(marks.has(id)));
    bookmark.textContent = marks.has(id) ? 'Bookmarked' : 'Bookmark';
  }
  function toggle(name) {
    const state = read(); const set = arraySet(state[name]);
    set.has(id) ? set.delete(id) : set.add(id);
    saveSet(state, name, set); refresh();
    show(name === 'completed' ? (set.has(id) ? 'Marked complete' : 'Marked incomplete') : (set.has(id) ? 'Bookmark saved' : 'Bookmark removed'));
  }
  complete?.addEventListener('click', () => toggle('completed'));
  bookmark?.addEventListener('click', () => toggle('bookmarks'));
  document.getElementById('copyLink')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); show('Link copied'); }
    catch (_) { show('Copy the address from the browser bar'); }
  });
  document.getElementById('printPage')?.addEventListener('click', () => window.print());
  window.addEventListener('storage', refresh);
  window.addEventListener('keydown', event => {
    if (/input|textarea|select/i.test(document.activeElement?.tagName || '')) return;
    if (event.key.toLowerCase() === 'b') { event.preventDefault(); toggle('bookmarks'); }
    if (event.key.toLowerCase() === 'c') { event.preventDefault(); toggle('completed'); }
  });
  const state = read(); state.lastNode = id; state.focusNode = id; write(state); refresh();
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('../../sw.js').catch(() => {});
})();
