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

from pkg_resources import resource_filename
import qt_compat
from chat import ChatTextEdit
from input import InputLineEdit
import weechat.color as color
import config
import utils

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')


class GenericListWidget(QtGui.QListWidget):
    """Generic QListWidget with dynamic size."""

    def __init__(self, *args):
        QtGui.QListWidget.__init__(*(self,) + args)
        self.setMaximumWidth(100)
        self.setTextElideMode(QtCore.Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

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
            self.setFlags(self.flags() & ~QtCore.Qt.ItemIsDropEnabled)

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
    def children(self):
        return [self.child(i) for i in range(self.childCount())]

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
        self.setTextElideMode(QtCore.Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setRootIsDecorated(False)
        self.header().close()
        self.buffers = []
        self.by_number = {}
        self.merged_buffers = True
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.customContextMenuRequested.connect(self._menu_context)
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

    def _not_yet_implemented(self):
        print("Not yet implemented.")

    def _toggle_buffer_flag(self, key):
        """Toggle the provided flag on the active item."""
        item = self.currentItem()
        if not item or not item.buf:
            return
        item.buf.set_flag(key, not item.buf.flag(key))

    def _menu_context(self, event):
        """Show a context menu when an item is right clicked."""
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
        if not self.ready and not ready:
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
        if not self.merged_buffers:
            self.by_number = by_number
            return
        for n, bufs in by_number.items():
            if len(bufs) == 1:
                top_item = BufferSwitchWidgetItem(bufs[0], self)
            else:
                self.setRootIsDecorated(True)
                top_item = BufferSwitchWidgetItem(n, self)
                [BufferSwitchWidgetItem(b, top_item) for b in bufs]
            top_item.setText(0, self._label(top_item))
            QtGui.QTreeWidget.insertTopLevelItem(self, n - 1, top_item)
        if ptr:
            self.setCurrentItem(self._find_by_pointer(ptr))
        self.by_number = by_number
        self.auto_resize()

    def _label(self, item):
        if item.buf:
            name = item.buf.data['full_name']
            if item.buf.data['short_name']: #item.buf.config.get("")
                name = item.buf.data['short_name']
            label = '%d. %s' % (item.buf.data['number'], name.decode('utf-8'))
            return label
        for child in item.children:
            full_name = child.buf.data['full_name'].decode('utf-8')
            if 'short_name' in child.buf.data and child.buf.data['short_name']:
                short_name = child.buf.data['short_name'].decode('utf-8')
            else:
                short_name = full_name
            number = child.buf.data['number']
            child.setText(0, short_name)
        label = '%d+ %s (%s)' % (number, full_name[:-len(short_name)],
                                 item.childCount())
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

    def _find_by_pointer(self, pointer):
        """Find a BufferWidgetItem for a given buffer pointer."""
        if isinstance(pointer, str):
            root = self.invisibleRootItem()
            for item in [root.child(i) for i in range(root.childCount())]:
                if item.pointer == pointer:
                    return item
                for child in item.children:
                    if child.pointer == pointer:
                        return child
        else:
            item = self._find_by_pointer(pointer[0])
            return item.parent() if item and item.parent() else item
        return None

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

    def update_hot_buffers(self):
        root = self.invisibleRootItem()
        for item in [root.child(i) for i in range(root.childCount())]:
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
            # TODO: Add a way to custom sort merged buffers, this is temporary:
            return
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


class BufferWidget(QtGui.QWidget):
    """
    Widget with (from top to bottom):
    title, chat + nicklist (optional) + prompt/input.
    """

    def __init__(self, display_nicklist=False):
        QtGui.QWidget.__init__(self)

        # title
        self.title = QtGui.QLineEdit()
        self.title.setFocusPolicy(QtCore.Qt.NoFocus)

        # splitter with chat + nicklist
        self.chat_nicklist = QtGui.QSplitter()
        self.chat_nicklist.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                         QtGui.QSizePolicy.Expanding)
        self.chat = ChatTextEdit(debug=False)
        self.chat_nicklist.addWidget(self.chat)
        self.nicklist = GenericListWidget()
        if not display_nicklist:
            self.nicklist.setVisible(False)
        self.chat_nicklist.addWidget(self.nicklist)

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


class Buffer(QtCore.QObject):
    """A WeeChat buffer."""

    bufferInput = qt_compat.Signal(str, str)

    def __init__(self, data={}, config=False):
        QtCore.QObject.__init__(self)
        self.data = data
        self.config = config
        self.nicklist = {}
        self.widget = BufferWidget(display_nicklist=self.data.get('nicklist',
                                                                  0))
        self.update_title()
        self.update_prompt()
        self.widget.input.textSent.connect(self.input_text_sent)
        self._hot = 0
        self._highlight = False

    @property
    def pointer(self):
        """Return pointer on buffer."""
        return self.data.get('__path', [''])[0]

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
            self.widget.set_prompt(self.data['local_variables']['nick'])
        except:
            self.widget.set_prompt(None)

    def input_text_sent(self, text):
        """Called when text has to be sent to buffer."""
        if self.data:
            self.bufferInput.emit(self.data['full_name'], text)

    def update_config(self):
        """Match visibility to configuration, faster than a nicklist refresh"""
        if (self.config):
            nicklist_visible = self.config.get("look", "nicklist") != "off"
            title_visible = self.config.get("look", "title") != "off"
            self.widget.nicklist.setVisible(nicklist_visible)
            self.widget.title.setVisible(title_visible)

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
        for group in sorted(self.nicklist):
            for nick in sorted(self.nicklist[group]['nicks'],
                               key=lambda n: n['name']):
                prefix_color = {
                    '': '',
                    ' ': '',
                    '+': 'yellow',
                }
                color = prefix_color.get(nick['prefix'], 'green')
                if color:
                    icon = QtGui.QIcon(
                        resource_filename(__name__,
                                          'data/icons/bullet_%s_8x8.png' %
                                          color))
                else:
                    pixmap = QtGui.QPixmap(8, 8)
                    pixmap.fill()
                    icon = QtGui.QIcon(pixmap)
                item = QtGui.QListWidgetItem(icon, nick['name'])
                self.widget.nicklist.addItem(item)
                if self.config and self.config.get("look",
                                                   "nicklist") == "off":
                    self.widget.nicklist.setVisible(False)
                else:
                    self.widget.nicklist.setVisible(True)

    def flag(self, key):
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
