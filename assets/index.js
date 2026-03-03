const BOOT = JSON.parse(atob('%BOOT%'));
// --- Global State ---
let editor;
let monaco;
let tabs = [];
let nextTabId = 0;
let activeTabId = -1;

// --- Find/Replace State ---
let currentMatches = [];
let currentMatchIndex = -1;

const SURGICAL_SCHEMA = {
  "file_path": "string (optional, for context)",
  "start_line": "number",
  "end_line": "number",
  "start_column": "number (optional)",
  "end_column": "number (optional)",
  "replacement_code": "string"
};

// --- FIND & REPLACE LOGIC (New) ---
function showFindReplace() {
    const modal = document.getElementById('find-modal-overlay');
    const input = document.getElementById('find-input');
    if (!modal) return;
    modal.classList.remove('hidden');
    input.focus();
    // Pre-fill with selected text if any
    const selection = editor.getSelection();
    if (selection && !selection.isEmpty()) {
        const text = editor.getModel().getValueInRange(selection);
        input.value = text;
    }
}

function closeFindReplace() {
    document.getElementById('find-modal-overlay').classList.add('hidden');
    editor.focus();
}

function doFindNext() {
    const findText = document.getElementById('find-input').value;
    if (!findText) return;

    const model = editor.getModel();
    // Find all matches
    currentMatches = model.findMatches(findText, false, false, false, null, true);
    
    if (currentMatches.length === 0) {
        document.getElementById('find-status').textContent = "No matches found.";
        return;
    }

    // Cycle index
    currentMatchIndex++;
    if (currentMatchIndex >= currentMatches.length) {
        currentMatchIndex = 0;
    }

    const match = currentMatches[currentMatchIndex];
    editor.setSelection(match.range);
    editor.revealRangeInCenter(match.range);
    document.getElementById('find-status').textContent = `Match ${currentMatchIndex + 1} of ${currentMatches.length}`;
}

function doReplace() {
    const replaceText = document.getElementById('replace-input').value;
    const selection = editor.getSelection();
    
    // Ensure the current selection matches the find text (safety check)
    // For simplicity in this faux-popup, we just replace the current selection
    if (!selection.isEmpty()) {
        editor.executeEdits('source', [{ range: selection, text: replaceText }]);
        doFindNext(); // Move to next
    } else {
        doFindNext(); // Nothing selected, find first
    }
}

function doReplaceAll() {
    const findText = document.getElementById('find-input').value;
    const replaceText = document.getElementById('replace-input').value;
    if (!findText) return;

    const model = editor.getModel();
    const matches = model.findMatches(findText, false, false, false, null, true);
    
    if (matches.length === 0) {
        document.getElementById('find-status').textContent = "Nothing to replace.";
        return;
    }

    const edits = matches.map(m => ({ range: m.range, text: replaceText }));
    editor.executeEdits('source', edits);
    document.getElementById('find-status').textContent = `Replaced ${matches.length} occurrences.`;
}

// --- SURGICAL REPLACE LOGIC (Existing) ---
function showSurgicalReplace() {
    const modal = document.getElementById('surgical-modal-overlay');
    const textArea = document.getElementById('surg-text');
    if (!modal || !textArea) return;

    const selection = editor.getSelection();
    let sampleSchema = { ...SURGICAL_SCHEMA };
    if (selection && !selection.isEmpty()) {
        sampleSchema.start_line = selection.startLineNumber;
        sampleSchema.end_line = selection.endLineNumber;
        sampleSchema.start_column = selection.startColumn;
        sampleSchema.end_column = selection.endColumn;
        sampleSchema.replacement_code = "Your replacement text here...";
    } else {
        sampleSchema.start_line = 1;
        sampleSchema.end_line = 1;
        sampleSchema.replacement_code = "Your replacement text here...";
    }
    
    textArea.placeholder = JSON.stringify(sampleSchema, null, 2);
    textArea.value = '';

    modal.classList.remove('hidden');
    textArea.focus();
}

