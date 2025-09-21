#!/usr/bin/env python3
"""
Monaco Viewer - A lightweight, cross-platform code editor.
Refactored into separate UI files and designed for both standalone use
and programmatic integration via command-line hooks.
"""
from __future__ import annotations
import argparse
import base64
import html
import json
import os
import sys
import contextlib
import re 

# Force Qt backend for stability
os.environ['PYWEBVIEW_GUI'] = 'qt'
os.environ.setdefault('PYWEBVIEW_LOG', 'info')

try:
    import qtpy
    from PySide6 import QtCore
    from PySide6.QtGui import QIcon # Used for setting the window icon
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
    """Encodes a string into Base64 for safe embedding in HTML."""
    return base64.b64encode(s.encode('utf-8')).decode('ascii')

def load_text(path: str | None) -> str:
    """Safely loads text from a file path."""
    if not path:
        return ''
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        # This function is called before the window exists, so we print to console.
        print(f"[error] Failed to read file: {path}\n{e}", file=sys.stderr)
        return f"<unable to read {html.escape(str(path))}>"

# ---------------- JS API ----------------
class Api:
    """
    The API class exposed to the JavaScript frontend.
    All methods here can be called from JS using `window.pywebview.api.*`.
    """
    def __init__(self):
        self.window: webview.Window | None = None
        self._active_path: str | None = None
        self._active_is_dirty: bool = False
        self._boot: dict | None = None

    def get_boot_data(self) -> dict:
        return self._boot or {}

    def create_alert(self, title: str, message: str):
        """Allows JS to show a native alert dialog."""
        if self.window:
            self.window.create_alert(title, message)

    def confirm_dialog(self, title: str, message:str) -> bool:
        """Allows JS to show a native confirmation dialog."""
        if self.window:
            return self.window.create_confirmation_dialog(title, message)
        return False

    def set_active_tab(self, path: str | None, is_dirty: bool):
        """Called by JS to keep the backend aware of the current file state."""
        self._active_path = path
        self._active_is_dirty = is_dirty
        self._update_title()

    def open_dialog(self) -> dict:
        """Opens a native file dialog to select a file to open."""
        assert self.window is not None
        result = self.window.create_file_dialog(FileDialog.OPEN, allow_multiple=False, file_types=("All files (*.*)",))
        if not result or not isinstance(result, (list, tuple)) or not result[0]:
            return {'cancelled': True}
        path = result[0]
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return {'cancelled': False, 'path': path, 'text': text}
        except Exception as e:
            self.window.create_alert('File Open Error', f'Failed to read file:\n{path}\n\n{e}')
            return {'cancelled': True}

    def save_dialog(self, content: str, path: str | None) -> dict:
        """Handles the logic for saving a file, prompting for a path if needed."""
        return self._save_logic(content, path, force_dialog=False)

    def save_as_dialog(self, content: str, path: str | None) -> dict:
        """Handles the logic for "Save As...", always forcing a path dialog."""
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
        """Closes the application window."""
        if self.window:
            self.window.destroy()

    def _update_title(self):
        """Updates the window title bar with the current file name and dirty status."""
        if not self.window:
            return
        base = os.path.basename(self._active_path) if self._active_path else 'Untitled'
        # Hide NamedTemporaryFile suffixes like "Untitled-xyz123.txt"
        if base.lower().startswith("untitled-") and base.lower().endswith(".txt"):
            base = "Untitled"
        dirty_indicator = '●' if self._active_is_dirty else ''
        self.window.set_title(f"{base}{dirty_indicator} - Monaco Viewer")

