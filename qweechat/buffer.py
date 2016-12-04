# -*- coding: utf-8 -*-
#
# buffer.py - management of WeeChat buffers/nicklist
#
# Copyright (C) 2011-2016 Sébastien Helleu <flashcode@flashtux.org>
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
from chat import ChatTextEdit
from input import InputLineEdit
import weechat.color as color
import config
import utils

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')
Qt = QtCore.Qt


class GenericListWidget(QtGui.QListWidget):
    """Generic QListWidget with dynamic size."""

    def __init__(self, *args):
        QtGui.QListWidget.__init__(*(self,) + args)
        self.setMaximumWidth(100)
        self.setTextElideMode(Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)

    def auto_resize(self):
        size = self.sizeHintForColumn(0)
        if size > 0:
            size += 4
        self.setMaximumWidth(size)

    def clear(self, *args):
        """Re-implement clear to set dynamic size after clear."""
        QtGui.QListWidget.clear(*(self,) + args)
        self.auto_resize()

    def addItem(self, *args):
        """Re-implement addItem to set dynamic size after add."""
        QtGui.QListWidget.addItem(*(self,) + args)
        self.auto_resize()

    def insertItem(self, *args):
        """Re-implement insertItem to set dynamic size after insert."""
        QtGui.QListWidget.insertItem(*(self,) + args)
        self.auto_resize()


class BufferSwitchWidgetItem(QtGui.QTreeWidgetItem):
    """Buffer list/tree item"""
    def __init__(self, buf, *args):
        QtGui.QTreeWidgetItem.__init__(*(self,) + args)
        config_color_options = config.config_color_options
        try:
            self.number = buf.data['number']
        except:
            self.number = int(buf)
            buf = None
        self.buf = buf
        self._color = "default"
        self._colormap = {  # Temporary work around.
            "default": config_color_options[11],  # chat_buffer
            "hotlist": config_color_options[44],    # chat_activity
            "hotlist_highlight": config_color_options[29],  # chat_highlight
        }
        if self.parent():
            self.setFlags(self.flags() & ~Qt.ItemIsDropEnabled)

    def __eq__(self, x):
        """Test equality for "in" statements."""
        if self.buf and x.buf:
            return self.buf.pointer == x.buf.pointer
        return x is self

    @property
    def pointer(self):
        """Returns a pointer for the item; a method rather than a property."""
        if self.buf:
            return self.buf.pointer
        elif self.childCount() > 0:
            return [c.buf.pointer for c in self.children]

    @property
    def full_name(self):
        """Returns the full name for an item."""
        if self.buf and "full_name" in self.buf.data:
            return self.buf.data["full_name"]
        return self.text(0)

    @property
    def children(self):
        return [self.child(i) for i in range(self.childCount())]

    @property
    def active(self):
        """The active item; merged root items return a child item."""
        if self.childCount() == 0:
            return self
        return self.treeWidget().active_item_for_merged_pointer(self.pointer)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color
        color_hex = self._colormap[color]
        self.setForeground(0, QtGui.QBrush(QtGui.QColor(color_hex)))