function applySurgicalReplace() {
    const textEl = document.getElementById('surg-text');
    if (!textEl.value) {
        cancelSurgicalReplace();
        return;
    }

    try {
        const data = JSON.parse(textEl.value);
        const rawStartLine = data.start_line;
        const rawEndLine = data.end_line;
        const rawStartCol = data.start_column;
        const rawEndCol = data.end_column;
        const text = data.replacement_code;

        if (rawStartLine == null || rawEndLine == null || text == null) {
            throw new Error('Missing required fields: start_line, end_line, replacement_code');
        }

        const sline = Number(rawStartLine);
        const eline = Number(rawEndLine);
        const tab = getActiveTab();
        
        if (!tab || !tab.model) throw new Error('No active tab.');

        const maxLine = tab.model.getLineCount();
        const startLine = Math.min(Math.max(sline, 1), maxLine);
        const endLine = Math.min(Math.max(eline, startLine), maxLine);

        const numericStartCol = rawStartCol != null ? Number(rawStartCol) : 1;
        const numericEndCol = rawEndCol != null ? Number(rawEndCol) : tab.model.getLineMaxColumn(endLine);
        
        const maxStartCol = tab.model.getLineMaxColumn(startLine);
        const maxEndCol = tab.model.getLineMaxColumn(endLine);

        const startColumn = Math.min(Math.max(numericStartCol || 1, 1), maxStartCol);
        const endColumn = Math.min(Math.max(numericEndCol || maxEndCol, 1), maxEndCol);

        const range = new monaco.Range(startLine, startColumn, endLine, endColumn);
        tab.model.pushEditOperations([], [{ range: range, text: text }], () => null);
        editor.revealRangeInCenter(range, monaco.editor.ScrollType.Smooth);
        cancelSurgicalReplace();
    } catch (e) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.create_alert) {
            window.pywebview.api.create_alert('JSON Parse Error', e.message);
        } else {
            alert('JSON Parse Error: ' + e.message);
        }
    }
}

function cancelSurgicalReplace() {
    const modal = document.getElementById('surgical-modal-overlay');
    if (modal) modal.classList.add('hidden');
    if (editor && typeof editor.focus === 'function') {
        editor.focus();
    }
}

function copySurgicalSchema() {
    const textArea = document.getElementById('surg-text');
    const schemaText = textArea.placeholder;
    navigator.clipboard.writeText(schemaText)
        .then(() => {
            const btn = document.getElementById('surg-copy-schema');
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => { btn.textContent = originalText; }, 1500);
        })
        .catch(err => {
            console.error('Failed to copy schema: ', err);
        });
}