# ---------------- Launcher ----------------
def load_and_combine_ui() -> str:
    """Reads the separate UI files and combines them into a single HTML string."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(script_dir, 'index.html'), 'r', encoding='utf-8') as f:
            html_template = f.read()
        with open(os.path.join(script_dir, 'style.css'), 'r', encoding='utf-8') as f:
            css_text = f.read()
        with open(os.path.join(script_dir, 'index.js'), 'r', encoding='utf-8') as f:
            js_text = f.read()
    except FileNotFoundError as e:
        print(f"[fatal] UI file not found: {e}. Ensure index.html, style.css, and index.js are in the src/ directory.", file=sys.stderr)
        sys.exit(1)
    return html_template.replace('%CSS%', css_text).replace('%JS%', js_text)

def launch_editor(file=None, sline=None, eline=None, scol=None, ecol=None,
                  replace_text=None, autosave=False, theme='vs-dark',
                  lang=None, read_only=False):
    # use the module-level os
    path = os.path.abspath(file) if file else None
    text = load_text(path)
    base = os.path.basename(path) if path else ""
    is_untitled = (not base) or (base.lower().startswith("untitled-") and base.lower().endswith(".txt"))
    display_name = "Untitled" if is_untitled else base

    boot = {
        'text': text, 'path': path, 'sline': sline, 'eline': eline, 'scol': scol, 'ecol': ecol,
        'replaceText': replace_text, 'autosave': autosave, 'theme': theme, 'lang': lang,
        'readOnly': read_only, 'displayName': display_name, 'isUntitled': is_untitled,
    }
    api = Api()
    api._boot = boot
    final_html = load_and_combine_ui().replace('%BOOT%', b64(json.dumps(boot)))
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
            MenuSeparator(),
            MenuAction('Agent Surgical Replace...', lambda: api.window.evaluate_js('window.__showSurgicalReplace()'))
        ])
    ]

    win = webview.create_window(
        title="Monaco Viewer", html=final_html, width=1100, height=750,
        js_api=api, confirm_close=True, menu=menu_items
    )
    api.window = win

    def set_icon():
        """This function runs after the GUI loop starts, ensuring the native window exists."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'monaco-viewer-icon.png')
        if webview.windows and hasattr(webview.windows[0], 'gui_window'):
            native_win = webview.windows[0].gui_window
            if native_win and os.path.exists(icon_path):
                native_win.setWindowIcon(QIcon(icon_path))

    with open(os.devnull, 'w') as f, contextlib.redirect_stderr(f):
        webview.start(set_icon, gui='qt', debug=False)

# ---------------- main ----------------

def main():
    """Parses command-line arguments and launches the editor."""
    ap = argparse.ArgumentParser(description='Monaco Viewer - A lightweight code editor and command-line manipulator.')
    
    # --- UI-based arguments ---
    ap.add_argument('--file', nargs='?', default=None, help='Path to file to open. Omit to start with an Untitled buffer.')
    ap.add_argument('--untitled', action='store_true', help='Ignore --file and start a new Untitled buffer.')
    ap.add_argument('--sline', type=int, help='The starting line number for selection/replacement.')
    ap.add_argument('--eline', type=int, help='The ending line number for selection/replacement.')
    ap.add_argument('--scol', type=int, help='The starting column number for replacement.')
    ap.add_argument('--ecol', type=int, help='The ending column number for replacement.')
    ap.add_argument('--replace-text', type=str, help='The text to insert into the specified range.')
    ap.add_argument('--autosave', action='store_true', help='Automatically save the file after a replacement.')
    ap.add_argument('--theme', type=str, default='vs-dark', help='Sets the editor theme. Options: vs, vs-dark.')
    ap.add_argument('--lang', type=str, help='Forces a specific syntax highlighting language.')
    ap.add_argument('--read-only', action='store_true', help='Opens the file in read-only mode.')

    # --- New Headless Regex Arguments ---
    ap.add_argument('--regex-find', type=str, help='[HEADLESS MODE] A regex pattern to find.')
    ap.add_argument('--regex-replace', type=str, help='[HEADLESS MODE] The replacement string for the regex pattern.')

    args = ap.parse_args()

    # --- Headless Mode Logic ---       
    if args.regex_find and args.regex_replace:
        if not args.file:
            print("[error] --file is required for headless regex mode.", file=sys.stderr)
            sys.exit(2)
        if not os.path.exists(args.file):        
            print(f"[error] File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content, count = re.subn(args.regex_find, args.regex_replace, content)

            if content != new_content:
                with open(args.file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Successfully made {count} replacement(s) in {args.file}")
            else:
                print("No matches found. File was not changed.")
        except Exception as e:
            print(f"[error] An error occurred during headless regex replacement: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Exit after headless operation is complete
        sys.exit(0)


    # --- UI Mode Logic (if not in headless mode) ---
    # Create a real temp file if no --file was given (or --untitled used),
    # so save/dirty workflows behave normally across platforms.
    if args.untitled or args.file is None:
        from tempfile import NamedTemporaryFile
        tmp = NamedTemporaryFile(mode="w+", suffix=".txt", prefix="Untitled-", delete=False)
        tmp.close()
        args.file = tmp.name

    # Infer language if not provided
    if not args.lang and args.file:
        ext = os.path.splitext(args.file)[1].lower()
        args.lang = {
            '.py':'python','.js':'javascript','.ts':'typescript','.json':'json',
            '.md':'markdown','.html':'html','.css':'css','.txt':'plaintext',
            '.c':'c','.cpp':'cpp','.h':'c','.hpp':'cpp','.sh':'shell','.ini':'ini',
        }.get(ext, 'plaintext')
    launch_editor(
        file=args.file, sline=args.sline, eline=args.eline, scol=args.scol, ecol=args.ecol,
        replace_text=args.replace_text, autosave=args.autosave, theme=args.theme,
        lang=args.lang, read_only=args.read_only
    )

if __name__ == '__main__':
    main()


