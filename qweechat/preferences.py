# -*- coding: utf-8 -*-
#
# preferences.py - preferences dialog box
#
# Copyright (C) 2016 Ricky Brent <ricky@rickybrent.com>
#
# This file is part of QWeeChat, a Qt remote GUI for WeeChat.
#
# QWeeChat is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# QWeeChat is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with QWeeChat.  If not, see <http://www.gnu.org/licenses/>.
#

import qt_compat
import config
import utils
from inputlinespell import InputLineSpell

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')


class PreferencesDialog(QtGui.QDialog):
    """Preferences dialog."""

    custom_sections = {
        "look": "Look",
        "input": "Input Box",
        "nicks": "Nick List",
        "buffers": "Buffer List",
        "buffer_flags": False,
        "notifications": "Notifications",
        "color": "Colors",
        "relay": "Relay/Connection"
    }

    def __init__(self, name, parent, *args):
        QtGui.QDialog.__init__(*(self,) + args)
        self.setModal(True)
        self.setWindowTitle(name)
        self.parent = parent
        self.config = parent.config
        self.stacked_panes = QtGui.QStackedWidget()
        self.list_panes = PreferencesTreeWidget("Settings")

        splitter = QtGui.QSplitter()
        splitter.addWidget(self.list_panes)
        splitter.addWidget(self.stacked_panes)

        # Follow same order as defaults:
        section_panes = {}
        for section in config.CONFIG_DEFAULT_SECTIONS:
            item = QtGui.QTreeWidgetItem(section)
            name = section
            item.setText(0, section.title())
            if section in self.custom_sections:
                if not self.custom_sections[section]:
                    continue
                item.setText(0, self.custom_sections[section])
            section_panes[section] = PreferencesPaneWidget(section, name)
            self.list_panes.addTopLevelItem(item)
            self.stacked_panes.addWidget(section_panes[section])

        for setting, default in config.CONFIG_DEFAULT_OPTIONS:
            section_key = setting.split(".")
            section = section_key[0]
            key = ".".join(section_key[1:])
            section_panes[section].addItem(
                key, self.config.get(section, key), default)
        for key, value in self.config.items("color"):
            section_panes["color"].addItem(key, value, False)
        notification_field_count = len(section_panes["notifications"].fields)
        notification = PreferencesNotificationBlock(
            section_panes["notifications"])
        section_panes["notifications"].grid.addLayout(
            notification, notification_field_count, 0, 1, -1)

        self.list_panes.currentItemChanged.connect(self._pane_switch)
        self.list_panes.setCurrentItem(self.list_panes.topLevelItem(0))

        hbox = QtGui.QHBoxLayout()
        self.dialog_buttons = QtGui.QDialogButtonBox()
        self.dialog_buttons.setStandardButtons(
            QtGui.QDialogButtonBox.Save | QtGui.QDialogButtonBox.Cancel)
        self.dialog_buttons.rejected.connect(self.close)
        self.dialog_buttons.accepted.connect(self._save_and_close)

        hbox.addStretch(1)
        hbox.addWidget(self.dialog_buttons)
        hbox.addStretch(1)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(splitter)
        vbox.addLayout(hbox)

        self.setLayout(vbox)
        self.show()

    def _pane_switch(self, item):
        """Switch the visible preference pane."""
        index = self.list_panes.indexOfTopLevelItem(item)
        if index >= 0:
            self.stacked_panes.setCurrentIndex(index)

    def _save_and_close(self):
        for widget in (self.stacked_panes.widget(i)
                       for i in range(self.stacked_panes.count())):
            for key, field in widget.fields.items():
                if isinstance(field, QtGui.QComboBox):
                    text = field.itemText(field.currentIndex())
                    data = field.itemData(field.currentIndex())
                    text = data if data else text
                elif isinstance(field, QtGui.QCheckBox):
                    text = "on" if field.isChecked() else "off"
                else:
                    text = field.text()
                self.config.set(widget.section_name, key, str(text))
        config.write(self.config)
        self.parent.apply_preferences()
        self.close()


