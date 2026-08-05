(() => {
  'use strict';

  const STORAGE_KEY = 'du-llb-graph-v1';
  const REPO_BLOB = 'https://github.com/Legedith/llb/blob/main/';
  const els = {};
  let data;
  let nodes;
  let subjects;
  let subjectMap;
  let searchIndex = [];
  let toastTimer;
  let lastGraphCenteredFocus = null;

  const state = {
    view: 'learn',
    terms: new Set([1, 2, 3, 4, 5, 6]),
    core: true,
    elective: true,
    availableOnly: false,
    bookmarkedOnly: false,
    completed: new Set(),
    bookmarks: new Set(),
    lastNode: null,
    focusNode: null,
    graphScale: 1,
  };

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    bindEvents();
    loadLocalState();
    try {
      const response = await fetch('data/curriculum.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error(`Data request failed: ${response.status}`);
      data = await response.json();
      nodes = data.nodes;
      subjects = data.subjects;
      subjectMap = Object.fromEntries(subjects.map(s => [s.id, s]));
      hydrateNodes();
      buildSearchIndex();
      buildTermFilters();
      chooseInitialFocus();
      renderAll();
      handleHash();
      if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
        navigator.serviceWorker.register('sw.js').catch(() => {});
      }
    } catch (error) {
      console.error(error);
      document.querySelector('main').innerHTML = `<div class="empty-state" style="margin-top:2rem"><strong>The curriculum data could not load.</strong><br>${escapeHtml(error.message)}</div>`;
    }
  }

  function cacheElements() {
    for (const id of [
      'menuButton','filterPanel','closeFilters','panelScrim','aboutButton','aboutDialog','closeAbout',
      'searchForm','searchInput','searchClear','searchResults','termFilters','coreFilter','electiveFilter',
      'availableFilter','bookmarkedFilter','resetFilters','statsStrip','readyList','learningQueue',
      'progressLabel','resumeButton','browseSummary','catalogTree','subjectGraphWrap','subjectGraph',
      'graphSmaller','graphLarger','focusGraph','chooseFocus','sourceRegister','nodeDialog','closeNode',
      'nodeBreadcrumb','nodeContent','toast'
    ]) els[id] = document.getElementById(id);
  }

  function bindEvents() {
    els.menuButton.addEventListener('click', () => toggleFilters(true));
    els.closeFilters.addEventListener('click', () => toggleFilters(false));
    els.panelScrim.addEventListener('click', () => toggleFilters(false));
    els.aboutButton.addEventListener('click', () => els.aboutDialog.showModal());
    els.closeAbout.addEventListener('click', () => els.aboutDialog.close());
    els.closeNode.addEventListener('click', closeNode);
    els.nodeDialog.addEventListener('click', e => {
      if (e.target === els.nodeDialog && window.innerWidth >= 700) closeNode();
    });
    document.querySelectorAll('.nav-item').forEach(button => {
      button.addEventListener('click', () => switchView(button.dataset.target));
    });
    els.searchForm.addEventListener('submit', e => {
      e.preventDefault();
      const first = els.searchResults.querySelector('[data-node-id]');
      if (first) openNode(first.dataset.nodeId);
    });
    els.searchInput.addEventListener('input', debounce(renderSearch, 80));
    els.searchInput.addEventListener('focus', renderSearch);
    els.searchInput.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeSearch();
      if (e.key === 'ArrowDown') {
        const first = els.searchResults.querySelector('[data-node-id]');
        if (first) { e.preventDefault(); first.focus(); }
      }
    });
    els.searchClear.addEventListener('click', () => {
      els.searchInput.value = '';
      closeSearch();
      els.searchInput.focus();
    });
    document.addEventListener('click', e => {
      if (!e.target.closest('.site-header')) closeSearch();
    });
    els.searchResults.addEventListener('click', e => {
      const result = e.target.closest('[data-node-id]');
      if (result) openNode(result.dataset.nodeId);
    });
    els.searchResults.addEventListener('keydown', e => {
      const current = e.target.closest('[data-node-id]');
      if (!current) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const all = [...els.searchResults.querySelectorAll('[data-node-id]')];
        const index = all.indexOf(current);
        const next = e.key === 'ArrowDown' ? all[index + 1] : all[index - 1];
        (next || (e.key === 'ArrowDown' ? all[0] : els.searchInput)).focus();
      }
    });
    for (const [element, key] of [
      [els.coreFilter, 'core'], [els.electiveFilter, 'elective'],
      [els.availableFilter, 'availableOnly'], [els.bookmarkedFilter, 'bookmarkedOnly']
    ]) {
      element.addEventListener('change', () => {
        state[key] = element.checked;
        renderFilteredViews();
        saveLocalState();
      });
    }
    els.resetFilters.addEventListener('click', resetFilters);
    els.readyList.addEventListener('click', openFromEvent);
    els.learningQueue.addEventListener('click', openFromEvent);
    els.catalogTree.addEventListener('click', e => {
      const open = e.target.closest('[data-node-id]');
      if (open && !e.target.closest('summary')) openNode(open.dataset.nodeId);
      const inspect = e.target.closest('[data-inspect]');
      if (inspect) openNode(inspect.dataset.inspect);
    });
    els.catalogTree.addEventListener('toggle', e => {
      const details = e.target;
      if (details.matches('.module-block') && details.open) populateModule(details);
    }, true);
    els.subjectGraph.addEventListener('click', e => {
      const group = e.target.closest('[data-subject-id]');
      if (group) {
        state.focusNode = group.dataset.subjectId;
        renderSubjectGraph();
        renderFocusGraph();
        openNode(group.dataset.subjectId);
      }
    });
    els.subjectGraph.addEventListener('keydown', e => {
      const group = e.target.closest('[data-subject-id]');
      if (group && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        group.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      }
    });
    els.graphSmaller.addEventListener('click', () => adjustGraphScale(-.12));
    els.graphLarger.addEventListener('click', () => adjustGraphScale(.12));
    els.focusGraph.addEventListener('click', openFromEvent);
    els.sourceRegister.addEventListener('click', e => {
      const inspect = e.target.closest('[data-inspect]');
      if (inspect) openNode(inspect.dataset.inspect);
    });
    els.chooseFocus.addEventListener('click', () => {
      els.searchInput.focus();
      els.searchInput.placeholder = 'Choose a node for the focus graph…';
      showToast('Search and open any node; it becomes the graph focus.');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    els.resumeButton.addEventListener('click', () => {
      const id = state.lastNode && nodes?.[state.lastNode] ? state.lastNode : nextIncomplete();
      if (id) openNode(id);
    });
    window.addEventListener('hashchange', handleHash);
    window.addEventListener('keydown', e => {
      if (e.key === '/' && !isTyping()) {
        e.preventDefault();
        els.searchInput.focus();
      }
      if (e.key === 'Escape' && els.nodeDialog.open) closeNode();
    });
    window.matchMedia('(min-width: 700px)').addEventListener('change', setResponsiveFilterState);
  }

  function setResponsiveFilterState() {
    if (window.innerWidth >= 700) {
      els.filterPanel.classList.remove('open');
      els.filterPanel.setAttribute('aria-hidden', 'true');
      els.panelScrim.hidden = true;
      els.menuButton.setAttribute('aria-expanded', 'false');
    } else {
      toggleFilters(false);
    }
  }

  function toggleFilters(open) {
    els.filterPanel.classList.toggle('open', open);
    els.filterPanel.setAttribute('aria-hidden', String(!open));
    els.menuButton.setAttribute('aria-expanded', String(open));
    els.panelScrim.hidden = !open || window.innerWidth >= 700;
    document.body.style.overflow = open && window.innerWidth < 700 ? 'hidden' : '';
  }

  function loadLocalState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      if (Array.isArray(saved.completed)) state.completed = new Set(saved.completed);
      if (Array.isArray(saved.bookmarks)) state.bookmarks = new Set(saved.bookmarks);
      if (Array.isArray(saved.terms)) state.terms = new Set(saved.terms.map(Number));
      for (const key of ['core','elective','availableOnly','bookmarkedOnly']) {
        if (typeof saved[key] === 'boolean') state[key] = saved[key];
      }
      if (typeof saved.lastNode === 'string') state.lastNode = saved.lastNode;
      if (typeof saved.focusNode === 'string') state.focusNode = saved.focusNode;
      if (typeof saved.graphScale === 'number') state.graphScale = clamp(saved.graphScale, .65, 1.55);
    } catch (_) {}
  }

  function saveLocalState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      completed: [...state.completed], bookmarks: [...state.bookmarks], terms: [...state.terms],
      core: state.core, elective: state.elective, availableOnly: state.availableOnly,
      bookmarkedOnly: state.bookmarkedOnly, lastNode: state.lastNode, focusNode: state.focusNode,
      graphScale: state.graphScale,
    }));
  }

  function hydrateNodes() {
    for (const subject of subjects) {
      const node = nodes[subject.id] || (nodes[subject.id] = {});
      Object.assign(node, subject);
    }
    for (const node of Object.values(nodes)) {
      if (node.subjectId) {
        const subject = subjectMap[node.subjectId];
        if (!subject) continue;
        node.subjectCode = subject.code;
        node.subjectTitle = subject.title;
        node.term = subject.term;
        node.elective = subject.elective;
        node.category = subject.category;
        node.source = subject.source;
        node.sourceStatus = subject.sourceStatus;
        node.sourceNote = subject.sourceNote;
        node.edition = subject.edition;
        node.laws = subject.laws;
        if (node.moduleId && nodes[node.moduleId]) node.moduleTitle = nodes[node.moduleId].title;
      }
      if (!node.breadcrumb) {
        if (node.subjectId) {
          node.breadcrumb = [`Term ${node.term}`, node.subjectTitle];
          if (node.moduleTitle) node.breadcrumb.push(node.moduleTitle);
          if (node.kind === 'topic') node.breadcrumb.push(node.title);
        } else if (node.kind === 'subject') {
          node.breadcrumb = [`Term ${node.term}`, node.title];
        } else {
          node.breadcrumb = ['Foundation', node.title];
        }
      }
    }
  }

  function buildSearchIndex() {
    searchIndex = Object.values(nodes).map(node => {
      const subject = node.subjectId ? subjectMap[node.subjectId] : null;
      const text = [
        node.id, node.title, node.kind, node.summary, node.eli15, node.subjectCode, node.subjectTitle,
        node.moduleTitle, node.category, ...(node.tags || []), ...(node.laws || []),
        ...(node.aliases || []), ...(subject?.aliases || []), subject?.catalogCode,
      ].filter(Boolean).join(' ').toLowerCase();
      return { id: node.id, text, title: node.title.toLowerCase(), code: (node.code || node.subjectCode || '').toLowerCase() };
    });
  }

  function buildTermFilters() {
    els.termFilters.innerHTML = [1,2,3,4,5,6].map(term =>
      `<button type="button" class="filter-chip ${state.terms.has(term) ? 'active' : ''}" data-term="${term}" aria-pressed="${state.terms.has(term)}">Term ${term}</button>`
    ).join('');
    els.termFilters.addEventListener('click', e => {
      const button = e.target.closest('[data-term]');
      if (!button) return;
      const term = Number(button.dataset.term);
      state.terms.has(term) ? state.terms.delete(term) : state.terms.add(term);
      button.classList.toggle('active', state.terms.has(term));
      button.setAttribute('aria-pressed', String(state.terms.has(term)));
      renderFilteredViews();
      saveLocalState();
    });
    syncFilterInputs();
  }

  function syncFilterInputs() {
    els.coreFilter.checked = state.core;
    els.electiveFilter.checked = state.elective;
    els.availableFilter.checked = state.availableOnly;
    els.bookmarkedFilter.checked = state.bookmarkedOnly;
  }

  function resetFilters() {
    state.terms = new Set([1,2,3,4,5,6]);
    state.core = true; state.elective = true; state.availableOnly = false; state.bookmarkedOnly = false;
    buildTermFilters();
    renderFilteredViews();
    saveLocalState();
  }

  function chooseInitialFocus() {
    if (!state.focusNode || !nodes[state.focusNode]) state.focusNode = nextIncomplete() || 'f01';
  }

  function renderAll() {
    renderStats();
    renderLearn();
    renderBrowse();
    renderSubjectGraph();
    renderFocusGraph();
    renderSources();
    switchView(state.view, false);
    setResponsiveFilterState();
  }

  function renderFilteredViews() {
    renderLearn();
    renderBrowse();
    renderSources();
  }

  function renderStats() {
    const s = data.meta.stats;
    els.statsStrip.innerHTML = [
      [s.subjects, 'papers'], [s.modules, 'modules'], [s.topics, 'topic nodes'], [s.strictEdges, 'strict edges']
    ].map(([value, label]) => `<div class="stat"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`).join('');
  }

  function renderLearn() {
    const ready = data.learningOrder.filter(id => isAvailable(id) && isNodeVisible(nodes[id])).slice(0, 9);
    els.readyList.innerHTML = ready.length ? ready.map((id, index) => nodeCard(nodes[id], index + 1)).join('') :
      `<div class="empty-state">No visible node is ready under the current filters. Broaden the filters or inspect the next locked node in the queue.</div>`;

    const queue = data.learningOrder.filter(id => !state.completed.has(id) && isNodeVisible(nodes[id])).slice(0, 24);
    els.learningQueue.innerHTML = queue.length ? queue.map((id, index) => timelineRow(nodes[id], index + 1)).join('') :
      `<div class="empty-state">Every visible learnable node is marked complete.</div>`;
    const completed = [...state.completed].filter(id => nodes[id]?.learnable).length;
    const total = data.meta.stats.learnableNodes;
    els.progressLabel.textContent = `${formatNumber(completed)} / ${formatNumber(total)} complete`;
  }

  function nodeCard(node, ordinal) {
    const ready = isAvailable(node.id);
    const code = node.subjectCode || (node.term === 0 ? 'METHOD' : node.id.toUpperCase());
    return `<button class="node-card ${state.completed.has(node.id) ? 'complete' : ''}" type="button" data-node-id="${node.id}">
      <span class="ordinal">${ready ? 'READY' : String(ordinal).padStart(2, '0')}</span>
      <span class="node-main"><span class="eyebrow">${escapeHtml(code)} · ${escapeHtml(kindLabel(node))}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.eli15 || node.summary || '')}</p>
      <span class="meta"><span>${node.term ? `Term ${node.term}` : 'Foundation'}</span><span>${node.prerequisites?.length || 0} prerequisites</span><span>${node.unlocks?.length || 0} unlocks</span></span></span>
      <span class="arrow" aria-hidden="true">›</span></button>`;
  }

  function timelineRow(node, ordinal) {
    const ready = isAvailable(node.id);
    const complete = state.completed.has(node.id);
    const stateClass = complete ? 'complete' : ready ? 'ready' : 'locked';
    const code = node.subjectCode || 'METHOD';
    const prereqText = ready ? 'Ready now' : `${countMissingPrerequisites(node.id)} prerequisite${countMissingPrerequisites(node.id) === 1 ? '' : 's'} not complete`;
    return `<button class="timeline-row ${stateClass}" type="button" data-node-id="${node.id}"><span class="timeline-dot">${complete ? '✓' : ordinal}</span><span class="timeline-copy"><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(code)} · ${escapeHtml(prereqText)}</small></span></button>`;
  }

  function renderBrowse() {
    const visible = subjects.filter(subjectVisible);
    const coreCount = visible.filter(s => !s.elective).length;
    const electiveCount = visible.filter(s => s.elective).length;
    els.browseSummary.innerHTML = `<span class="summary-pill">${visible.length} papers</span><span class="summary-pill">${coreCount} core</span><span class="summary-pill">${electiveCount} elective</span><span class="summary-pill">topics render when opened</span>`;

    const terms = [1,2,3,4,5,6].filter(term => state.terms.has(term));
    els.catalogTree.innerHTML = terms.map(term => {
      const termSubjects = visible.filter(s => s.term === term);
      if (!termSubjects.length) return '';
      return `<details class="term-block" ${term === 1 ? 'open' : ''}>
        <summary class="term-summary"><h2>Term ${term}</h2><span>${termSubjects.length} paper${termSubjects.length === 1 ? '' : 's'} · ${formatNumber(termSubjects.reduce((n,s)=>n+s.topicCount,0))} nodes</span></summary>
        <div class="subject-list">${termSubjects.map(subjectBlock).join('')}</div>
      </details>`;
    }).join('') || `<div class="empty-state">No papers match the filters.</div>`;
  }

  function subjectBlock(subject) {
    const warning = subject.sourceNote ? ' · source note' : '';
    return `<details class="subject-block" data-subject="${subject.id}">
      <summary class="subject-summary"><span class="paper-code">${escapeHtml(subject.code)}</span><span><h3>${escapeHtml(subject.title)}</h3><small>${subject.moduleCount} modules · ${subject.topicCount} nodes${warning}</small></span><span class="paper-type ${subject.elective ? 'elective' : ''}">${subject.elective ? 'Elective' : 'Core'}</span></summary>
      <div class="subject-actions"><button class="small-button" type="button" data-inspect="${subject.id}">Inspect paper</button><a class="small-button" href="${escapeAttr(subject.notePath)}">Note scaffold</a></div>
      <div class="module-list">${subject.moduleIds.map(mid => moduleBlock(nodes[mid])).join('')}</div>
    </details>`;
  }

  function moduleBlock(module) {
    return `<details class="module-block" data-module-id="${module.id}"><summary class="module-summary"><strong>${module.moduleNumber}. ${escapeHtml(module.title)}</strong><span>${module.children.length} nodes</span></summary><div class="topic-list" data-topic-container="${module.id}"></div></details>`;
  }

  function populateModule(details) {
    const mid = details.dataset.moduleId;
    const container = details.querySelector('[data-topic-container]');
    if (!mid || !container || container.dataset.loaded) return;
    const module = nodes[mid];
    container.innerHTML = module.children.filter(id => isNodeVisible(nodes[id])).map(id => {
      const node = nodes[id];
      const status = state.completed.has(id) ? 'complete' : isAvailable(id) ? 'ready' : '';
      return `<button class="topic-row" type="button" data-node-id="${id}"><span class="topic-no">${module.moduleNumber}.${node.topicNumber}</span><strong>${escapeHtml(node.title)}</strong><span class="state-dot ${status}" aria-label="${status || 'locked'}"></span></button>`;
    }).join('') || `<div class="empty-state">No topic matches the current filters.</div>`;
    container.dataset.loaded = 'true';
  }

  function renderSubjectGraph() {
    const svg = els.subjectGraph;
    if (!data) return;
    const scale = state.graphScale;
    const compact = window.innerWidth >= 1100;
    const nodeW = compact ? 138 : 178;
    const nodeH = 52;
    const colGap = compact ? 154 : 228;
    const rowGap = 78;
    const firstColumnX = compact ? 156 : 240;
    const positions = { 'foundation-spine': { x: compact ? 8 : 25, y: 370 } };
    const byTerm = new Map([1,2,3,4,5,6].map(t => [t, subjects.filter(s => s.term === t)]));
    let maxRows = 0;
    for (const [term, list] of byTerm) {
      maxRows = Math.max(maxRows, list.length);
      list.forEach((s, index) => positions[s.id] = { x: firstColumnX + (term - 1) * colGap, y: 45 + index * rowGap });
    }
    const width = firstColumnX + 5 * colGap + nodeW + (compact ? 18 : 55);
    const height = Math.max(670, 65 + maxRows * rowGap);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.style.width = `${width * scale}px`;
    svg.style.height = `${height * scale}px`;
    svg.innerHTML = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#aaa08f"></path></marker></defs><title id="subjectGraphTitle">DU LL.B. subject prerequisite graph</title><desc id="subjectGraphDesc">Forty-five papers in six term columns, with strict prerequisite arrows.</desc>`;

    for (const edge of data.subjectEdges) {
      const a = positions[edge.from], b = positions[edge.to];
      if (!a || !b) continue;
      const startX = edge.from === 'foundation-spine' ? a.x + nodeW : a.x + nodeW;
      const startY = a.y + nodeH / 2;
      const endX = b.x;
      const endY = b.y + nodeH / 2;
      const sameCol = Math.abs(startX - endX) < nodeW;
      const curve = sameCol ? 70 : Math.max(38, (endX - startX) * .42);
      const d = sameCol
        ? `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX + curve} ${endY}, ${endX} ${endY}`
        : `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`;
      svg.insertAdjacentHTML('beforeend', `<path class="graph-edge ${edge.from === 'foundation-spine' ? 'foundation' : ''}" d="${d}" marker-end="url(#arrow)"></path>`);
    }

    svg.insertAdjacentHTML('beforeend', graphNodeSvg({ id: 'foundation-spine', code: 'METHOD', title: '26-node legal-method spine', elective: false }, positions['foundation-spine'], true, nodeW));
    for (const subject of subjects) svg.insertAdjacentHTML('beforeend', graphNodeSvg(subject, positions[subject.id], false, nodeW));
    const focused = nodes[state.focusNode];
    const focusSubjectId = focused?.kind === 'subject' ? focused.id : focused?.subjectId;
    if (focusSubjectId && positions[focusSubjectId] && lastGraphCenteredFocus !== focusSubjectId) {
      lastGraphCenteredFocus = focusSubjectId;
      requestAnimationFrame(() => {
        const target = positions[focusSubjectId].x * scale - (els.subjectGraphWrap.clientWidth - nodeW * scale) / 2;
        els.subjectGraphWrap.scrollLeft = Math.max(0, target);
      });
    }
  }

  function graphNodeSvg(subject, pos, foundation, nodeW) {
    const focused = nodes[state.focusNode];
    const focusSubjectId = focused?.kind === 'subject' ? focused.id : focused?.subjectId;
    const selected = focusSubjectId === subject.id;
    const words = wrapText(subject.title, Math.max(17, Math.floor(nodeW / 7))).slice(0, 2);
    const titleLines = words.map((line, i) => `<text class="graph-title" x="10" y="${31 + i * 12}">${escapeXml(line)}</text>`).join('');
    return `<g class="graph-node ${subject.elective ? 'elective' : ''} ${foundation ? 'foundation' : ''} ${selected ? 'selected' : ''}" transform="translate(${pos.x} ${pos.y})" ${foundation ? '' : `data-subject-id="${subject.id}"`} tabindex="${foundation ? '-1' : '0'}" role="button" aria-label="${escapeAttr(subject.code + ' ' + subject.title)}"><rect width="${nodeW}" height="52"></rect><text class="graph-code" x="10" y="15">${escapeXml(subject.code)}</text>${titleLines}</g>`;
  }

  function renderFocusGraph() {
    const node = nodes[state.focusNode] || nodes[nextIncomplete()] || nodes.f01;
    if (!node) return;
    const prereqs = node.prerequisites || [];
    const unlocks = node.unlocks || [];
    const context = [];
    if (node.kind === 'subject') {
      for (const id of node.background || []) context.push([id, 'Background']);
      for (const id of node.related || []) context.push([id, 'Related']);
    }
    els.focusGraph.innerHTML = `<div class="focus-center"><span class="eyebrow">${escapeHtml(node.subjectCode || node.code || kindLabel(node))}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.summary || '')}</p></div>
      <div class="focus-columns">
        ${focusColumn('Prerequisites', prereqs, 'Nothing is required before this node.')}
        ${focusColumn('Unlocks', unlocks.slice(0, 18), 'No direct unlocks recorded.')}
        ${focusContextColumn(context)}
      </div>`;
  }

  function focusColumn(title, ids, empty) {
    return `<div class="focus-column"><h4>${title}</h4>${ids.length ? ids.map(id => focusLink(id)).join('') : `<p class="quiet-label">${empty}</p>`}</div>`;
  }

  function focusContextColumn(context) {
    return `<div class="focus-column"><h4>Context links</h4>${context.length ? context.map(([id,type]) => focusLink(id, type)).join('') : `<p class="quiet-label">Open a subject node to see optional background and related papers.</p>`}</div>`;
  }

  function focusLink(id, type = '') {
    const node = nodes[id];
    if (!node) return '';
    return `<button class="focus-link" type="button" data-node-id="${id}"><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(node.subjectCode || node.code || kindLabel(node))}${type ? ` · ${type}` : ''}</small></span><span aria-hidden="true">›</span></button>`;
  }

  function adjustGraphScale(delta) {
    state.graphScale = clamp(state.graphScale + delta, .65, 1.55);
    saveLocalState();
    renderSubjectGraph();
  }

  function renderSources() {
    const visible = subjects.filter(subjectVisible);
    els.sourceRegister.innerHTML = visible.map(subject => {
      const warning = subject.sourceNote ? `<span class="warning-badge">Edition / source note</span>` : '';
      return `<article class="source-card"><div class="source-card-head"><span class="paper-code">${escapeHtml(subject.code)}</span><div><h3>${escapeHtml(subject.title)}</h3><div class="edition">Term ${subject.term} · ${subject.elective ? 'Elective' : 'Core'} · ${escapeHtml(subject.edition || 'Edition not stated')}</div>${warning}</div></div>
        <p>${escapeHtml(subject.sourceNote || 'Official DU course material; verify present law before relying on substantive propositions.')}</p>
        <div class="source-actions"><a class="small-button" href="${escapeAttr(subject.source)}" target="_blank" rel="noopener">Open DU source</a><button class="small-button" type="button" data-inspect="${subject.id}">Inspect nodes</button><a class="small-button" href="${escapeAttr(subject.notePath)}">Note scaffold</a></div></article>`;
    }).join('') || `<div class="empty-state">No source matches the filters.</div>`;
  }

  function switchView(view, scroll = true) {
    if (!['learn','browse','graph','sources'].includes(view)) view = 'learn';
    state.view = view;
    document.querySelectorAll('.view').forEach(section => {
      const active = section.dataset.view === view;
      section.hidden = !active;
      section.classList.toggle('active', active);
    });
    document.querySelectorAll('.nav-item').forEach(button => {
      const active = button.dataset.target === view;
      button.classList.toggle('active', active);
      active ? button.setAttribute('aria-current', 'page') : button.removeAttribute('aria-current');
    });
    if (view === 'graph') { renderSubjectGraph(); renderFocusGraph(); }
    if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderSearch() {
    if (!data) return;
    const query = normalize(els.searchInput.value);
    els.searchClear.hidden = !query;
    if (query.length < 2) { closeSearch(); return; }
    const terms = query.split(/\s+/).filter(Boolean);
    const results = searchIndex.map(entry => {
      if (!terms.every(term => entry.text.includes(term))) return null;
      let score = 0;
      if (entry.title === query) score += 100;
      if (entry.title.startsWith(query)) score += 55;
      if (entry.code === query || entry.id === query) score += 90;
      if (entry.code.startsWith(query)) score += 35;
      score += terms.reduce((sum, term) => sum + (entry.title.includes(term) ? 12 : 2), 0);
      const node = nodes[entry.id];
      if (node.kind === 'subject') score += 8;
      if (state.bookmarks.has(entry.id)) score += 4;
      return { id: entry.id, score };
    }).filter(Boolean).sort((a,b) => b.score - a.score || nodeSort(nodes[a.id], nodes[b.id])).slice(0, 30);

    els.searchResults.innerHTML = results.length ? results.map(({id}) => searchResult(nodes[id])).join('') : `<div class="empty-state">No node matches “${escapeHtml(els.searchInput.value)}”.</div>`;
    els.searchResults.hidden = false;
  }

  function searchResult(node) {
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : node.id);
    const context = node.moduleTitle ? `${node.subjectTitle} › ${node.moduleTitle}` : node.subjectTitle || node.summary || '';
    return `<button class="search-result" type="button" data-node-id="${node.id}"><span class="code">${escapeHtml(code)}</span><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(context)}</small></span><span class="kind">${escapeHtml(kindLabel(node))}</span></button>`;
  }

  function closeSearch() {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = '';
    els.searchClear.hidden = !els.searchInput.value;
  }

  function openFromEvent(e) {
    const target = e.target.closest('[data-node-id]');
    if (target) openNode(target.dataset.nodeId);
  }

  function openNode(id, updateHash = true) {
    const node = nodes?.[id];
    if (!node) return;
    state.lastNode = id;
    state.focusNode = id;
    saveLocalState();
    els.nodeBreadcrumb.textContent = (node.breadcrumb || [node.title]).join(' › ');
    els.nodeContent.innerHTML = renderNodeContent(node);
    bindNodeDialogActions(node);
    if (!els.nodeDialog.open) els.nodeDialog.showModal();
    if (updateHash) { try { history.replaceState(null, '', `#node=${encodeURIComponent(id)}`); } catch (_) {} }
    renderFocusGraph();
    renderSubjectGraph();
    closeSearch();
  }

  function closeNode() {
    if (els.nodeDialog.open) els.nodeDialog.close();
    if (location.hash.startsWith('#node=')) {
      try { history.replaceState(null, '', location.pathname + location.search); } catch (_) { try { location.hash = ''; } catch (_) {} }
    }
  }

  function renderNodeContent(node) {
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : node.id.toUpperCase());
    const ready = node.learnable ? isAvailable(node.id) : true;
    const status = node.learnable ? state.completed.has(node.id) ? 'Complete' : ready ? 'Ready' : 'Locked' : 'Container';
    const prereqs = relationSection('Strict prerequisites', node.prerequisites || [], 'strict', 'This node has no strict prerequisite.');
    const unlocks = relationSection('Direct unlocks', node.unlocks || [], 'strict', 'No direct unlock is recorded.');
    let context = '';
    if (node.kind === 'subject') {
      context += relationSection('Helpful background', node.background || [], 'background', 'No optional background link recorded.');
      context += relationSection('Related papers', node.related || [], 'related', 'No related paper link recorded.');
    }
    let children = '';
    if (node.kind === 'subject') {
      children = `<section class="node-section"><h3>Modules</h3><div class="relation-list">${node.moduleIds.map(mid => relationButton(mid, 'related')).join('')}</div></section>`;
    } else if (node.kind === 'module') {
      children = `<section class="node-section"><h3>Topic nodes</h3><div class="relation-list">${node.children.map(id => relationButton(id, 'related')).join('')}</div></section>`;
    }
    const laws = (node.laws || []).length ? `<section class="node-section"><h3>Principal legislation / instruments</h3><div class="law-list">${node.laws.map(law => `<span class="law-pill">${escapeHtml(law)}</span>`).join('')}</div></section>` : '';
    const sourceNote = node.sourceNote ? `<div class="source-callout"><strong>Source note</strong><p>${escapeHtml(node.sourceNote)}</p></div>` : '';
    const eli = node.eli15 ? `<div class="eli15"><strong>ELI15</strong>${escapeHtml(node.eli15)}</div>` : '';
    const noteHref = node.notePath || (node.subjectId ? subjectMap[node.subjectId]?.notePath : 'notes/foundations.md');
    const githubHref = REPO_BLOB + noteHref;
    const completeLabel = state.completed.has(node.id) ? 'Mark incomplete' : ready ? 'Mark complete' : 'Mark complete anyway';
    const bookmarkLabel = state.bookmarks.has(node.id) ? 'Remove bookmark' : 'Bookmark';
    const actions = `<div class="node-actions">
      ${node.learnable ? `<button id="completeNodeAction" class="button" type="button">${completeLabel}</button>` : ''}
      <button id="bookmarkNodeAction" class="button secondary" type="button">${bookmarkLabel}</button>
      <button id="focusNodeAction" class="button secondary ${node.learnable ? '' : 'wide'}" type="button">Focus in graph</button>
      <a class="button secondary" href="${escapeAttr(githubHref)}" target="_blank" rel="noopener">Open note on GitHub</a>
      ${node.source ? `<a class="button secondary" href="${escapeAttr(node.source)}" target="_blank" rel="noopener">Open DU source</a>` : ''}
    </div>`;
    return `<span class="node-kicker">${escapeHtml(code)} · ${escapeHtml(kindLabel(node))}</span><h2>${escapeHtml(node.title)}</h2><p class="summary">${escapeHtml(node.summary || '')}</p>${eli}
      <div class="node-meta-grid"><div><small>Status</small><strong>${status}</strong></div><div><small>Term</small><strong>${node.term || 'Method spine'}</strong></div><div><small>Edition</small><strong>${escapeHtml(node.edition || 'Method node')}</strong></div><div><small>Stable ID</small><strong>${escapeHtml(node.id)}</strong></div></div>
      ${sourceNote}${prereqs}${unlocks}${context}${children}${laws}${actions}`;
  }

  function relationSection(title, ids, type, empty) {
    return `<section class="node-section"><h3>${title}</h3>${ids.length ? `<div class="relation-list">${ids.slice(0, 80).map(id => relationButton(id, type)).join('')}</div>` : `<p class="quiet-label">${empty}</p>`}</section>`;
  }

  function relationButton(id, type) {
    const node = nodes[id];
    if (!node) return '';
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : kindLabel(node));
    return `<button class="relation-button ${type}" type="button" data-relation-node="${id}"><span class="relation-type"></span><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(code)}</small></span><span aria-hidden="true">›</span></button>`;
  }

  function bindNodeDialogActions(node) {
    els.nodeContent.querySelectorAll('[data-relation-node]').forEach(button => button.addEventListener('click', () => openNode(button.dataset.relationNode)));
    const complete = document.getElementById('completeNodeAction');
    if (complete) complete.addEventListener('click', () => toggleComplete(node.id));
    document.getElementById('bookmarkNodeAction')?.addEventListener('click', () => toggleBookmark(node.id));
    document.getElementById('focusNodeAction')?.addEventListener('click', () => {
      state.focusNode = node.id;
      saveLocalState();
      closeNode();
      switchView('graph');
      renderFocusGraph();
      renderSubjectGraph();
    });
  }

  function toggleComplete(id) {
    const wasComplete = state.completed.has(id);
    wasComplete ? state.completed.delete(id) : state.completed.add(id);
    saveLocalState();
    renderLearn(); renderBrowse(); renderFocusGraph();
    openNode(id, false);
    showToast(wasComplete ? 'Node marked incomplete.' : `Complete. ${nodes[id].unlocks?.filter(n => isAvailable(n)).length || 0} direct node(s) now ready.`);
  }

  function toggleBookmark(id) {
    const had = state.bookmarks.has(id);
    had ? state.bookmarks.delete(id) : state.bookmarks.add(id);
    saveLocalState();
    renderFilteredViews();
    openNode(id, false);
    showToast(had ? 'Bookmark removed.' : 'Node bookmarked.');
  }

  function handleHash() {
    if (!data) return;
    const match = location.hash.match(/^#node=(.+)$/);
    if (match) {
      const id = decodeURIComponent(match[1]);
      if (nodes[id]) openNode(id, false);
    }
  }

  function isAvailable(id) {
    const node = nodes[id];
    return Boolean(node?.learnable && !state.completed.has(id) && (node.prerequisites || []).every(pre => state.completed.has(pre)));
  }

  function countMissingPrerequisites(id) {
    return (nodes[id]?.prerequisites || []).filter(pre => !state.completed.has(pre)).length;
  }

  function nextIncomplete() {
    return data?.learningOrder.find(id => !state.completed.has(id)) || null;
  }

  function isNodeVisible(node) {
    if (!node) return false;
    if (node.term && !state.terms.has(node.term)) return false;
    if (node.term && node.elective && !state.elective) return false;
    if (node.term && !node.elective && !state.core) return false;
    if (state.availableOnly && node.learnable && !isAvailable(node.id)) return false;
    if (state.bookmarkedOnly && !state.bookmarks.has(node.id) && !state.bookmarks.has(node.subjectId)) return false;
    return true;
  }

  function subjectVisible(subject) {
    if (!state.terms.has(subject.term)) return false;
    if (subject.elective && !state.elective) return false;
    if (!subject.elective && !state.core) return false;
    if (state.bookmarkedOnly && !state.bookmarks.has(subject.id) && !subject.moduleIds.some(mid => state.bookmarks.has(mid) || nodes[mid].children.some(id => state.bookmarks.has(id)))) return false;
    if (state.availableOnly && !isAvailable(subject.firstNode) && !subject.moduleIds.some(mid => nodes[mid].children.some(id => isAvailable(id)))) return false;
    return true;
  }

  function kindLabel(node) {
    if (node.kind === 'topic') return 'Topic';
    if (node.kind === 'module') return 'Module';
    if (node.kind === 'subject') return node.elective ? 'Elective paper' : 'Core paper';
    if (node.kind === 'skill') return 'Method skill';
    return 'Foundation';
  }

  function nodeSort(a, b) {
    return (a.term || 0) - (b.term || 0) || (a.learningOrder || 999999) - (b.learningOrder || 999999) || a.title.localeCompare(b.title);
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.hidden = false;
    toastTimer = setTimeout(() => { els.toast.hidden = true; }, 2600);
  }

  function wrapText(value, limit) {
    const words = value.split(/\s+/); const lines = []; let line = '';
    for (const word of words) {
      const next = line ? `${line} ${word}` : word;
      if (next.length > limit && line) { lines.push(line); line = word; } else line = next;
    }
    if (line) lines.push(line);
    return lines;
  }

  function normalize(value) { return String(value || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim(); }
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch])); }
  function escapeAttr(value) { return escapeHtml(value); }
  function escapeXml(value) { return escapeHtml(value); }
  function formatNumber(value) { return new Intl.NumberFormat('en-IN').format(value); }
  function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }
  function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
  function isTyping() { const tag = document.activeElement?.tagName; return tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable; }
})();