class BufferSwitchWidget(QtGui.QTreeWidget):
    """Widget with tree or list of buffers."""

    def __init__(self, *args):
        QtGui.QTreeWidget.__init__(*(self,) + args)
        self.setMaximumWidth(100)
        self.setTextElideMode(Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)
        self.setRootIsDecorated(False)
        self.header().close()
        self.buffers = []
        self.by_number = {}
        self._merged_buffers_active = {}
        self._current_pointer = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.customContextMenuRequested.connect(self._buffer_context)
        self.currentItemChanged.connect(self._currentItemChanged)

        self.ready = False

        # Context menu actions for the buffer switcher.
        self.actions_def = {
            'beep on message': [
                False, 'beep on message',
                False, lambda: self._toggle_buffer_flag('beep'), 'beep'],
            'blink tray icon': [
                False, 'beep on message',
                False, lambda: self._toggle_buffer_flag('tray'), 'tray'],
            'blink task bar': [
                False, 'beep on message',
                False, lambda: self._toggle_buffer_flag('taskbar'), 'taskbar'],
            'close': [
                'dialog-close.png', 'Close buffer',
                'Ctrl+W', lambda:self.buffer_input(self.currentItem().buf,
                                                   '/buffer close')],
            'unmerge': [
                False, 'Unmerge buffer',
                False, lambda:self.buffer_input(self.currentItem().buf,
                                                '/buffer unmerge')],
        }

    def _currentItemChanged(self, item, prior):
        if item and item.parent():
            ptr_str = "".join(item.parent().pointer)
            self._merged_buffers_active[ptr_str] = item.pointer
        if item:
            self._current_pointer = item.pointer

    def _not_yet_implemented(self):
        print("Not yet implemented.")

    def _toggle_buffer_flag(self, key):
        """Toggle the provided flag on the active item."""
        item = self.currentItem()
        if not item or not item.buf:
            return
        item.buf.set_flag(key, not item.buf.flag(key))

    def _buffer_context(self, event):
        """Show a context menu when the menu is right clicked."""
        item = self.currentItem()
        if not item:
            return
        menu = QtGui.QMenu()
        label_action = QtGui.QAction(self)
        if item.buf:
            label_action.setText(item.buf.data["full_name"])
        else:
            label_action.setText(str(item.childCount()) + " buffers")
        actions = utils.build_actions(self.actions_def, self)
        for action_name, action_def in self.actions_def.items():
            if len(action_def) > 4 and item.buf:
                checked = item.buf.flag(action_def[4])
                actions[action_name].setChecked(checked)
        menu.addAction(label_action)
        if item.buf:
            menu.addAction(utils.separator(self))
            menu.addActions([actions['beep on message'],
                             actions['blink tray icon'],
                             actions['blink task bar']])
        menu.addActions([utils.separator(self), actions['close']])
        if item.buf and len(self.by_number[item.buf.data["number"]]) > 1:
            menu.addActions([utils.separator(self), actions['unmerge']])
        menu.exec_(self.mapToGlobal(event))

    def renumber(self, ready=False):
        """Renumber buffers. Needed after a buffer move, close, merge etc."""
        if not self.ready and not ready or not self.buffers:
            return
        elif ready:
            self.ready = ready
        by_number = {}
        ptr = self.currentItem().pointer if self.currentItem() else None
        QtGui.QTreeWidget.clear(self)
        for buf in self.buffers:
            n = buf.data['number']
            by_number[n] = by_number[n] if n in by_number else []
            by_number[n].append(buf)
        self.setRootIsDecorated(False)
        tree_view_merged = True
        if not self.config.getboolean('buffers', 'tree_view_merged'):
            tree_view_merged = False
        for n, bufs in by_number.items():
            if not tree_view_merged or len(bufs) == 1:
                top_items = [BufferSwitchWidgetItem(b, self) for b in bufs]
                [item.setText(0, self._label(item)) for item in top_items]
                QtGui.QTreeWidget.addTopLevelItems(self, top_items)
            else:
                self.setRootIsDecorated(True)
                top_item = BufferSwitchWidgetItem(n, self)
                [BufferSwitchWidgetItem(b, top_item) for b in bufs]
                top_item.setText(0, self._label(top_item))
                QtGui.QTreeWidget.addTopLevelItem(self, top_item)
        self.by_number = by_number
        # Restore our active view before the renumber; which pointer object to
        # use depends on which client requested a merge/move, if any
        if ptr:
            self.setCurrentItem(self._find(ptr))
        elif self._current_pointer:
            self.setCurrentItem(self._find(self._current_pointer))
        self.auto_resize()

    def _icon(self, item):
        try:
            local = item.buf.data['local_variables']
            if local['type'] == "private":
                qicon = utils.qicon_from_theme('im-user')
            elif local['type'] == "channel":
                qicon = utils.qicon_from_theme('view-conversation-balloon')
            elif local['type'] == "server":
                qicon = utils.qicon_from_theme('network-server')
            item.setIcon(0, qicon)
            return qicon
        except:
            pass
        return None

    def _label(self, item):
        short_names = self.config.getboolean("buffers", "look.short_names")
        show_number = self.config.getboolean("buffers", "look.show_number")
        number_char = self.config.get("buffers", "look.number_char")
        crop_suffix = self.config.get("buffers", "look.name_crop_suffix")
        show_icons = self.config.getboolean("buffers", "show_icons")
        name_size_max = int(self.config.get("buffers", "look.name_size_max"))
        name = ""
        if show_icons and item.buf:
            self._icon(item)
        if item.buf:
            number = item.buf.data['number']
            name = item.buf.data['full_name']
            if item.buf.data['short_name'] and short_names:
                name = item.buf.data['short_name']
        for child in item.children:
            full_name = child.buf.data['full_name'].decode('utf-8')
            if 'short_name' in child.buf.data and child.buf.data['short_name']:
                short_name = child.buf.data['short_name'].decode('utf-8')
            else:
                short_name = full_name
            name = full_name[:-len(short_name)]
            number = child.buf.data['number']
            child.setText(0, short_name)
            self._icon(child)
        if name_size_max:
            name = name[:name_size_max] + crop_suffix
        if show_number:
            label = '%d%s %s' % (number, number_char, name.decode('utf-8'))
        else:
            label = '%s' % (name.decode('utf-8'))
        if item.childCount():
            label_count = '(%d)' % (item.childCount())
            if name_size_max:
                label = label[:-len(label_count)] + label_count
            else:
                label += " " + label_count + crop_suffix
        return label

    def auto_resize(self):
        size = self.sizeHintForColumn(0)
        if size > 0:
            size += 4
            self.setMaximumWidth(size)

    def clear(self, *args):
        """Re-implement clear to set dynamic size after clear."""
        QtGui.QTreeWidget.clear(*(self,) + args)
        self.auto_resize()
        self.buffers = []
        self.by_number = {}
        self._active_index_merged_buffers = {}
        self.setRootIsDecorated(False)

    def insert(self, index, buf):
        """Insert a BufferSwitchWidgetItem with the given buffer."""
        if buf not in self.buffers:
            self.buffers.insert(index, buf)
        self.renumber()
        self.auto_resize()

    def add(self, buf):
        """Add a BufferSwitchWidgetItem for a buffer to the end."""
        if buf not in self.buffers:
            self.insert(len(self.buffers), buf)

    def take(self, buf):
        """Remove and return the item matching."""
        if buf in self.buffers:
            self.buffers.remove(buf)
        self.renumber()
        return buf

    def _find(self, search):
        """Find a BufferWidgetItem for a given buffer pointer or name."""
        root = self.invisibleRootItem()
        for item in [root.child(i) for i in range(root.childCount())]:
            if item.pointer == search or item.full_name == search:
                return item
            for child in item.children:
                if child.pointer == search or child.full_name == search:
                    return child
        return None

    def set_current_buffer(self, bufptr):
        """Sets the current item to the provided buffer or pointer."""
        try:
            item = self._find(bufptr.pointer)
        except:
            item = self._find(bufptr)
        if not item:
            item = self.topLevelItem(0)
        self.setCurrentItem(item)

    def active_item_for_merged_pointer(self, pointer):
        """Find the active item in a merged pointer."""
        ptr_str = "".join(pointer)
        if ptr_str in self._merged_buffers_active:
            return self._find(self._merged_buffers_active[ptr_str])
        item = self._find(pointer)
        return item.children[0] if item and item.childCount() > 0 else None

    def selected_item(self):
        items = self.selectedItems()
        return items[0] if len(items) > 0 else self.topLevelItem(0)

    def switch_prev_buffer(self):
        item = self.itemAbove(self.selected_item())
        if item:
            self.setCurrentItem(item)
        else:
            idx = self.topLevelItemCount() - 1
            self.setCurrentItem(self.topLevelItem(idx))

    def switch_next_buffer(self):
        item = self.itemBelow(self.selected_item())
        if item:
            self.setCurrentItem(item)
        else:
            self.setCurrentItem(self.topLevelItem(0))

    def switch_active_buffer(self, step=1):
        """Switch current buffer if buffers are attached with same number."""
        item = self.selected_item()
        active = None
        parent = None
        if item.parent():
            parent = item.parent()
            active = item
        elif item.childCount() > 0:
            active = item.active
            parent = item
        if parent and active:
            ptr_str = "".join(parent.pointer)
            index = parent.indexOfChild(active)
            sibling = parent.child(index + step)
            if not sibling:
                sibling = parent.child(0) if step > 0 else parent.children[-1]
            self._merged_buffers_active[ptr_str] = sibling.pointer
            self.currentItemChanged.emit(parent, item)

    def switch_active_buffer_previous(self):
        """Switch current buffer if buffers are attached with same number."""
        self.switch_active_buffer(-1)

    def update_hot_buffers(self):
        root = self.invisibleRootItem()
        for item in [root.child(i) for i in range(root.childCount())]:
            if not isinstance(item, BufferSwitchWidgetItem):
                continue
            if item.buf and item.buf.hot:
                item.color = "hotlist"
                if item.buf.highlight:
                    item.color = "hotlist_highlight"
            else:
                item.color = "default"
            for itemc in item.children:
                if itemc.buf.hot:
                    itemc.color = "hotlist"
                    item.color = "hotlist"
                else:
                    itemc.color = "default"
        self.update()

    def dropEvent(self, drop_event):
        """Handle drag and drop buffer merging, unmerging, and moving."""
        item = self.selectedItems()[0]
        buf = item.buf if item.buf else item.children[0].buf
        dest_item = self.itemAt(drop_event.pos())
        drop_pos = self.dropIndicatorPosition()
        n = dest_item.number if dest_item else len(self.by_number)
        positions = QtGui.QAbstractItemView.DropIndicatorPosition
        if item.parent():
            n = n + 1 if n >= item.number else n
            self.buffer_input(buf, '/buffer unmerge')
        if n == item.number:
            # TODO: Add a way to custom sort merged buffers; there is no order.
            return
        if item.number < n and not drop_pos == positions.OnItem:
            n -= 1
        if drop_pos == positions.OnViewport:
            self.buffer_input(buf, '/buffer move ' + str(n + 1))
        elif drop_pos == positions.OnItem:
            self.buffer_input(buf, '/buffer merge ' + str(n))
        elif drop_pos == positions.AboveItem:
            self.buffer_input(buf, '/buffer move ' + str(n))
        elif drop_pos == positions.BelowItem:
            self.buffer_input(buf, '/buffer move ' + str(n + 1))

    def buffer_input(self, buf, command):
        main_window = self.parent().parent()
        main_window.buffer_input(buf.data['full_name'], command)

    @property
    def config(self):
        """Return config object."""
        return QtGui.QApplication.instance().config