class PreferencesNotificationBlock(QtGui.QVBoxLayout):
    """Display notification settings with drill down to configure."""
    def __init__(self, pane, *args):
        QtGui.QVBoxLayout.__init__(*(self,) + args)
        self.section = "notifications"
        self.config = QtGui.QApplication.instance().config
        self.pane = pane
        self.stack = QtGui.QStackedWidget()

        self.table = QtGui.QTableWidget()
        fg_color = self.table.palette().text().color().name()
        self.action_labels = {
            "sound": "Play a sound",
            "message": "Show a message in a popup",
            "file": "Log to a file",
            "taskbar": "Mark taskbar entry",
            "tray": "Mark systray/indicator",
            "command": "Run a command"}
        self.action_icons = {
            "sound": utils.qicon_from_theme("media-playback-start"),
            "message": utils.qicon_from_theme("dialog-information"),
            "file": utils.qicon_from_theme("document-export"),
            "taskbar": utils.qicon_from_theme("weechat"),
            "tray": utils.qicon_tint("ic_hot", fg_color),
            "command": utils.qicon_from_theme("system-run")}
        self.icon_widget_qss = "padding:0;min-height:10px;min-width:16px;"
        self.table.resizeColumnsToContents()
        self.table.setColumnCount(2)
        self.table.resizeRowsToContents()
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.setHorizontalHeaderLabels(["State", "Type"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._table_row_changed)

        self.buftypes = {}
        for key, value in config.CONFIG_DEFAULT_NOTIFICATION_OPTIONS:
            buftype, optkey = key.split(".")
            if buftype not in self.buftypes:
                self.buftypes[buftype] = {}
            self.buftypes[buftype][optkey] = self.config.get(self.section, key)
        for buftype, optkey in self.buftypes.items():
            self._insert_type(buftype)
        self.update_icons()
        self.resize_table()
        self.addWidget(self.table)
        self.addWidget(self.stack)
        self.table.selectRow(0)

    def _insert_type(self, buftype):
        row = self.table.rowCount()
        self.table.insertRow(row)
        buftype_item = QtGui.QTableWidgetItem(buftype)
        buftype_item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.table.setItem(row, 0, QtGui.QTableWidgetItem())
        self.table.setItem(row, 1, buftype_item)
        subgrid = QtGui.QGridLayout()
        subgrid.setColumnStretch(2, 1)
        subgrid.setSpacing(10)

        for key, qicon in self.action_icons.items():
            value = self.buftypes[buftype][key]
            line = subgrid.rowCount()
            label = IconTextLabel(self.action_labels[key], qicon, 16)

            checkbox = QtGui.QCheckBox()
            span = 1
            edit = None
            if key in ("message", "taskbar", "tray"):
                checkbox.setChecked(value == "on")
                span = 2
            elif key == "sound":
                edit = PreferencesFileEdit(
                    checkbox=checkbox, caption='Select a sound file',
                    filter='Audio Files (*.wav *.mp3 *.ogg)')
            elif key == "file":
                edit = PreferencesFileEdit(checkbox=checkbox, mode="save")
            else:
                edit = PreferencesFileEdit(checkbox=checkbox)
            if edit:
                edit.insert(value)
                subgrid.addWidget(edit, line, 2)
            else:
                edit = checkbox
            subgrid.addWidget(label, line, 1, 1, span)
            subgrid.addWidget(checkbox, line, 0)
            self.pane.fields[buftype + "." + key] = edit
        subpane = QtGui.QWidget()
        subpane.setLayout(subgrid)
        subpane.setMaximumHeight(subgrid.totalMinimumSize().height())
        self.stack.addWidget(subpane)

    def resize_table(self):
        """Fit the table height to contents."""
        height = self.table.horizontalHeader().height()
        height = height * (self.table.rowCount() + 1)
        height += self.table.contentsMargins().top()
        height += self.table.contentsMargins().bottom()
        self.table.setMaximumHeight(height)
        self.table.setMinimumHeight(height)
        self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def update_icons(self):
        """Draw the correct icons in the left col."""
        for i in range(self.table.rowCount()):
            hbox = QtGui.QHBoxLayout()
            iconset = QtGui.QWidget()
            buftype = self.table.item(i, 1).text()
            for key, qicon in self.action_icons.items():
                field = self.pane.fields[buftype + "." + key]
                if isinstance(field, QtGui.QCheckBox):
                    val = "on" if field.isChecked() else "off"
                else:
                    val = field.text()
                iconbtn = QtGui.QPushButton()
                iconbtn.setContentsMargins(0, 0, 0, 0)
                iconbtn.setFlat(True)
                iconbtn.setFocusPolicy(QtCore.Qt.NoFocus)
                if val and val != "off":
                    iconbtn.setIcon(qicon)
                iconbtn.setStyleSheet(self.icon_widget_qss)
                iconbtn.setToolTip(key)
                iconbtn.clicked.connect(lambda i=i: self.table.selectRow(i))
                hbox.addWidget(iconbtn)
            iconset.setLayout(hbox)
            self.table.setCellWidget(i, 0, iconset)

    def _table_row_changed(self):
        row = self.table.selectionModel().selectedRows()[0].row()
        self.stack.setCurrentIndex(row)


class PreferencesTreeWidget(QtGui.QTreeWidget):
    """Widget with tree list of preferences."""
    def __init__(self, header_label, *args):
        QtGui.QTreeWidget.__init__(*(self,) + args)
        self.setHeaderLabel(header_label)
        self.setRootIsDecorated(False)
        self.setMaximumWidth(180)
        self.setTextElideMode(QtCore.Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(QtCore.Qt.NoFocus)


class PreferencesSliderEdit(QtGui.QSlider):
    """Percentage slider."""
    def __init__(self, *args):
        QtGui.QSlider.__init__(*(self,) + args)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setTickPosition(QtGui.QSlider.TicksBelow)
        self.setTickInterval(5)

    def insert(self, percent):
        self.setValue(int(percent[:-1]))

    def text(self):
        return str(self.value()) + "%"


class PreferencesColorEdit(QtGui.QPushButton):
    """Simple color square that changes based on the color selected."""
    def __init__(self, *args):
        QtGui.QPushButton.__init__(*(self,) + args)
        self.color = "#000000"
        self.clicked.connect(self._color_picker)
        # Some of the configured colors use a astrisk prefix.
        # Toggle this on right click.
        self.star = False
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._color_star)

    def insert(self, color):
        """Insert the desired color for the widget."""
        if color[:1] == "*":
            self.star = True
            color = color[1:]
        self.setText("*" if self.star else "")
        self.color = color
        self.setStyleSheet("background-color: " + color)

    def text(self):
        """Returns the hex value of the color."""
        return ("*" if self.star else "") + self.color

    def _color_picker(self):
        color = QtGui.QColorDialog.getColor(self.color)
        self.insert(color.name())

    def _color_star(self):
        self.star = not self.star
        self.insert(self.text())


class PreferencesFontEdit(QtGui.QWidget):
    """Font entry and selection."""
    def __init__(self, *args):
        QtGui.QWidget.__init__(*(self,) + args)
        layout = QtGui.QHBoxLayout()
        self.checkbox = QtGui.QCheckBox()
        self.edit = QtGui.QLineEdit()
        self.font = ""
        self.qfont = None
        self.button = QtGui.QPushButton("C&hoose")
        self.button.clicked.connect(self._font_picker)
        self.checkbox.toggled.connect(
            lambda: self._checkbox_toggled(self.checkbox))
        layout.addWidget(self.checkbox)
        layout.addWidget(self.edit)
        layout.addWidget(self.button)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def insert(self, font_str):
        """Insert the font described by the string."""
        self.font = font_str
        self.edit.insert(font_str)
        if font_str:
            self.qfont = utils.Font.str_to_qfont(font_str)
            self.edit.setFont(self.qfont)
            self.checkbox.setChecked(True)
            self._checkbox_toggled(self.checkbox)
        else:
            self.checkbox.setChecked(False)
            self.qfont = None
            self._checkbox_toggled(self.checkbox)

    def text(self):
        """Returns the human readable font string."""
        return self.font

    def _font_picker(self):
        font, ok = QtGui.QFontDialog.getFont(self.qfont)
        if ok:
            self.insert(utils.Font.qfont_to_str(font))

    def _checkbox_toggled(self, button):
        if button.isChecked() is False and not self.font == "":
            self.insert("")
        self.edit.setEnabled(button.isChecked())
        self.button.setEnabled(button.isChecked())


class PreferencesFileEdit(QtGui.QWidget):
    """File entry and selection."""
    def __init__(self, checkbox=None, caption="Select a file", filter=None,
                 mode="open", *args):
        QtGui.QWidget.__init__(*(self,) + args)
        layout = QtGui.QHBoxLayout()
        self.caption = caption
        self.filter = filter
        self.edit = QtGui.QLineEdit()
        self.file_str = ""
        self.mode = mode
        self.button = QtGui.QPushButton("B&rowse")
        self.button.clicked.connect(self._file_picker)
        if checkbox:
            self.checkbox = checkbox
        else:
            self.checkbox = QtGui.QCheckBox()
            layout.addWidget(self.checkbox)
        self.checkbox.toggled.connect(
            lambda: self._checkbox_toggled(self.checkbox))
        layout.addWidget(self.edit)
        layout.addWidget(self.button)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def insert(self, file_str):
        """Insert the file."""
        self.file_str = file_str
        self.edit.insert(file_str)
        if file_str:
            self.checkbox.setChecked(True)
            self._checkbox_toggled(self.checkbox)
        else:
            self.checkbox.setChecked(False)
            self._checkbox_toggled(self.checkbox)

    def text(self):
        """Returns the human readable font string."""
        return self.file_str

    def _file_picker(self):
        path = ""
        if self.mode == "save":
            fn = QtGui.QFileDialog.getSaveFileName
        else:
            fn = QtGui.QFileDialog.getOpenFileName
        filename, fil = fn(self, self.caption, path, self.filter, self.filter)
        if filename:
            self.insert(filename)

    def _checkbox_toggled(self, button):
        if button.isChecked() is False and not self.file_str == "":
            self.insert("")
        self.edit.setEnabled(button.isChecked())
        self.button.setEnabled(button.isChecked())


class PreferencesPaneWidget(QtGui.QWidget):
    """
    Widget with (from top to bottom):
    title, chat + nicklist (optional) + prompt/input.
    """

    disabled_fields = ["show_hostnames", "hide_nick_changes",
                       "hide_join_and_part"]

    def __init__(self, section, section_name):
        QtGui.QWidget.__init__(self)
        self.grid = QtGui.QGridLayout()
        self.grid.setAlignment(QtCore.Qt.AlignTop)
        self.section = section
        self.section_name = section_name
        self.fields = {}
        self.setLayout(self.grid)
        self.grid.setColumnStretch(2, 1)
        self.grid.setSpacing(10)
        self.int_validator = QtGui.QIntValidator(0, 2147483647, self)
        toolbar_icons = [
             ('ToolButtonFollowStyle', 'Default'),
             ('ToolButtonIconOnly', 'Icon Only'),
             ('ToolButtonTextOnly', 'Text Only'),
             ('ToolButtonTextBesideIcon', 'Text Alongside Icons'),
             ('ToolButtonTextUnderIcon', 'Text Under Icons')]
        tray_options = [
            ('always', 'Always'),
            ('unread', 'On Unread Messages'),
            ('never', 'Never'),
        ]
        list_positions = [
            ('left', 'Left'),
            ('right', 'Right'),
        ]
        sort_options = ['A-Z Ranked', 'A-Z', 'Z-A Ranked', 'Z-A']
        spellcheck_langs = [(x, x) for x in
                            InputLineSpell.list_languages()]
        spellcheck_langs.insert(0, ('', ''))
        focus_opts = ["requested", "always", "never"]
        self.comboboxes = {"style": QtGui.QStyleFactory.keys(),
                           "position": list_positions,
                           "toolbar_icons": toolbar_icons,
                           "focus_new_tabs": focus_opts,
                           "tray_icon": tray_options,
                           "sort": sort_options,
                           "spellcheck_dictionary": spellcheck_langs}

    def addItem(self, key, value, default):
        """Add a key-value pair."""
        line = len(self.fields)
        name = key.split(".")[-1:][0].capitalize().replace("_", " ")
        label = QtGui.QLabel(name)
        start = 0

        if self.section == "color":
            start = 2 * (line % 2)
            line = line // 2
            edit = PreferencesColorEdit()
            edit.setFixedWidth(edit.sizeHint().height())
            edit.insert(value)
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        elif key == "custom_stylesheet":
            edit = PreferencesFileEdit(caption='Select QStyleSheet File',
                                       filter='*.qss')
            edit.insert(value)
        elif name.lower()[-5:] == "sound":
            edit = PreferencesFileEdit(
                caption='Select a sound file',
                filter='Audio Files (*.wav *.mp3 *.ogg)')
            edit.insert(value)
        elif name.lower()[-4:] == "font":
            edit = PreferencesFontEdit()
            edit.setFixedWidth(200)
            edit.insert(value)
        elif key in self.comboboxes.keys():
            edit = QtGui.QComboBox()
            if len(self.comboboxes[key][0]) == 2:
                for keyvalue in self.comboboxes[key]:
                    edit.addItem(keyvalue[1], keyvalue[0])
                # if self.section == "nicks" and key == "position":
                #     edit.addItem("below", "Below Buffer List")
                #     edit.addItem("above", "Above Buffer List")
                edit.setCurrentIndex(edit.findData(value))
            else:
                edit.addItems(self.comboboxes[key])
                edit.setCurrentIndex(edit.findText(value))
            edit.setFixedWidth(200)
        elif default in ["on", "off"]:
            edit = QtGui.QCheckBox()
            edit.setChecked(value == "on")
        elif default[-1:] == "%":
            edit = PreferencesSliderEdit(QtCore.Qt.Horizontal)
            edit.setFixedWidth(200)
            edit.insert(value)
        else:
            edit = QtGui.QLineEdit()
            edit.setFixedWidth(200)
            edit.insert(value)
            if default.isdigit() or key == "port":
                edit.setValidator(self.int_validator)
        if key == 'password':
            edit.setEchoMode(QtGui.QLineEdit.Password)
        if key in self.disabled_fields:
            edit.setDisabled(True)
        self.grid.addWidget(label, line, start + 0)
        self.grid.addWidget(edit, line, start + 1)

        self.fields[key] = edit


class IconTextLabel(QtGui.QWidget):
    """An icon next to text."""
    def __init__(self, text=None, icon=None, extent=None):
        QtGui.QWidget.__init__(self)
        text_label = QtGui.QLabel(text)
        if not extent:
            extent = text_label.height()
        icon_label = QtGui.QLabel()
        pixmap = icon.pixmap(extent, QtGui.QIcon.Normal, QtGui.QIcon.On)
        icon_label.setPixmap(pixmap)
        label_layout = QtGui.QHBoxLayout()
        label_layout.addWidget(icon_label)
        label_layout.addWidget(text_label)
        label_layout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.setLayout(label_layout)
