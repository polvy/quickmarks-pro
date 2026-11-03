# Quickmarks Pro - paste this whole script into a Python shelf tool.
# Quickmarks are stored inside the .hip itself (userData on the root node, key
# 'quickmarksPro'), so they travel with the file. Save the .hip to keep them.
# If the hip has none yet, quickmarks from earlier versions of this tool (userData keys
# 'advancedQuickmarks' / 'networkShortcuts', or $HIP/networkShortcuts.json) are imported once.
#
# Popup keys: type to filter | Up/Down select | Tab complete name | Enter go
#             Ctrl+S save here | Ctrl+D delete | Esc cancel
# Empty field = most recently used quickmarks first. Missing nodes are greyed out
# (button "Remove missing" cleans them). Saving can also remember selected nodes.
import json
import os
import time

import hou

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt

STYLE = """
QDialog { background: #2b2b2b; border: 1px solid #6a6a6a; }
QLabel { color: #dddddd; font-size: 12px; }
QLabel#hint { color: #8a8a8a; font-size: 11px; }
QCheckBox { color: #dddddd; }
QLineEdit { background: #1e1e1e; color: #ffffff; border: 1px solid #555555;
            padding: 6px; font-size: 15px; selection-background-color: #c9772b; }
QListWidget { background: #232323; color: #eeeeee; border: 1px solid #444444;
              font-size: 13px; outline: 0; }
QListWidget::item { padding: 5px 6px; }
QListWidget::item:selected { background: #c9772b; color: #ffffff; }
QPushButton { background: #3c3c3c; color: #eeeeee; border: 1px solid #666666;
              padding: 5px 14px; }
QPushButton:hover { background: #4d4d4d; }
"""


USERDATA_KEY = "quickmarksPro"
OLD_USERDATA_KEYS = ("advancedQuickmarks", "networkShortcuts")  # earlier names, import only


def store_path():  # legacy json location, only used for the one-time import
    return os.path.join(hou.expandString("$HIP"), "networkShortcuts.json")


def _clean(data):
    # accept both the plain list and the {"shortcuts": [...]} format
    if isinstance(data, dict):
        data = data.get("shortcuts", [])
    if not isinstance(data, list):
        return []
    return [i for i in data if isinstance(i, dict) and "name" in i and "path" in i]


def load_items():
    raw = hou.node("/").userData(USERDATA_KEY)
    for old_key in OLD_USERDATA_KEYS:  # earlier versions of this tool
        if raw is None:
            raw = hou.node("/").userData(old_key)
    if raw is not None:
        try:
            return _clean(json.loads(raw))
        except Exception:
            return []
    # nothing stored in this hip yet: import the old json once, if there is one
    try:
        with open(store_path(), "r") as f:
            return _clean(json.load(f))
    except Exception:
        return []


def save_items(items):
    with hou.undos.disabler():
        hou.node("/").setUserData(USERDATA_KEY, json.dumps(items))


def _used_map():
    m = getattr(hou, "_quickmarks_pro_used", None)
    if m is None:
        m = {}
        hou._quickmarks_pro_used = m
    return m


def used_time(it):
    key = (hou.hipFile.path(), it["name"])
    return max(it.get("used", 0), _used_map().get(key, 0))


def touch(it):  # in memory only, so jumping doesn't mark the scene as modified
    _used_map()[(hou.hipFile.path(), it["name"])] = time.time()


def selected_in(pwd):
    return [n.path() for n in hou.selectedNodes()
            if n.parent() is not None and n.parent().path() == pwd.path()]


def find_pane():
    pane = hou.ui.paneTabUnderCursor()
    if isinstance(pane, hou.NetworkEditor):
        return pane
    return hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)


def default_name(items):
    names = {i["name"].lower() for i in items}
    n = len(items) + 1
    while "network%d" % n in names:
        n += 1
    return "Network%d" % n