class BufferWidget(QtGui.QWidget):
    """
    Widget with (from top to bottom):
    title, chat + nicklist (optional) + prompt/input.
    """

    def __init__(self, display_nicklist=False, time_format='%H:%M'):
        QtGui.QWidget.__init__(self)

        # title
        self.title = QtGui.QLineEdit()
        self.title.setFocusPolicy(Qt.NoFocus)

        # splitter with chat + nicklist
        self.chat_nicklist = QtGui.QSplitter()
        self.chat_nicklist.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                         QtGui.QSizePolicy.Expanding)
        self.chat = ChatTextEdit(debug=False)
        self.chat.time_format = time_format
        self.chat_nicklist.addWidget(self.chat)

        self.nicklist = GenericListWidget()
        if not display_nicklist:
            self.nicklist.setVisible(False)
        self.nicklist.confighash = None
        self.nicklist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.nicklist.customContextMenuRequested.connect(
            self._nicklist_context)
        self.chat_nicklist.addWidget(self.nicklist)
        # Context menu actions for the buffer switcher.
        self.nicklist_actions_def = {
            'query': [
                False, 'open dialog window',
                False, lambda:self._nicklist_action('/query %s')],
            'whois': [
                False, 'user info',
                False, lambda:self._nicklist_action('/whois %s')],
            'ignore': [
                False, 'ignore',
                False, lambda:self._nicklist_action('/ignore %s')],
        }

        # prompt + input
        self.hbox_edit = QtGui.QHBoxLayout()
        self.hbox_edit.setContentsMargins(0, 0, 0, 0)
        self.hbox_edit.setSpacing(0)
        self.input = InputLineEdit(self.chat)
        self.hbox_edit.addWidget(self.input)
        prompt_input = QtGui.QWidget()
        prompt_input.setLayout(self.hbox_edit)

        # vbox with title + chat/nicklist + prompt/input
        vbox = QtGui.QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.title)
        vbox.addWidget(self.chat_nicklist)
        vbox.addWidget(prompt_input)

        self.setLayout(vbox)

    def set_title(self, title):
        """Set buffer title."""
        self.title.clear()
        if title is not None:
            self.title.setText(title)

    def set_prompt(self, prompt):
        """Set prompt."""
        if self.hbox_edit.count() > 1:
            self.hbox_edit.takeAt(0)
        if prompt is not None:
            label = QtGui.QLabel(prompt)
            label.setContentsMargins(0, 0, 5, 0)
            self.hbox_edit.insertWidget(0, label)

    def _nicklist_context(self, event):
        """Show a context menu when the nicklist is right clicked."""
        item = self.nicklist.currentItem()
        if not item:
            return
        nick = item.text()
        menu = QtGui.QMenu()
        label_action = QtGui.QAction(nick, self.nicklist)
        actions = utils.build_actions(self.nicklist_actions_def, self.nicklist)
        menu.addActions([label_action, utils.separator(self.nicklist),
                         actions['query'],
                         actions['whois'],
                         actions['ignore']])
        menu.exec_(self.nicklist.mapToGlobal(event))

    def _nicklist_action(self, command):
        item = self.nicklist.currentItem()
        if not item:
            return
        nick = item.text()
        main_window = self.parent().parent().parent()
        buf = main_window.switch_buffers.currentItem().buf
        if not buf:
            return
        main_window.buffer_input(buf.data['full_name'], command % nick)


