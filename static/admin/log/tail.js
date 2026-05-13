// Admin · Logs UI controller.
//
// Single-expand drilldown, live SSE or from/to snapshot, free DSL search,
// preset chips, drilldown actions: + filter (kv.k=v), - filter (drop kv.k=*),
// exclude (copy kv.k=v negation hint to clipboard).
//
// Rendering order: newest entries on top.

(function () {
    // Server already strips its promoted columns (timestamp/level/logger/event
    // /pathname/lineno/func_name/trace_id/span_id) from context_json, so we
    // only need to filter formatter byproducts that still ride along.
    const RESERVED_KEYS = new Set(['stack_info', 'exception']);

    const PRESET_DSL = {
        access:   'logger:access',
        lifespan: 'logger:root.lifespan',
    };

    const $ = (sel) => document.querySelector(sel);

    const els = {
        rows: $('#rows'),
        empty: $('#empty'),
        liveBadge: $('#live-badge'),
        statRate: $('#stat-rate'),
        statCount: $('#stat-count'),
        timeFrom: $('#time-from'),
        timeTo: $('#time-to'),
        liveToggle: $('#live-toggle'),
        search: $('#search-input'),
        searchError: $('#search-error'),
        exportJson: $('#export-json'),
        exportCsv: $('#export-csv'),
        chips: document.querySelectorAll('.chip[data-preset]'),
        presetClear: $('#preset-clear'),
        levelGroup: $('#level-group'),
        levelInputs: document.querySelectorAll('#level-group input[type="checkbox"]'),
        btnReload: $('#btn-reload'),
        btnOlder: $('#btn-older'),
        btnClear: $('#btn-clear'),
    };

    const state = {
        live: true,
        timeFrom: '',     // datetime-local string
        timeTo: '',       // datetime-local string
        search: '',
        levels: new Set(), // selected levels (empty = all)
        entries: [],      // newest at index 0
        seenIds: new Set(),
        expandedId: null,
        expandedTab: 'context',
        eventSource: null,
        rateBuf: [],
        oldestCursor: null,
        clearArmed: false,
        clearArmTimer: 0,
    };

    // ---------- DSL composition ----------
    function localToIsoUtc(local) {
        if (!local) return '';
        const d = new Date(local);
        if (isNaN(d.getTime())) return '';
        return d.toISOString();
    }

    function buildQ() {
        const parts = [];
        if (state.search) parts.push(state.search);
        if (!state.live) {
            const from = localToIsoUtc(state.timeFrom);
            const to = localToIsoUtc(state.timeTo);
            if (from) parts.push(`from:${from}`);
            if (to) parts.push(`to:${to}`);
        }
        return parts.join(' ').trim();
    }

    function buildParams() {
        const p = new URLSearchParams();
        const q = buildQ();
        if (q) p.set('q', q);
        for (const lvl of state.levels) p.append('levels', lvl);
        return p;
    }

    // ---------- rendering ----------
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

    function parseContext(entry) {
        if (entry._context) return entry._context;
        try { entry._context = JSON.parse(entry.context_json || '{}'); }
        catch { entry._context = {}; }
        return entry._context;
    }

    // Reconstruct the full structlog record by merging promoted top-level
    // columns with parsed context. Used by the JSON drill tab.
    function fullRecord(entry) {
        const ctx = parseContext(entry);
        const out = {
            timestamp: entry.timestamp,
            level: entry.level,
            logger: entry.logger,
            event: entry.event,
            pathname: entry.pathname,
            lineno: entry.lineno,
            func_name: entry.func_name,
        };
        if (entry.trace_id) out.trace_id = entry.trace_id;
        if (entry.span_id)  out.span_id  = entry.span_id;
        return Object.assign(out, ctx);
    }

    function contextKvs(entry) {
        const data = parseContext(entry);
        const out = [];
        for (const [k, v] of Object.entries(data)) {
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

    function renderRow(entry) {
        const lvl = (entry.level || '').toUpperCase();
        const kvs = contextKvs(entry);
        const ctxHtml = kvs.slice(0, 4).map(([k, v]) =>
            `<span class="kv"><b>${escape(k)}</b>=<i>${escape(shortValue(v))}</i></span>`
        ).join('');

        const row = document.createElement('div');
        row.className = 'row grid-cols';
        row.dataset.id = String(entry.id);
        row.innerHTML = `
            <div class="ts">${escape(shortTime(entry.timestamp))}</div>
            <div class="lv ${lvl}">${escape(lvl.toLowerCase())}</div>
            <div class="lg" title="${escape(entry.logger || '')}">${escape(entry.logger || '')}</div>
            <div class="ev">${escape(entry.event || '')}</div>
            <div class="ctx">${ctxHtml}</div>
        `;
        row.addEventListener('click', () => toggleExpand(entry.id));
        return row;
    }

    function inferType(v) {
        if (v === null) return 'null';
        if (Array.isArray(v)) return 'list';
        return typeof v;
    }

    function renderDrill(entry) {
        const data = fullRecord(entry);
        const ctx = parseContext(entry);
        // Drill 'context' tab lists ALL fields (promoted + structured kwargs)
        // so users can copy / filter against any of them, including timestamp.
        const kvs = Object.entries(data);
        const exception = ctx.exception;
        const tabs = ['context', 'json', 'exception'];

        const drill = document.createElement('div');
        drill.className = 'drill';
        drill.dataset.drillFor = String(entry.id);

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
                <div class="ctx-acts">
                    <button class="btn include" data-act="add"     title="add filter ${escape(k)}=${escape(valStr)}">+ filter</button>
                    <button class="btn"         data-act="remove"  title="remove all filters on ${escape(k)}">− filter</button>
                    <button class="btn exclude" data-act="exclude" title="copy exclusion hint ${escape(k)}=${escape(valStr)}">exclude</button>
                </div>
            `;
            row.querySelector('.ctx-val').addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard?.writeText(valStr);
            });
            row.querySelector('[data-act="add"]').addEventListener('click', (e) => {
                e.stopPropagation();
                addKvFilter(k, valStr);
            });
            row.querySelector('[data-act="remove"]').addEventListener('click', (e) => {
                e.stopPropagation();
                removeKvFilter(k);
            });
            row.querySelector('[data-act="exclude"]').addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard?.writeText(`-kv.${k}=${valStr}`);
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

    function quoteIfNeeded(v) {
        return /\s/.test(v) ? `"${v.replace(/"/g, '\\"')}"` : v;
    }

    function tokenize(s) {
        const out = [];
        const re = /"(?:\\.|[^"\\])*"|\S+/g;
        let m;
        while ((m = re.exec(s)) !== null) out.push(m[0]);
        return out;
    }

    function setSearchTokens(tokens) {
        const next = tokens.join(' ');
        els.search.value = next;
        state.search = next;
    }

    function addKvFilter(key, val) {
        const token = `kv.${key}=${quoteIfNeeded(val)}`;
        const tokens = tokenize(state.search || '');
        // Replace existing kv.<key>=... if present; else append.
        const prefix = `kv.${key}=`;
        const idx = tokens.findIndex(t => t.startsWith(prefix));
        if (idx >= 0) tokens[idx] = token;
        else tokens.push(token);
        setSearchTokens(tokens);
        reload();
    }

    function removeKvFilter(key) {
        const prefix = `kv.${key}=`;
        const tokens = tokenize(state.search || '').filter(t => !t.startsWith(prefix));
        setSearchTokens(tokens);
        reload();
    }

    function renderAll() {
        els.rows.innerHTML = '';
        if (state.entries.length === 0) {
            els.empty.style.display = 'block';
            els.statCount.textContent = '0 records';
            return;
        }
        els.empty.style.display = 'none';

        // newest on top
        for (const entry of state.entries) {
            const row = renderRow(entry);
            if (state.expandedId === entry.id) row.classList.add('expanded');
            els.rows.appendChild(row);
            if (state.expandedId === entry.id) {
                els.rows.appendChild(renderDrill(entry));
            }
        }
        els.statCount.textContent = `${state.entries.length} records`;
    }

    function appendLiveEntry(entry) {
        if (state.seenIds.has(entry.id)) return;
        state.seenIds.add(entry.id);
        state.entries.unshift(entry);  // newest on top
        if (state.entries.length > 2000) {
            const dropped = state.entries.splice(2000);
            for (const e of dropped) state.seenIds.delete(e.id);
        }
        const row = renderRow(entry);
        if (state.expandedId === entry.id) row.classList.add('expanded');
        els.rows.insertBefore(row, els.rows.firstChild);
        els.empty.style.display = 'none';
        els.statCount.textContent = `${state.entries.length} records`;

        const now = Date.now();
        state.rateBuf.push(now);
        while (state.rateBuf.length && now - state.rateBuf[0] > 60000) {
            state.rateBuf.shift();
        }
    }

    function toggleExpand(id) {
        const same = state.expandedId === id;
        state.expandedId = same ? null : id;
        renderAll();
        if (!same) {
            const row = els.rows.querySelector(`.row[data-id="${id}"]`);
            row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    // ---------- API ----------
    async function fetchSnapshot() {
        const res = await fetch(`/api/v1/admin/logs?${buildParams()}`);
        if (res.status === 400) {
            const body = await res.json().catch(() => ({}));
            els.searchError.textContent = body.reason ? `dsl: ${body.reason}` : 'invalid query';
            els.searchError.classList.add('on');
            state.entries = [];
            state.seenIds.clear();
            renderAll();
            return false;
        }
        els.searchError.classList.remove('on');
        const data = await res.json();
        state.entries = [];
        state.seenIds.clear();
        // API returns oldest -> newest; flip so newest is at index 0.
        for (const e of [...data.entries].reverse()) {
            state.seenIds.add(e.id);
            state.entries.push(e);
        }
        state.oldestCursor = data.cursor;
        renderAll();
        return true;
    }

    async function fetchOlder() {
        if (state.oldestCursor === null || state.oldestCursor === undefined) return;
        const params = buildParams();
        params.set('cursor', String(state.oldestCursor));
        els.btnOlder.disabled = true;
        try {
            const res = await fetch(`/api/v1/admin/logs/older?${params}`);
            if (res.status === 400) {
                const body = await res.json().catch(() => ({}));
                els.searchError.textContent = body.reason ? `dsl: ${body.reason}` : 'invalid query';
                els.searchError.classList.add('on');
                return;
            }
            const data = await res.json();
            // API returns oldest -> newest within the older page; append to bottom.
            for (const e of data.entries) {
                if (state.seenIds.has(e.id)) continue;
                state.seenIds.add(e.id);
                state.entries.push(e);
            }
            state.oldestCursor = data.cursor;
            renderAll();
        } finally {
            els.btnOlder.disabled = false;
        }
    }

    async function clearLogs() {
        const res = await fetch('/api/v1/admin/logs?confirm=yes-i-am-sure', { method: 'DELETE' });
        if (!res.ok) {
            els.searchError.textContent = `clear failed: HTTP ${res.status}`;
            els.searchError.classList.add('on');
            return;
        }
        state.entries = [];
        state.seenIds.clear();
        state.oldestCursor = null;
        renderAll();
        // Restart stream so its internal last_id resets after the wipe.
        if (state.live) startStream();
    }

    function startStream() {
        stopStream();
        const params = buildParams();
        try {
            state.eventSource = new EventSource(`/api/v1/admin/logs/stream?${params}`);
            state.eventSource.onmessage = (ev) => {
                try { appendLiveEntry(JSON.parse(ev.data)); }
                catch { /* ignore malformed frame */ }
            };
            state.eventSource.onerror = () => {
                els.liveBadge.classList.add('off');
            };
            els.liveBadge.classList.remove('off');
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
        state.expandedId = null;
        const ok = await fetchSnapshot();
        if (state.live && ok) {
            els.liveBadge.classList.remove('off');
            startStream();
        } else {
            stopStream();
            els.liveBadge.classList.add('off');
        }
    }

    // ---------- wiring ----------
    els.liveToggle.addEventListener('change', () => {
        state.live = els.liveToggle.checked;
        reload();
    });
    els.timeFrom.addEventListener('change', () => {
        state.timeFrom = els.timeFrom.value;
        if (state.live) {
            state.live = false;
            els.liveToggle.checked = false;
        }
        reload();
    });
    els.timeTo.addEventListener('change', () => {
        state.timeTo = els.timeTo.value;
        if (state.live) {
            state.live = false;
            els.liveToggle.checked = false;
        }
        reload();
    });

    els.btnReload.addEventListener('click', () => reload());
    els.btnOlder.addEventListener('click', () => fetchOlder());
    els.btnClear.addEventListener('click', () => {
        if (!state.clearArmed) {
            state.clearArmed = true;
            els.btnClear.classList.add('armed');
            els.btnClear.textContent = '✕ click again to wipe';
            clearTimeout(state.clearArmTimer);
            state.clearArmTimer = setTimeout(() => {
                state.clearArmed = false;
                els.btnClear.classList.remove('armed');
                els.btnClear.textContent = '✕ clear';
            }, 4000);
            return;
        }
        // Second click → confirm with a native modal then issue.
        clearTimeout(state.clearArmTimer);
        state.clearArmed = false;
        els.btnClear.classList.remove('armed');
        els.btnClear.textContent = '✕ clear';
        if (!window.confirm('Permanently delete ALL log records? This cannot be undone.')) return;
        clearLogs();
    });

    let searchTimer = 0;
    els.search.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.search = els.search.value.trim();
            reload();
        }, 250);
    });
    els.search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            els.search.value = '';
            state.search = '';
            reload();
            els.search.blur();
        }
    });

    els.chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const id = chip.dataset.preset;
            const dsl = PRESET_DSL[id] || '';
            const isOn = chip.classList.contains('active');
            els.chips.forEach(c => c.classList.remove('active'));
            if (!isOn) chip.classList.add('active');
            els.search.value = isOn ? '' : dsl;
            state.search = els.search.value;
            reload();
        });
    });

    els.presetClear.addEventListener('click', () => {
        els.search.value = '';
        state.search = '';
        state.levels.clear();
        els.chips.forEach(c => c.classList.remove('active'));
        els.levelInputs.forEach(inp => {
            inp.checked = false;
            inp.parentElement.classList.remove('on');
        });
        reload();
    });

    els.levelInputs.forEach(inp => {
        inp.addEventListener('change', () => {
            const value = inp.value;
            if (inp.checked) {
                state.levels.add(value);
                inp.parentElement.classList.add('on');
            } else {
                state.levels.delete(value);
                inp.parentElement.classList.remove('on');
            }
            reload();
        });
    });

    els.exportJson.addEventListener('click', () => {
        window.open(`/api/v1/admin/logs/export?format=ndjson&${buildParams()}`, '_blank');
    });
    els.exportCsv.addEventListener('click', () => {
        window.open(`/api/v1/admin/logs/export?format=csv&${buildParams()}`, '_blank');
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== els.search) {
            e.preventDefault();
            els.search.focus();
            els.search.select();
        } else if (e.key === 'Escape' && state.expandedId !== null) {
            state.expandedId = null;
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
