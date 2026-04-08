<?xml version="1.0" encoding="utf-8"?>
<!-- Created by Leo: https://leo-editor.github.io/leo-editor/leo_toc.html -->
<leo_file xmlns:leo="https://leo-editor.github.io/leo-editor/namespaces/leo-python-editor/1.1" >
<leo_header file_format="2"/>
<globals/>
<preferences/>
<find_panel_settings/>
<vnodes>
<v t="zxc.20260315205826.2"><vh>Settings README</vh></v>
<v t="zxc.20260315205826.3"><vh>@settings</vh>
<v t="zxc.20260315210026.1"><vh>@string font-family = Maple Mono NF CN</vh></v>
<v t="zxc.20260315205956.1"><vh>@string theme-name = EKRDark</vh></v>
<v t="zxc.20260315205826.4"><vh>@enabled-plugins</vh></v>
<v t="zxc.20260315205826.5"><vh>@keys</vh>
<v t="zxc.20260315205826.6"><vh>@shortcuts</vh></v>
</v>
</v>
</vnodes>
<tnodes>
<t tx="zxc.20260315205826.2">myLeoSettings.leo personal settings file created Sun Mar 15 20:58:26 2026

Only nodes that are descendants of the @settings node are read.

Only settings you need to modify should be in this file, do
not copy large parts of leoSettings.py here.

For more information see https://leo-editor.github.io/leo-editor/customizing.html</t>
<t tx="zxc.20260315205826.3"></t>
<t tx="zxc.20260315205826.4"># Leo loads plugins in the order they appear here.
# The children of this node are *not* loaded.

# This node *MUST* be a child of the @settings node to take effect.

# **Important**: to change these defaults, put
# an @enabled-plugins node in myLeoSettings.leo.

# Standard plugins...

plugins_menu.py     # Adds 'Plugins' menu.
contextmenu.py      # Required by the vim.py and xemacs.py plugins.
mod_scripting.py
nav_qt.py           # Forward/back buttons &amp; goto-next/prev-history-node
nodetags.py
quicksearch.py      # Nav pane.
todo.py             # Task pane.
viewrendered.py     # (Or viewrendered3.py) Plugins menu support.
leo_to_html_outline_viewer.py  # Self-contained HTML Outline Viewer
vim.py</t>
<t tx="zxc.20260315205826.5"></t>
<t tx="zxc.20260315205826.6"># You can define keyboard shortcuts here of the form:
#
#    some-command Shift-F5
vim-open-node=Ctrl-X
</t>
<t tx="zxc.20260315205956.1"></t>
<t tx="zxc.20260315210026.1"></t>
</tnodes>
</leo_file>
