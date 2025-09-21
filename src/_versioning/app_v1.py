#!/usr/bin/env python3
"""
Monaco Seed v8 — Suppresses harmless Qt warnings for a cleaner experience.
Refactored to be both a standalone app and an importable module.
"""
from __future__ import annotations
import argparse
import base64
import html
import json
import os
import sys
import contextlib

# Force Qt backend for stability
os.environ['PYWEBVIEW_GUI'] = 'qt'
os.environ.setdefault('PYWEBVIEW_LOG', 'info')

try:
    import qtpy  # noqa: F401
    from PySide6 import QtCore  # noqa: F401
except Exception as e:
    print(f"[fatal] Qt backend not available. Install: pip install qtpy PySide6\n{e}", file=sys.stderr)
    raise

try:
    import webview
    from webview import FileDialog
    from webview.menu import Menu, MenuAction, MenuSeparator
except Exception as e:
    print(f"[fatal] pywebview not available. Install: pip install pywebview\n{e}", file=sys.stderr)
    raise

# ---------------- helpers ----------------

def b64(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('ascii')

def load_text(path: str | None) -> str:
    if not path:
        return ''
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"<unable to read {html.escape(str(path))}>{e}"

# ---------------- HTML (CSP relaxed for Monaco) ----------------
HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self' https://cdn.jsdelivr.net https://unpkg.com;
                 style-src   'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com;
                 script-src  'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com;
                 font-src    https://cdn.jsdelivr.net https://unpkg.com;
                 img-src     'self' data:;
                 worker-src  blob:"> 
  <title>Monaco Seed</title>
  <style>
    html, body { 
        height: 100%; width: 100%; margin: 0; padding: 0; overflow: hidden; 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        display: flex;
        flex-direction: column;
    }
    #tabs-container {
        flex: 0 0 auto;
        display: flex;
        background-color: #252526;
        padding: 5px 5px 0 5px;
        overflow-x: auto;
    }
    .tab {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        background-color: #2D2D2D;
        color: #9e9e9e;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
        cursor: pointer;
        font-size: 14px;
        white-space: nowrap;
    }
    .tab.active {
        background-color: #1E1E1E;
        color: #ffffff;
    }
    .tab-close {
        margin-left: 10px;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
    }
    .tab:hover .tab-close { background-color: #3f3f3f; }
    .tab-close:hover { background-color: #5f5f5f; }
    #editor { 
        flex: 1 1 auto;
        min-height: 0;
    }
  </style>
  <script>
    const BOOT = JSON.parse(atob('%BOOT%'));
    
    // --- Global State ---
    let editor;
    let monaco;
    let tabs = [];
    let nextTabId = 0;
    let activeTabId = -1;

    function bootMonaco() {
      if (!window.require) { console.error('[monaco] AMD loader not present'); return; }
      window.require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
      window.require(['vs/editor/editor.main'], function (m) {
        monaco = m;
        const el = document.getElementById('editor');
        editor = monaco.editor.create(el, {
          model: null, // No model on startup
          automaticLayout: true,
          readOnly: !!BOOT.readOnly,
          minimap: { enabled: true },
          lineNumbers: 'on'
        });
        if (BOOT.theme) monaco.editor.setTheme(BOOT.theme);

        // Create initial tab from boot data
        addTab(BOOT.path, BOOT.text);
        if (BOOT.sline && BOOT.eline) {
            const r = new monaco.Range(BOOT.sline, 1, BOOT.eline, 1);
            editor.revealRangeInCenter(r, monaco.editor.ScrollType.Smooth);
            editor.setSelection(r);
        }

        document.addEventListener('keydown', (e) => {
            const ctrl = e.ctrlKey || e.metaKey;
            if (ctrl && (e.key === 's' || e.key === 'S')) { e.preventDefault(); doSave(); }
            if (ctrl && (e.key === 'o' || e.key === 'O')) { e.preventDefault(); doOpen(); }
        }, true);

        // --- Expose API on window for menus ---
        window.__doNew = () => addTab(null, '');
        window.__doOpen = doOpen;
        window.__doSave = doSave;
        window.__doSaveAs = doSaveAs;
        window.__doUndo = () => getActiveTab()?.model.undo();
        window.__doRedo = () => getActiveTab()?.model.redo();
        window.__doCut = () => editor.getAction('editor.action.clipboardCutAction').run();
        window.__doCopy = () => editor.getAction('editor.action.clipboardCopyAction').run();
        window.__doPaste = () => editor.getAction('editor.action.clipboardPasteAction').run();
        window.__doFind = () => editor.getAction('actions.find').run();
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
            const dirty = tab.isDirty ? '*' : '';
            tabEl.innerHTML = `<span>${dirty}${name}</span><span class="tab-close" onclick="closeTab(event, ${tab.id})">&times;</span>`;
            container.appendChild(tabEl);
        });
        const activeTab = getActiveTab();
        if (window.pywebview && window.pywebview.api && window.pywebview.api.set_active_tab) {
             window.pywebview.api.set_active_tab(activeTab?.path || null, activeTab?.isDirty || false);
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
    
    function closeTab(event, tabId) {
        event.stopPropagation();
        const tabIdx = tabs.findIndex(t => t.id === tabId);
        if (tabIdx === -1) return;

        // Simple close logic: no save prompt for now
        const [removedTab] = tabs.splice(tabIdx, 1);
        removedTab.model.dispose();

        if (activeTabId === tabId) {
            const newActiveIdx = Math.max(0, tabIdx - 1);
            const newActiveTab = tabs.length > 0 ? tabs[newActiveIdx] : null;
            switchTab(newActiveTab ? newActiveTab.id : -1);
        }
        
        if (tabs.length === 0) {
            addTab(null, ''); // Always have at least one tab
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
  </script>
</head>
<body>
  <div id="tabs-container"></div>
  <div id="editor"></div>
</body>
</html>"""

# ---------------- JS API ----------------
class Api:
    def __init__(self):
        self.window: webview.Window | None = None
        self._active_path: str | None = None
        self._active_is_dirty: bool = False

    def set_active_tab(self, path: str | None, is_dirty: bool):
        self._active_path = path
        self._active_is_dirty = is_dirty
        self._update_title()

    def open_dialog(self) -> dict:
        assert self.window is not None
        result = self.window.create_file_dialog(FileDialog.OPEN, allow_multiple=False, file_types=("All files (*.*)",))
        if not result or not isinstance(result, (list, tuple)) or not result[0]:
            return {'cancelled': True}
        path = result[0]
        text = load_text(path)
        return {'cancelled': False, 'path': path, 'text': text}

    def save_dialog(self, content: str, path: str | None) -> dict:
        return self._save_logic(content, path, force_dialog=False)

    def save_as_dialog(self, content: str, path: str | None) -> dict:
        return self._save_logic(content, path, force_dialog=True)

    def _save_logic(self, content: str, path: str | None, force_dialog: bool) -> dict:
        assert self.window is not None
        if not path or force_dialog:
            result = self.window.create_file_dialog(
                FileDialog.SAVE, 
                directory=os.path.dirname(path) if path else '', 
                save_filename=os.path.basename(path) if path else 'untitled.txt', 
                file_types=("All files (*.*)",)
            )
            if not result:
                return {'saved': False}
            path = result[0] if isinstance(result, (tuple, list)) and len(result) > 0 else result
        
        if not path:
             return {'saved': False}
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.set_active_tab(path, is_dirty=False)
            return {'saved': True, 'path': path}
        except Exception as e:
            self.window.create_alert('Save Error', f'Failed to save to {path}\n{e}')
            return {'saved': False, 'error': str(e)}

    def quit(self):
        if self.window:
            self.window.destroy()

    def _update_title(self):
        if not self.window:
            return
        name = os.path.basename(self._active_path) if self._active_path else 'Untitled'
        dirty = '*' if self._active_is_dirty else ''
        self.window.set_title(f"{dirty}{name} - Monaco Editor")

# ---------------- Launcher ----------------

def launch_editor(file=None, sline=None, eline=None, theme='vs-dark', lang=None, read_only=False):
    """
    Creates and runs a new Monaco editor window.
    This function blocks until the created window is closed.
    """
    path = os.path.abspath(file) if file else None
    text = load_text(path)

    api = Api()

    boot = {
        'text': text,
        'path': path,
        'sline': sline,
        'eline': eline,
        'theme': theme,
        'lang': lang,
        'readOnly': read_only,
    }

    html_text = HTML.replace('%BOOT%', b64(json.dumps(boot)))

    menu_items = [
        Menu('File', [
            MenuAction('New', lambda: api.window.evaluate_js('window.__doNew()')),
            MenuAction('Open', lambda: api.window.evaluate_js('window.__doOpen()')),
            MenuAction('Save', lambda: api.window.evaluate_js('window.__doSave()')),
            MenuAction('Save As...', lambda: api.window.evaluate_js('window.__doSaveAs()')),
            MenuSeparator(),
            MenuAction('Quit', api.quit)
        ]),
        Menu('Edit', [
            MenuAction('Undo', lambda: api.window.evaluate_js('window.__doUndo()')),
            MenuAction('Redo', lambda: api.window.evaluate_js('window.__doRedo()')),
            MenuSeparator(),
            MenuAction('Cut', lambda: api.window.evaluate_js('window.__doCut()')),
            MenuAction('Copy', lambda: api.window.evaluate_js('window.__doCopy()')),
            MenuAction('Paste', lambda: api.window.evaluate_js('window.__doPaste()')),
            MenuSeparator(),
            MenuAction('Find / Replace', lambda: api.window.evaluate_js('window.__doFind()')),
        ])
    ]

    win = webview.create_window(
        title="Monaco Editor",
        html=html_text,
        width=1100,
        height=750,
        js_api=api,
        confirm_close=True,
        menu=menu_items
    )
    api.window = win

    # Use a context manager to temporarily suppress stderr during startup
    # to hide harmless Qt warnings that can clutter the log.
    with open(os.devnull, 'w') as f, contextlib.redirect_stderr(f):
        webview.start(gui='qt', debug=False)


# ---------------- main ----------------

def main():
    """Parses command-line arguments and launches the editor."""
    ap = argparse.ArgumentParser(description='Monaco Viewer')
    ap.add_argument('--file', type=str, help='File to open')
    ap.add_argument('--sline', type=int, help='Start line to reveal')
    ap.add_argument('--eline', type=int, help='End line to reveal')
    ap.add_argument('--theme', type=str, default='vs-dark', help='Theme: vs | vs-dark | hc-black')
    ap.add_argument('--lang', type=str, help='Force Monaco language id (optional)')
    ap.add_argument('--read-only', action='store_true', help='Set editor to read-only mode')
    args = ap.parse_args()

    launch_editor(
        file=args.file,
        sline=args.sline,
        eline=args.eline,
        theme=args.theme,
        lang=args.lang,
        read_only=args.read_only
    )

if __name__ == '__main__':
    main()