// --- MONACO BOOT ---
function bootMonaco() {
  if (!window.require) { console.error('[monaco] AMD loader not present'); return; }
  window.require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
  window.require(['vs/editor/editor.main'], function (m) {
    monaco = m;
    const el = document.getElementById('editor');
    editor = monaco.editor.create(el, {
      model: null,
      automaticLayout: true,
      readOnly: !!BOOT.readOnly,
      minimap: { enabled: true },
      lineNumbers: 'on'
    });

    editor.onDidChangeCursorPosition(e => {
        const statusCursor = document.getElementById('status-cursor');
        if (statusCursor) {
            const { lineNumber, column } = e.position;
            statusCursor.textContent = `Ln ${lineNumber}, Col ${column}`;
        }
    });

    if (BOOT.theme) monaco.editor.setTheme(BOOT.theme);

    addTab(BOOT.path, BOOT.text);

    // Initial surgical replacement if passed via CLI args
    const tab = getActiveTab();
    if (tab) {
        if (BOOT.replaceText != null && BOOT.sline && BOOT.eline) {
            const startColumn = BOOT.scol || 1;
            const endColumn = BOOT.ecol || tab.model.getLineMaxColumn(BOOT.eline);
            const range = new monaco.Range(BOOT.sline, startColumn, BOOT.eline, endColumn);
            tab.model.pushEditOperations([], [{ range: range, text: BOOT.replaceText }], () => null);
            editor.setSelection(new monaco.Range(0,0,0,0));
            editor.revealRangeInCenter(range, monaco.editor.ScrollType.Smooth);
            if (BOOT.autosave) {
                setTimeout(doSave, 100);
            }
        } else if (BOOT.sline && BOOT.eline) {
            const range = new monaco.Range(BOOT.sline, 1, BOOT.eline, 1);
            editor.revealRangeInCenter(range, monaco.editor.ScrollType.Smooth);
            editor.setSelection(range);
        }
    }

    document.addEventListener('keydown', (e) => {
        const ctrl = e.ctrlKey || e.metaKey;
        if (ctrl && (e.key === 's' || e.key === 'S')) { e.preventDefault(); doSave(); }
        if (ctrl && (e.key === 'o' || e.key === 'O')) { e.preventDefault(); doOpen(); }
        // Bind Ctrl+F to our custom modal
        if (ctrl && (e.key === 'f' || e.key === 'F')) { e.preventDefault(); showFindReplace(); }
    }, true);

    // Expose Global Hooks
    window.__doNew = () => addTab(null, '');
    window.__doOpen = doOpen;
    window.__doSave = doSave;
    window.__doSaveAs = doSaveAs;
    window.__doUndo = () => getActiveTab()?.model.undo();
    window.__doRedo = () => getActiveTab()?.model.redo();
    window.__doCut = () => editor.getAction('editor.action.clipboardCutAction').run();
    window.__doCopy = () => editor.getAction('editor.action.clipboardCopyAction').run();
    window.__doPaste = () => editor.getAction('editor.action.clipboardPasteAction').run();
    
    // THE FIX: Point to our new function!
    window.__showFindReplace = showFindReplace;
    window.__showSurgicalReplace = showSurgicalReplace;

    // Event Listeners for Surgical
    document.getElementById('surg-apply').addEventListener('click', applySurgicalReplace);
    document.getElementById('surg-cancel').addEventListener('click', cancelSurgicalReplace);
    document.getElementById('surg-copy-schema').addEventListener('click', copySurgicalSchema);
    document.getElementById('surgical-modal-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'surgical-modal-overlay') cancelSurgicalReplace();
    });

    // Event Listeners for Find/Replace
    document.getElementById('btn-find-next').addEventListener('click', doFindNext);
    document.getElementById('btn-replace').addEventListener('click', doReplace);
    document.getElementById('btn-replace-all').addEventListener('click', doReplaceAll);
    document.getElementById('btn-find-close').addEventListener('click', closeFindReplace);
    document.getElementById('find-modal-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'find-modal-overlay') closeFindReplace();
    });

    // Escape Key Handler
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (!document.getElementById('surgical-modal-overlay').classList.contains('hidden')) {
                cancelSurgicalReplace();
            }
            if (!document.getElementById('find-modal-overlay').classList.contains('hidden')) {
                closeFindReplace();
            }
        }
    });
  });
}

// --- Tab Helper Functions ---
const getTab = (tabId) => tabs.find(t => t.id === tabId);
const getActiveTab = () => getTab(activeTabId);
const languageFromPath = (p) => {
    if (!p || !monaco) return 'plaintext';
    const ext = '.' + p.split('.').pop();
    const langs = monaco.languages.getLanguages();
    const hit = langs.find(l => Array.isArray(l.extensions) && l.extensions.includes(ext));
    return hit ? hit.id : 'plaintext';
}