class Buffer(QtCore.QObject):
    """A WeeChat buffer."""

    bufferInput = qt_compat.Signal(str, str)

    def __init__(self, data={}):
        QtCore.QObject.__init__(self)
        self.data = data
        self.nicklist = {}
        display_nicklist = self.data.get('nicklist', 0)
        self.widget = BufferWidget(display_nicklist=display_nicklist)
        self.update_title()
        self.update_prompt()
        self.update_config()
        self.widget.input.textSent.connect(self.input_text_sent)
        self.widget.input.specialKey.connect(self.input_special_key)
        self._hot = 0
        self._highlight = False
        if 'short_name' not in data and 'full_name' in data:
            self.data['short_name'] = data['full_name'].rsplit(".", 1)[-1]

    @property
    def pointer(self):
        """Return pointer on buffer."""
        return self.data.get('__path', [''])[0]

    @property
    def config(self):
        """Return config object."""
        return QtGui.QApplication.instance().config

    def update_title(self):
        """Update title."""
        try:
            self.widget.set_title(
                color.remove(self.data['title'].decode('utf-8')))
        except:
            self.widget.set_title(None)

    def update_prompt(self):
        """Update prompt."""
        try:
            if self.config.getboolean("input", "nick_box"):
                self.widget.set_prompt(
                    self.data['local_variables']['nick'])
            else:
                self.widget.set_prompt(None)
        except:
            self.widget.set_prompt(None)

    def input_text_sent(self, text):
        """Called when text has to be sent to buffer."""
        if self.data:
            self.bufferInput.emit(self.data['full_name'], text)

    def input_special_key(self, key):
        """Handle special hotkeys that act on the buffer, e.g. copy."""
        if key[:1] == "c":
            cur = self.widget.chat.textCursor()
            if cur.hasSelection():
                self.widget.chat.copy()

    def update_config(self):
        """Apply configuration changes."""
        if (self.config):
            self.update_prompt()
            nicklist_visible = self.config.get("look", "nicklist") != "off"
            title_visible = self.config.get("look", "title") != "off"
            time_format = self.config.get("look", "buffer_time_format")
            indent = self.config.get("look", "indent")
            self.widget.nicklist.setVisible(nicklist_visible)
            self.widget.title.setVisible(title_visible)
            if self.config.getboolean("input", "spellcheck"):
                lang = self.config.get("input", "spellcheck_dictionary")
                self.widget.input.initDict(lang if lang else None)
            else:
                self.widget.input.killDict()

            # Nicklist position:
            if self.config.get('nicks', 'position') == 'above':
                pass
            if self.config.get('nicks', 'position') == 'below':
                pass
            if self.config.get('nicks', 'position') == 'left':
                self.widget.chat_nicklist.insertWidget(0, self.widget.nicklist)
            else:
                self.widget.chat_nicklist.insertWidget(1, self.widget.nicklist)
            keys = ['color_nicknames', 'sort', 'show_icons', 'show_hostnames']
            confighash = "".join([self.config.get('nicks', k) for k in keys])
            if self.widget.nicklist.confighash != confighash:
                self.nicklist_refresh()

            # Requires buffer redraw currently.
            if (self.widget.chat.time_format != time_format or
                    self.widget.chat.indent != indent):
                self.widget.chat.time_format = time_format
                self.widget.chat.indent = indent

    def nicklist_add_item(self, parent, group, prefix, name, visible):
        """Add a group/nick in nicklist."""
        if group:
            self.nicklist[name] = {
                'visible': visible,
                'nicks': []
            }
        else:
            self.nicklist[parent]['nicks'].append({
                'prefix': prefix,
                'name': name,
                'visible': visible,
            })

    def nicklist_remove_item(self, parent, group, name):
        """Remove a group/nick from nicklist."""
        if group:
            if name in self.nicklist:
                del self.nicklist[name]
        else:
            if parent in self.nicklist:
                self.nicklist[parent]['nicks'] = [
                    nick for nick in self.nicklist[parent]['nicks']
                    if nick['name'] != name
                ]

    def nicklist_update_item(self, parent, group, prefix, name, visible):
        """Update a group/nick in nicklist."""
        if group:
            if name in self.nicklist:
                self.nicklist[name]['visible'] = visible
        else:
            if parent in self.nicklist:
                for nick in self.nicklist[parent]['nicks']:
                    if nick['name'] == name:
                        nick['prefix'] = prefix
                        nick['visible'] = visible
                        break

    def nicklist_refresh(self):
        """Refresh nicklist."""
        self.widget.nicklist.clear()
        sort = self.config.get("nicks", "sort")
        icons = self.config.get("nicks", "show_icons")
        colors = self.config.get("nicks", "color_nicknames")
        hostnames = self.config.get("nicks", "show_hostnames")
        self.widget.nicklist.confighash = colors + sort + icons + hostnames

        reverse = True if sort[0:3] == "Z-A" else False
        for group in sorted(self.nicklist, reverse=reverse):
            for nick in sorted(self.nicklist[group]['nicks'],
                               key=lambda n: n['name'], reverse=reverse):
                prefix_color = {
                    '': '',
                    ' ': '',
                    '+': 'yellow',
                }
                color = prefix_color.get(nick['prefix'], 'green')
                if color:
                    icon = utils.qicon_from_theme('bullet_%s_8x8' % color)
                else:
                    pixmap = QtGui.QPixmap(8, 8)
                    pixmap.fill()
                    icon = QtGui.QIcon(pixmap)
                label = nick['name']
                if icons != "off":
                    item = QtGui.QListWidgetItem(icon, label)
                else:
                    item = QtGui.QListWidgetItem(label)
                if colors and label in self.widget.chat.prefix_colors:
                    item.setForeground(
                        QtGui.QBrush(self.widget.chat.prefix_colors[label]))
                self.widget.nicklist.addItem(item)
        if not sort[4:]:
            self.widget.nicklist.sortItems(
                Qt.DescendingOrder if reverse else Qt.AscendingOrder)

    def flag(self, key=None):
        if not key:
            return (self.flag("beep") or self.flag("tray") or
                    self.flag("taskbar"))
        option = self.data["full_name"] + "." + key
        if ((self.config.has_option("buffer_flags", option) and
             self.config.get("buffer_flags", option) == "on")):
            return True
        return False

    def set_flag(self, key, value):
        option = self.data["full_name"] + "." + key
        if value:
            self.config.set("buffer_flags", option, "on")
        else:
            self.config.remove_option("buffer_flags", option)

    @property
    def hot(self):
        return self._hot

    @hot.setter
    def hot(self, value):
        self._hot = value

    @property
    def highlight(self):
        return self._highlight

    @highlight.setter
    def highlight(self, value):
        self._highlight = value