class Popup(QtWidgets.QDialog):
    def __init__(self, pane, items, parent=None):
        super(Popup, self).__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.pane = pane
        self.items = items
        self.mode = "list"
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(480)

        lay = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel()
        self.edit = QtWidgets.QLineEdit()
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumHeight(200)
        self.chk = QtWidgets.QCheckBox()
        self.hint = QtWidgets.QLabel()
        self.hint.setObjectName("hint")
        self.sel_paths = []
        row = QtWidgets.QHBoxLayout()
        self.btn_a = QtWidgets.QPushButton()
        self.btn_b = QtWidgets.QPushButton()
        self.btn_c = QtWidgets.QPushButton("Cancel (Esc)")
        self.btn_d = QtWidgets.QPushButton()
        self.btn_del = QtWidgets.QPushButton("Delete (Ctrl+D)")
        self._last_delete = 0.0
        row.addWidget(self.btn_del)
        row.addWidget(self.btn_d)
        row.addStretch(1)
        row.addWidget(self.btn_c)
        row.addWidget(self.btn_b)
        row.addWidget(self.btn_a)
        for w in (self.label, self.edit, self.chk, self.list, self.hint):
            lay.addWidget(w)
        lay.addLayout(row)

        self.edit.textChanged.connect(self.refilter)
        self.edit.returnPressed.connect(self.on_enter)
        self.list.itemClicked.connect(lambda _i: self.jump())
        self.btn_a.clicked.connect(self.on_enter)
        self.btn_b.clicked.connect(self.on_secondary)
        self.btn_c.clicked.connect(self.close)
        self.btn_d.clicked.connect(self.remove_missing)
        self.btn_del.clicked.connect(self.delete_current)

        # Esc cancels from anywhere in the popup (field, list or buttons)
        Shortcut = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
        self._esc = Shortcut(QtGui.QKeySequence(Qt.Key_Escape), self)
        self._esc.setContext(Qt.WindowShortcut)
        self._esc.activated.connect(self.close)

        # Houdini grabs some key combos (Ctrl+D, Ctrl+S, ...) before widgets see them,
        # so the popup watches keys at application level while it is open. Our filter is
        # installed after Houdini's, which makes it run first.
        QtWidgets.QApplication.instance().installEventFilter(self)

        if items:
            self.list_mode()
        else:
            self.save_mode(default_name(items))

    # modes
    def list_mode(self):
        self.mode = "list"
        self.label.setText("Quickmarks Pro  -  go to quickmark")
        self.list.show()
        self.btn_a.setText("Go")
        self.btn_b.setText("Save here (Ctrl+S)")
        self.btn_b.show()
        self.btn_del.show()
        self.chk.hide()
        self.edit.clear()
        self.refilter()
        self.center()

    def save_mode(self, name):
        self.mode = "save"
        self.label.setText("Name for %s" % self.pane.pwd().path())
        self.list.hide()
        self.btn_a.setText("Save")
        self.btn_b.hide()
        self.btn_del.hide()
        self.btn_d.hide()
        self.hint.setText("Enter: save    Esc: cancel")
        self.sel_paths = selected_in(self.pane.pwd())
        n = len(self.sel_paths)
        self.chk.setVisible(n > 0)
        self.chk.setChecked(True)
        self.chk.setText("Also remember selected node%s (%d)" % ("s" if n != 1 else "", n))
        self.edit.setText(name)
        self.edit.selectAll()
        self.center()

    def center(self):
        self.adjustSize()
        screen = (QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
                  or QtWidgets.QApplication.primaryScreen())
        c = screen.availableGeometry().center()
        self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)

    # list
    def refilter(self, *_):
        if self.mode != "list":
            return
        q = self.edit.text().lower().strip()
        ranked = []
        for it in self.items:
            n = it["name"].lower()
            if q and n == q:
                r = 0
            elif n.startswith(q):
                r = 1
            elif q in n:
                r = 2
            else:
                continue
            ranked.append((r, -used_time(it), n, it))
        ranked.sort(key=lambda t: t[:3])

        self.list.clear()
        for _r, _u, _n, it in ranked:
            missing = hou.node(it["path"]) is None
            text = "%s     %s" % (it["name"], it["path"])
            sel = it.get("selected") or []
            if sel:
                text += "   > %s%s" % (sel[0].rsplit("/", 1)[-1],
                                       " +%d" % (len(sel) - 1) if len(sel) > 1 else "")
            if missing:
                text += "   (missing)"
            li = QtWidgets.QListWidgetItem(text)
            li.setData(Qt.UserRole, it["name"])
            if missing:
                li.setForeground(QtGui.QBrush(QtGui.QColor("#777777")))
                li.setToolTip("This node no longer exists")
            self.list.addItem(li)
        if self.list.count():
            self.list.setCurrentRow(0)

        n_missing = sum(1 for i in self.items if hou.node(i["path"]) is None)
        self.btn_d.setText("Remove missing (%d)" % n_missing)
        self.btn_d.setVisible(n_missing > 0)
        self.hint.setText("Enter: go    Tab: complete    Ctrl+S: save here    "
                          "Ctrl+D: delete    Esc: cancel")

    def current(self):
        li = self.list.currentItem()
        if li is None:
            return None
        for it in self.items:
            if it["name"] == li.data(Qt.UserRole):
                return it

    # actions
    def commit(self, name, selected):
        """Save (or update) a quickmark for the current network location."""
        name = name.strip()
        if not name:
            return
        b = self.pane.visibleBounds()
        entry = {"name": name,
                 "path": self.pane.pwd().path(),
                 "bounds": [b.min()[0], b.min()[1], b.max()[0], b.max()[1]],
                 "selected": selected,
                 "used": time.time()}
        existed = any(i["name"].lower() == name.lower() for i in self.items)
        self.items[:] = [i for i in self.items if i["name"].lower() != name.lower()]
        self.items.append(entry)
        save_items(self.items)
        hou.ui.setStatusMessage("Quickmark %s: %s -> %s  (save the .hip to keep it)"
                                % ("updated" if existed else "saved", name, entry["path"]))
        self.close()

    def on_enter(self):
        text = self.edit.text().strip()
        if self.mode == "save":
            self.commit(text, self.sel_paths if self.chk.isChecked() else [])
        elif self.current():
            self.jump()
        elif text:
            # no match: save the current location under the typed name, in one go
            self.commit(text, selected_in(self.pane.pwd()))

    def save_here(self):
        # typed name -> save immediately (also works when the name only partly
        # matches an existing quickmark); empty field -> ask for a name
        text = self.edit.text().strip()
        if text:
            self.commit(text, selected_in(self.pane.pwd()))
        else:
            self.save_mode(default_name(self.items))

    def on_secondary(self):
        self.save_here()

    def jump(self):
        it = self.current()
        if not it:
            return
        node = hou.node(it["path"])
        if node is None:
            hou.ui.setStatusMessage("%s no longer exists" % it["path"],
                                    severity=hou.severityType.Warning)
            self.hint.setText("%s no longer exists (Ctrl+D to delete it)" % it["path"])
            return
        self.close()
        touch(it)
        self.pane.setPwd(node)
        sel = [n for n in (hou.node(p) for p in it.get("selected", [])) if n is not None]
        if sel:
            sel[0].setSelected(True, clear_all_selected=True)
            for n in sel[1:]:
                n.setSelected(True)
            self.pane.setCurrentNode(sel[0])
        if it.get("bounds"):
            self.pane.setVisibleBounds(hou.BoundingRect(*it["bounds"]))

    def remove_missing(self):
        self.items[:] = [i for i in self.items if hou.node(i["path"]) is not None]
        save_items(self.items)
        if self.items:
            self.refilter()
        else:
            self.save_mode(default_name(self.items))
            self.center()

    def delete_if_list(self):
        if self.mode == "list":
            self.delete_current()

    def save_if_list(self):
        if self.mode == "list":
            self.save_here()

    def delete_current(self):
        now = time.time()
        if now - self._last_delete < 0.2:  # a key can reach us by two routes: ignore the repeat
            return
        self._last_delete = now
        it = self.current()
        if it:
            self.items.remove(it)
            save_items(self.items)
            if self.items:
                self.refilter()
            else:
                self.save_mode(default_name(self.items))

    def move_sel(self, step):
        if self.list.count():
            r = self.list.currentRow() + step
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, r)))

    def complete(self):
        it = self.current()
        if it:
            self.edit.setText(it["name"])

    def key_action(self, ev):
        k, mods = ev.key(), ev.modifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        if k == Qt.Key_Escape:
            return self.close
        if self.mode != "list":
            return None
        if k == Qt.Key_Down:
            return lambda: self.move_sel(1)
        if k == Qt.Key_Up:
            return lambda: self.move_sel(-1)
        if k == Qt.Key_Tab:
            return self.complete
        if k == Qt.Key_D and ctrl:
            return self.delete_current
        if k == Qt.Key_S and ctrl:
            return self.save_here
        return None

    def eventFilter(self, obj, ev):
        t = ev.type()
        if self.isVisible() and t in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
            action = self.key_action(ev)
            if action is not None:
                if t == QtCore.QEvent.ShortcutOverride:
                    ev.accept()  # we want this key as a normal key press
                elif not (ev.isAutoRepeat() and action in (self.delete_current, self.save_here)):
                    action()
                return True
        return super(Popup, self).eventFilter(obj, ev)

    def closeEvent(self, ev):
        QtWidgets.QApplication.instance().removeEventFilter(self)
        super(Popup, self).closeEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
        else:
            super(Popup, self).keyPressEvent(ev)


def run():
    pane = find_pane()
    if pane is None:
        hou.ui.setStatusMessage("No network editor found", severity=hou.severityType.Warning)
        return
    dlg = Popup(pane, load_items(), hou.qt.mainWindow())
    dlg.center()
    dlg.show()
    dlg.edit.setFocus()
    # modal loop keeps the dialog alive (exec in PySide6, exec_ in PySide2)
    try:
        (getattr(dlg, "exec", None) or dlg.exec_)()
    finally:
        QtWidgets.QApplication.instance().removeEventFilter(dlg)


run()