function renderTabs() {
    const container = document.getElementById('tabs-container');
    container.innerHTML = '';
    tabs.forEach(tab => {
        const tabEl = document.createElement('div');
        tabEl.className = 'tab' + (tab.id === activeTabId ? ' active' : '');
        tabEl.onclick = () => switchTab(tab.id);
        const name = tab.path ? tab.path.split(/[\\/]/).pop() : 'Untitled';
        const closeIcon = tab.isDirty ? '●' : '&times;';
        tabEl.innerHTML = `<span>${name}</span><span class="tab-close" onclick="closeTab(event, ${tab.id})">${closeIcon}</span>`;
        container.appendChild(tabEl);
    });
    const activeTab = getActiveTab();
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_active_tab) {
         window.pywebview.api.set_active_tab(activeTab?.path || null, activeTab?.isDirty || false);
    }
    const statusFilepath = document.getElementById('status-filepath');
    if (statusFilepath) {
        statusFilepath.textContent = activeTab?.path || '[Untitled]';
    }
}

function switchTab(tabId) {
    if (activeTabId === tabId) return;
    const currentTab = getActiveTab();
    if (currentTab) {
        currentTab.viewState = editor.saveViewState();
    }
    activeTabId = tabId;
    const newTab = getActiveTab();
    editor.setModel(newTab ? newTab.model : null);
    if (newTab && newTab.viewState) {
        editor.restoreViewState(newTab.viewState);
    }
    editor.focus();
    renderTabs();
}

function addTab(path, text) {
    const existing = path ? tabs.find(t => t.path === path) : null;
    if (existing) {
        switchTab(existing.id);
        return;
    }
    const newTab = {
        id: nextTabId++,
        path: path,
        model: monaco.editor.createModel(text, languageFromPath(path)),
        viewState: null,
        isDirty: false
    };
    newTab.model.onDidChangeContent(() => {
        if (!newTab.isDirty) {
            newTab.isDirty = true;
            renderTabs();
        }
    });
    tabs.push(newTab);
    switchTab(newTab.id);
}

async function closeTab(event, tabId) {
    event.stopPropagation();
    const tabIdx = tabs.findIndex(t => t.id === tabId);
    if (tabIdx === -1) return;

    const tabToClose = getTab(tabId);
    if (tabToClose.isDirty) {
        const confirmed = await window.pywebview.api.confirm_dialog(
            'Unsaved Changes',
            'You have unsaved changes. Are you sure you want to close this tab?'
        );
        if (!confirmed) {
            return;
        }
    }

    const [removedTab] = tabs.splice(tabIdx, 1);
    removedTab.model.dispose();
    if (activeTabId === tabId) {
        const newActiveIdx = Math.max(0, tabIdx - 1);
        const newActiveTab = tabs.length > 0 ? tabs[newActiveIdx] : null;
        switchTab(newActiveTab ? newActiveTab.id : -1);
    }

    if (tabs.length === 0) {
        addTab(null, '');
    } else {
        renderTabs();
    }
}

// --- File Operations ---
async function doOpen() {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.open_dialog)) return;
    const res = await window.pywebview.api.open_dialog();
    if (res && res.path != null && typeof res.text === 'string') {
        addTab(res.path, res.text);
    }
}

async function doSave() {
    const tab = getActiveTab();
    if (!tab) return;
    const res = await window.pywebview.api.save_dialog(tab.model.getValue(), tab.path);
    if (res && res.saved && res.path) {
       tab.path = res.path;
       tab.isDirty = false;
       monaco.editor.setModelLanguage(tab.model, languageFromPath(tab.path));
       renderTabs();
    }
}

async function doSaveAs() {
    const tab = getActiveTab();
    if (!tab) return;
    const res = await window.pywebview.api.save_as_dialog(tab.model.getValue(), tab.path);
    if (res && res.saved && res.path) {
        tab.path = res.path;
        tab.isDirty = false;
        monaco.editor.setModelLanguage(tab.model, languageFromPath(tab.path));
        renderTabs();
    }
}

// --- Boot sequence ---
(function(){
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js';
  s.onload = () => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', bootMonaco) : bootMonaco();
  document.head.appendChild(s);
})();