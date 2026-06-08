// Admin · Logs UI controller.
//
// File-tail viewer: history via /api/v1/admin/logs (tail page) + /older
// (cursor pagination), live via /stream (SSE). Level filter and substring
// search are CLIENT-SIDE over already-loaded rows. "Load more" pulls more
// history from the file, which then becomes filterable.
//
// Rendering order: newest entries on top.

(function () {
    const RESERVED_KEYS = new Set(['stack_info', 'exception']);
    // Drilldown field carrying the structured kwargs. Backend LogEntrySchema
    // names it `context_json`; if the backend renames, change only this.
    const CONTEXT_FIELD = 'context_json';
    const MAX_BACKOFF_MS = 10000;

    const $ = (sel) => document.querySelector(sel);

    const els = {
        rows: $('#rows'),
        empty: $('#empty'),
        liveBadge: $('#live-badge'),
        statRate: $('#stat-rate'),
        statCount: $('#stat-count'),
        search: $('#search-input'),
        levelInputs: document.querySelectorAll('#level-group input[type="checkbox"]'),
        btnReload: $('#btn-reload'),
        btnOlder: $('#btn-older'),
    };

    const state = {
        search: '',
        levels: new Set(),   // selected levels (empty = all)
        entries: [],         // newest at index 0 (loaded rows)
        seenKeys: new Set(),
        expandedUid: null,
        expandedTab: 'context',
        eventSource: null,
        rateBuf: [],
        oldestCursor: null,  // opaque base64 string or null
        backoffMs: 500,
        uidSeq: 0,
        historyExhausted: false,
    };

    // ---------- identity ----------
    function entryKey(e) {
        return `${e.timestamp || ''}|${e.logger || ''}|${e.event || ''}`;
    }
    function tagUid(e) {
        e._uid = ++state.uidSeq;
        return e;
    }

    // ---------- rendering helpers ----------
    function shortTime(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        const hh = String(d.getUTCHours()).padStart(2, '0');
        const mm = String(d.getUTCMinutes()).padStart(2, '0');
        const ss = String(d.getUTCSeconds()).padStart(2, '0');
        const ms = String(d.getUTCMilliseconds()).padStart(3, '0');
        return `${hh}:${mm}:${ss}.${ms}`;
    }

    function shortValue(v) {
        if (v === null || v === undefined) return '';
        const s = typeof v === 'string' ? v : JSON.stringify(v);
        return s.length > 24 ? s.slice(0, 22) + '…' : s;
    }

    function contextOf(entry) {
        const c = entry[CONTEXT_FIELD];
        if (c && typeof c === 'object') return c;
        if (typeof c === 'string') {
            try { return JSON.parse(c || '{}'); } catch { return {}; }
        }
        return {};
    }

    function fullRecord(entry) {
        const ctx = contextOf(entry);
        const out = {
            timestamp: entry.timestamp,
            level: entry.level,
            logger: entry.logger,
            event: entry.event,
        };
        return Object.assign(out, ctx);
    }

    function contextKvs(entry) {
        const out = [];
        for (const [k, v] of Object.entries(contextOf(entry))) {
            if (RESERVED_KEYS.has(k)) continue;
            out.push([k, v]);
        }
        return out;
    }

    function escape(s) {
        return String(s ?? '').replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }

    // ---------- client-side filtering ----------
    function matchesFilters(entry) {
        if (state.levels.size > 0) {
            const lvl = (entry.level || '').toUpperCase();
            if (!state.levels.has(lvl)) return false;
        }
        if (state.search) {
            const needle = state.search.toLowerCase();
            const hay = (
                (entry.event || '') + ' ' +
                (entry.logger || '') + ' ' +
                (entry.level || '') + ' ' +
                JSON.stringify(entry[CONTEXT_FIELD] ?? {})
            ).toLowerCase();
            if (!hay.includes(needle)) return false;
        }
        return true;
    }

    function visibleEntries() {
        return state.entries.filter(matchesFilters);
    }

    // ---------- rendering ----------
    function renderRow(entry) {
        const lvl = (entry.level || '').toUpperCase();
        const kvs = contextKvs(entry);
        const ctxHtml = kvs.slice(0, 4).map(([k, v]) =>
            `<span class="kv"><b>${escape(k)}</b>=<i>${escape(shortValue(v))}</i></span>`
        ).join('');

        const row = document.createElement('div');
        row.className = 'row grid-cols';
        row.dataset.id = String(entry._uid);
        row.innerHTML = `
            <div class="ts">${escape(shortTime(entry.timestamp))}</div>
            <div class="lv ${lvl}">${escape(lvl.toLowerCase())}</div>
            <div class="lg" title="${escape(entry.logger || '')}">${escape(entry.logger || '')}</div>
            <div class="ev">${escape(entry.event || '')}</div>
            <div class="ctx">${ctxHtml}</div>
        `;
        row.addEventListener('click', () => toggleExpand(entry._uid));
        return row;
    }

    function inferType(v) {
        if (v === null) return 'null';
        if (Array.isArray(v)) return 'list';
        return typeof v;
    }

    function renderDrill(entry) {
        const data = fullRecord(entry);
        const ctx = contextOf(entry);
        const kvs = Object.entries(data);
        const exception = ctx.exception;
        const tabs = ['context', 'json', 'exception'];

        const drill = document.createElement('div');
        drill.className = 'drill';
        drill.dataset.drillFor = String(entry._uid);

        const tabsBar = document.createElement('nav');
        tabsBar.className = 'tabs';
        tabsBar.innerHTML = `
            <button data-tab="context" class="${state.expandedTab === 'context' ? 'on' : ''}">Context <span class="badge">${kvs.length}</span></button>
            <button data-tab="json" class="${state.expandedTab === 'json' ? 'on' : ''}">JSON</button>
            <button data-tab="exception" class="${state.expandedTab === 'exception' ? 'on' : ''}">Exception</button>
        `;
        tabsBar.querySelectorAll('button').forEach(b => {
            b.addEventListener('click', (e) => {
                e.stopPropagation();
                state.expandedTab = b.dataset.tab;
                tabs.forEach(t => {
                    drill.querySelector(`.tab-panel[data-tab="${t}"]`).classList.toggle('on', t === state.expandedTab);
                    const tb = tabsBar.querySelector(`button[data-tab="${t}"]`);
                    if (tb) tb.classList.toggle('on', t === state.expandedTab);
                });
            });
        });
        drill.appendChild(tabsBar);

        const ctxPanel = document.createElement('div');
        ctxPanel.className = `tab-panel ${state.expandedTab === 'context' ? 'on' : ''}`;
        ctxPanel.dataset.tab = 'context';
        for (const [k, v] of kvs) {
            const row = document.createElement('div');
            row.className = 'ctx-row';
            const valStr = typeof v === 'string' ? v : JSON.stringify(v);
            row.innerHTML = `
                <div class="ctx-key">${escape(k)} <span class="type">${escape(inferType(v))}</span></div>
                <div class="ctx-val copy" title="click to copy">${escape(valStr)}</div>
            `;
            row.querySelector('.ctx-val').addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard?.writeText(valStr);
            });
            ctxPanel.appendChild(row);
        }
        drill.appendChild(ctxPanel);

        const jsonPanel = document.createElement('div');
        jsonPanel.className = `tab-panel ${state.expandedTab === 'json' ? 'on' : ''}`;
        jsonPanel.dataset.tab = 'json';
        const pre = document.createElement('pre');
        pre.className = 'json-view';
        pre.textContent = JSON.stringify(data, null, 2);
        jsonPanel.appendChild(pre);
        drill.appendChild(jsonPanel);

        const excPanel = document.createElement('div');
        excPanel.className = `tab-panel ${state.expandedTab === 'exception' ? 'on' : ''}`;
        excPanel.dataset.tab = 'exception';
        const excPre = document.createElement('pre');
        if (exception) {
            excPre.className = 'exception-view';
            excPre.textContent = typeof exception === 'string'
                ? exception
                : JSON.stringify(exception, null, 2);
        } else {
            excPre.className = 'exception-view empty';
            excPre.textContent = 'no exception attached';
        }
        excPanel.appendChild(excPre);
        drill.appendChild(excPanel);

        drill.addEventListener('click', (e) => e.stopPropagation());
        return drill;
    }

    function renderAll() {
        els.rows.innerHTML = '';
        const visible = visibleEntries();
        if (visible.length === 0) {
            els.empty.style.display = 'block';
            els.statCount.textContent = `0 / ${state.entries.length} records`;
            return;
        }
        els.empty.style.display = 'none';
        for (const entry of visible) {
            const row = renderRow(entry);
            if (state.expandedUid === entry._uid) row.classList.add('expanded');
            els.rows.appendChild(row);
            if (state.expandedUid === entry._uid) {
                els.rows.appendChild(renderDrill(entry));
            }
        }
        els.statCount.textContent = `${visible.length} / ${state.entries.length} records`;
        els.btnOlder.disabled = state.historyExhausted || state.oldestCursor === null;
    }

    function appendLiveEntry(entry) {
        const key = entryKey(entry);
        if (state.seenKeys.has(key)) return;
        state.seenKeys.add(key);
        tagUid(entry);
        state.entries.unshift(entry);  // newest on top
        if (state.entries.length > 2000) {
            const dropped = state.entries.splice(2000);
            for (const e of dropped) state.seenKeys.delete(entryKey(e));
        }
        renderAll();

        const now = Date.now();
        state.rateBuf.push(now);
        while (state.rateBuf.length && now - state.rateBuf[0] > 60000) {
            state.rateBuf.shift();
        }
    }

    function toggleExpand(uid) {
        const same = state.expandedUid === uid;
        state.expandedUid = same ? null : uid;
        renderAll();
        if (!same) {
            const row = els.rows.querySelector(`.row[data-id="${uid}"]`);
            row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    // ---------- API ----------
    async function fetchTail() {
        const res = await fetch('/api/v1/admin/logs/');
        if (!res.ok) return false;
        const data = await res.json();
        state.entries = [];
        state.seenKeys.clear();
        state.historyExhausted = false;
        // API returns oldest -> newest; flip so newest is at index 0.
        for (const e of [...(data.entries || [])].reverse()) {
            const key = entryKey(e);
            if (state.seenKeys.has(key)) continue;
            state.seenKeys.add(key);
            state.entries.push(tagUid(e));
        }
        state.oldestCursor = data.cursor ?? null;
        renderAll();
        return true;
    }

    async function fetchOlder() {
        if (state.oldestCursor === null || state.oldestCursor === undefined) return;
        const params = new URLSearchParams();
        params.set('cursor', state.oldestCursor);
        els.btnOlder.disabled = true;
        try {
            const res = await fetch(`/api/v1/admin/logs/older?${params}`);
            if (!res.ok) return;
            const data = await res.json();
            const before = state.entries.length;
            // older page is oldest -> newest; append to the bottom (older end).
            for (const e of (data.entries || [])) {
                const key = entryKey(e);
                if (state.seenKeys.has(key)) continue;
                state.seenKeys.add(key);
                state.entries.push(tagUid(e));
            }
            // null cursor or no new rows => history truncated / exhausted.
            if (data.cursor === null || data.cursor === undefined || state.entries.length === before) {
                state.historyExhausted = true;
            }
            state.oldestCursor = data.cursor ?? null;
            renderAll();
        } finally {
            els.btnOlder.disabled = state.historyExhausted || state.oldestCursor === null;
        }
    }

    function startStream() {
        stopStream();
        try {
            state.eventSource = new EventSource('/api/v1/admin/logs/stream');
            state.eventSource.onopen = () => {
                state.backoffMs = 500;
                els.liveBadge.classList.remove('off');
            };
            state.eventSource.onmessage = (ev) => {
                try { appendLiveEntry(JSON.parse(ev.data)); }
                catch { /* ignore malformed frame */ }
            };
            state.eventSource.onerror = () => {
                els.liveBadge.classList.add('off');
                stopStream();
                const delay = state.backoffMs;
                state.backoffMs = Math.min(state.backoffMs * 2, MAX_BACKOFF_MS);
                setTimeout(startStream, delay);
            };
        } catch {
            els.liveBadge.classList.add('off');
        }
    }

    function stopStream() {
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }
    }

    async function reload() {
        state.expandedUid = null;
        const ok = await fetchTail();
        if (ok) startStream();
    }

    // ---------- wiring ----------
    els.btnReload.addEventListener('click', () => reload());
    els.btnOlder.addEventListener('click', () => fetchOlder());

    let searchTimer = 0;
    els.search.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.search = els.search.value.trim();
            renderAll();
        }, 150);
    });
    els.search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            els.search.value = '';
            state.search = '';
            renderAll();
            els.search.blur();
        }
    });

    els.levelInputs.forEach(inp => {
        inp.addEventListener('change', () => {
            const value = inp.value.toUpperCase();
            if (inp.checked) {
                state.levels.add(value);
                inp.parentElement.classList.add('on');
            } else {
                state.levels.delete(value);
                inp.parentElement.classList.remove('on');
            }
            renderAll();
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== els.search) {
            e.preventDefault();
            els.search.focus();
            els.search.select();
        } else if (e.key === 'Escape' && state.expandedUid !== null) {
            state.expandedUid = null;
            renderAll();
        }
    });

    // column resizers
    const colVarMap = { ts: '--col-ts', lv: '--col-lv', lg: '--col-lg', ev: '--col-ev' };
    const minPx = { ts: 100, lv: 50, lg: 120, ev: 160 };
    document.querySelectorAll('.resizer').forEach(r => {
        r.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const cssVar = colVarMap[r.dataset.col];
            if (!cssVar) return;
            const startX = e.clientX;
            const startW = r.parentElement.getBoundingClientRect().width;
            r.classList.add('dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            const move = (ev) => {
                const next = Math.max(minPx[r.dataset.col] || 60, startW + (ev.clientX - startX));
                document.documentElement.style.setProperty(cssVar, next + 'px');
            };
            const up = () => {
                r.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                window.removeEventListener('mousemove', move);
                window.removeEventListener('mouseup', up);
            };
            window.addEventListener('mousemove', move);
            window.addEventListener('mouseup', up);
        });
    });

    setInterval(() => {
        const now = Date.now();
        while (state.rateBuf.length && now - state.rateBuf[0] > 60000) {
            state.rateBuf.shift();
        }
        els.statRate.textContent = `${state.rateBuf.length} / min`;
    }, 1000);

    // boot
    reload();
})();
