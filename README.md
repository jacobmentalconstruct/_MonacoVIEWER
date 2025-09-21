# **Monaco Viewer**

A lightweight, cross-platform desktop editor and command-line utility powered by Python. It uses the same Monaco engine that drives VS Code and is designed to be used as a standalone code viewer, a surgical replacement tool for AI agents, and a headless script for fast regex manipulations.

## **Core Features**

* **Modern Editing Experience**: Leverages the Monaco Editor for a fluid, familiar interface with rich syntax highlighting.  
* **Cross-Platform**: Runs consistently on Windows, macOS, and Linux.  
* **Tabbed Interface**: Manage multiple files in a clean, tabbed layout with unsaved-changes indicators.  
* **Hybrid Functionality**: Use it as a quick-launch GUI app or as a powerful command-line tool.  
* **Surgical & Headless Modes**: Perform complex, UI-assisted replacements or lightning-fast, headless regex substitutions from your scripts.

## **Installation**

The project uses Conda to manage its environment and dependencies.

1. **Prerequisites**: Ensure you have [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution) installed.  
2. **Clone the Repository**:  
   git clone \[https://github.com/jacobmentalconstruct/\_MonacoVIEWER.git\](https://github.com/jacobmentalconstruct/\_MonacoVIEWER.git)  
   cd \_MonacoVIEWER

3. **Create the Conda Environment**:  
   conda env create \-f environment.yml

4. **Activate the Environment**:  
   conda activate monaco-viewer-env

## **Usage**

### **As a Standalone App (UI Mode)**

To launch the editor, simply run the launcher script:  
python start\_app.py \--file /path/to/your/file.js

### **Programmatic & Command-Line Integration**

#### **1\. Headless Regex Replacement (Fast & Scriptable)**

For simple find-and-replace operations in scripts, you can run the app in a truly headless mode that does not launch the UI.  
**Example:** To replace all occurrences of old\_api\_key in a configuration file:  
python start\_app.py \--file "config.ini" \\  
\--regex-find "old\_api\_key" \\  
\--regex-replace "new\_super\_secret\_key"

#### **2\. Surgical Text Replacement (Precise & UI-Assisted)**

For complex edits from AI agents or scripts that require precise line/column accuracy, use the surgical replacement flags. This will briefly launch the UI to perform the operation.  
**Example:** To replace lines 10-12 of config.txt and save automatically:  
python start\_app.py \--file "config.txt" \\  
\--sline 10 \--eline 12 \\  
\--replace-text "\#\# NEW CONFIGURATION \#\#\\nkey \= value" \\  
\--autosave

#### **All Command-Line Options**

| Argument | Description |
| :---- | :---- |
| \--file | **Required.** The path to the file. |
| \--regex-find | **\[HEADLESS\]** A regex pattern to find. |
| \--regex-replace | **\[HEADLESS\]** The replacement string for the regex pattern. |
| \--sline | **\[UI\]** The starting line number for selection/replacement. |
| \--eline | **\[UI\]** The ending line number for selection/replacement. |
| \--scol | **\[UI\]** The starting column number for replacement. |
| \--ecol | **\[UI\]** The ending column number for replacement. |
| \--replace-text | **\[UI\]** The text to insert into the specified range. |
| \--autosave | **\[UI\]** Automatically save after a surgical replacement. |
| \--theme | **\[UI\]** Sets the editor theme. Options: vs, vs-dark. |
| \--lang | **\[UI\]** Forces a specific syntax highlighting language. |
| \--read-only | **\[UI\]** Opens the file in read-only mode. |

## **Contributing**

Contributions are welcome\! If you have ideas for new features or have found a bug, please feel free to open an issue or submit a pull request.

## **License**

This project is licensed under the MIT License \- see the [LICENSE.md](http://docs.google.com/LICENSE.md) file for details.