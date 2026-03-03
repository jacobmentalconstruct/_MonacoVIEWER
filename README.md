# **Monaco Viewer**

A lightweight, cross-platform desktop editor and command-line utility powered by Python. It uses the same Monaco engine that drives VS Code and is designed to be used as a standalone code viewer, a surgical replacement tool for AI agents, and a headless script for fast regex manipulations.

## **Core Features**

* **Modern Editing Experience**: Leverages the Monaco Editor for a fluid, familiar interface with rich syntax highlighting.  
* **Cross-Platform**: Runs consistently on Windows, macOS, and Linux.  
* **Tabbed Interface**: Manage multiple files in a clean, tabbed layout with unsaved-changes indicators.  
* **Hybrid Functionality**: Use it as a quick-launch GUI app or as a powerful command-line tool.  
* **Surgical & Headless Modes**: Perform complex, UI-assisted replacements or lightning-fast, headless regex substitutions from your scripts.

## **Installation**

The project uses a standard Python virtual environment (.venv) to manage dependencies.

1. **Prerequisites**: Ensure you have **Python 3.10, 3.11, or 3.12** installed. (Python 3.11 is recommended for maximum compatibility with PySide6 and pywebview).  
2. **Clone the Repository**:  
   git clone \[https://github.com/jacobmentalconstruct/\_MonacoVIEWER.git\](https://github.com/jacobmentalconstruct/\_MonacoVIEWER.git)  
   cd \_MonacoVIEWER

3. **Setup Environment**:  
   * **Windows**: Run the automated setup script:  
     setup\_env.bat

   * **Linux/macOS**:  
     python3 \-m venv .venv  
     source .venv/bin/activate  
     pip install \-r requirements.txt

## **Usage**

### **Launch Command**

Once the environment is initialized, launch the application using the module path through your virtual environment:  
**Windows:**  
.venv\\Scripts\\python \-m src.app \--file /path/to/your/file.js

**Linux/macOS:**  
./.venv/bin/python \-m src.app \--file /path/to/your/file.js

### **Command-Line Integration**

#### **1\. Headless Regex Replacement (Fast & Scriptable)**

For simple find-and-replace operations in scripts without launching the UI:  
.venv\\Scripts\\python \-m src.app \--file "config.ini" \--regex-find "old\_api\_key" \--regex-replace "new\_secret\_key"

#### **2\. Surgical Text Replacement (Precise & UI-Assisted)**

For complex edits that require precise line/column accuracy, this briefly launches the UI to perform the operation.  
.venv\\Scripts\\python \-m src.app \--file "config.txt" \--sline 10 \--eline 12 \--replace-text "\#\# NEW HEADER \#\#" \--autosave

## **Command-Line Options**

| Argument | Description |
| :---- | :---- |
| \--file | **Required.** Path to the file to open or process. |
| \--regex-find | **\[HEADLESS\]** A regex pattern to find. |
| \--regex-replace | **\[HEADLESS\]** The replacement string for the regex pattern. |
| \--sline / \--eline | **\[UI\]** The starting and ending line numbers for selection. |
| \--scol / \--ecol | **\[UI\]** The starting and ending column numbers for selection. |
| \--replace-text | **\[UI\]** The text to insert into the specified range. |
| \--autosave | **\[UI\]** Automatically save and exit after a surgical replacement. |
| \--theme | **\[UI\]** Sets the editor theme (vs or vs-dark). |
| \--lang | **\[UI\]** Forces a specific syntax highlighting language. |
| \--read-only | **\[UI\]** Opens the file in read-only mode. |

## **License**

This project is licensed under the MIT License \- see the LICENSE file for details.