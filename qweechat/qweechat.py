# -*- coding: utf-8 -*-
#
# qweechat.py - WeeChat remote GUI using Qt toolkit
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

"""
QWeeChat is a WeeChat remote GUI using Qt toolkit.

It requires requires WeeChat 0.3.7 or newer, running on local or remote host.
"""

#
# History:
#
# 2011-05-27, Sébastien Helleu <flashcode@flashtux.org>:
#     start dev
#

import signal
import sys
import traceback
import qt_compat
import config
import weechat.protocol as protocol
from network import Network
from connection import ConnectionDialog
from buffer import BufferSwitchWidget, Buffer
from debug import DebugDialog
from about import AboutDialog
from preferences import PreferencesDialog
from version import qweechat_version
import utils

signal.signal(signal.SIGINT, signal.SIG_DFL)

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')

NAME = 'QWeeChat'
AUTHOR = 'Sébastien Helleu'
AUTHOR_MAIL = 'flashcode@flashtux.org'
WEECHAT_SITE = 'https://weechat.org/'

# number of lines in buffer for debug window
DEBUG_NUM_LINES = 50


class MainWindow(QtGui.QMainWindow):
    """Main window."""

    def __init__(self, *args):
        QtGui.QMainWindow.__init__(*(self,) + args)
        app = QtGui.QApplication.instance()
        self.config = config.read()
        app.config = self.config

        self.resize(1000, 600)
        self.setWindowTitle(NAME)

        self.debug_dialog = None
        self.debug_lines = []

        self.about_dialog = None
        self.connection_dialog = None
        self.preferences_dialog = None

        # network
        self.network = Network()
        self.network.statusChanged.connect(self._network_status_changed)
        self.network.messageFromWeechat.connect(self._network_weechat_msg)
        self._last_msgid = None

        # list of buffers
        self.switch_buffers = BufferSwitchWidget()
        self.switch_buffers.currentItemChanged.connect(self._buffer_switch)
        self._hotlist = []

        # default buffer
        self.buffers = [Buffer()]
        self.stacked_buffers = QtGui.QStackedWidget()
        self.stacked_buffers.addWidget(self.buffers[0].widget)

        # splitter with buffers + chat/input
        self.splitter = QtGui.QSplitter()
        self.splitter.addWidget(self.switch_buffers)
        self.splitter.addWidget(self.stacked_buffers)

        self.setCentralWidget(self.splitter)

        # actions for menu and toolbar
        actions_def = {
            'connect': [
                'network-connect', 'Connect to WeeChat',
                'Ctrl+O', self.open_connection_dialog],
            'disconnect': [
                'network-disconnect', 'Disconnect from WeeChat',
                'Ctrl+D', self.network.disconnect_weechat],
            'debug': [
                'edit-find', 'Debug console window',
                'Ctrl+Shift+B', self.open_debug_dialog],
            'view source': [
                None, 'View buffer chat source',
                'Ctrl+Shift+U', self.open_chat_source],
            'preferences': [
                'preferences-other', 'Preferences',
                'Ctrl+P', self.open_preferences_dialog],
            'about': [
                'help-about', 'About',
                'Ctrl+H', self.open_about_dialog],
            'save connection': [
                'document-save', 'Save connection configuration',
                'Ctrl+S', self.save_connection],
            'quit': [
                'application-exit', 'Quit application',
                'Ctrl+Q', self.close],
        }
        # toggleable actions
        self.toggles_def = {
            'show menubar': [
                False, 'Show Menubar', 'Ctrl+M',
                lambda: self.config_toggle('look', 'menubar'),
                'look.menubar'],
            'show toolbar': [
                False, 'Show Toolbar',
                False, lambda: self.config_toggle('look', 'toolbar'),
                'look.toolbar'],
            'show status bar': [
                False, 'Show Status Bar',
                False, lambda: self.config_toggle('look', 'statusbar'),
                'look.statusbar'],
            'show title': [
                False, 'Show Topic',
                False, lambda: self.config_toggle('look', 'title'),
                'look.title'],
            'show nick list': [
                False, 'Show Nick List',
                'Ctrl+F7', lambda: self.config_toggle('look', 'nicklist'),
                'look.nicklist'],
            'fullscreen': [
                False, 'Fullscreen',
                'F11', self.toggle_fullscreen],
        }
        self.actions = utils.build_actions(actions_def, self)
        self.actions.update(utils.build_actions(self.toggles_def, self))

        # menu
        self.menu = self.menuBar()
        menu_file = self.menu.addMenu('&File')
        menu_file.addActions([self.actions['connect'],
                              self.actions['disconnect'],
                              self.actions['preferences'],
                              self.actions['save connection'],
                              self.actions['quit']])
        menu_view = self.menu.addMenu('&View')
        menu_view.addActions([self.actions['show menubar'],
                              self.actions['show toolbar'],
                              self.actions['show status bar'],
                              utils.separator(self),
                              self.actions['show title'],
                              self.actions['show nick list'],
                              utils.separator(self),
                              self.actions['fullscreen']])
        menu_window = self.menu.addMenu('&Window')
        menu_window.addAction(self.actions['debug'])
        menu_window.addAction(self.actions['view source'])
        menu_help = self.menu.addMenu('&Help')
        menu_help.addAction(self.actions['about'])
        self.network_status = QtGui.QPushButton()

        self.network_status.setContentsMargins(0, 0, 10, 0)
        self.network_status.setFlat(True)
        self.network_status.setFocusPolicy(QtCore.Qt.NoFocus)

        self.network_status.setStyleSheet("""text-align:right;padding:0;
            background-color: transparent;min-width:216px;min-height:20px""")

        if hasattr(self.menu, 'setCornerWidget'):
            self.menu.setCornerWidget(self.network_status,
                                      QtCore.Qt.TopRightCorner)

        # toolbar
        toolbar = self.addToolBar('toolBar')
        toolbar.setMovable(False)
        toolbar.addActions([self.actions['connect'],
                            self.actions['disconnect'],
                            self.actions['debug'],
                            self.actions['preferences'],
                            self.actions['about'],
                            self.actions['quit']])
        self.toolbar = toolbar

        # Override context menu for both -- default is a simple menubar toggle.
        self.menu.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.toolbar.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.menu.customContextMenuRequested.connect(self._menu_context)
        self.toolbar.customContextMenuRequested.connect(self._toolbar_context)

        self.buffers[0].widget.input.setFocus()

        # open debug dialog
        if self.config.getboolean('look', 'debug'):
            self.open_debug_dialog()

        self.apply_preferences()
        self.network_status_set(self.network.status_disconnected)

        # auto-connect to relay
        if self.config.getboolean('relay', 'autoconnect'):
            self.network.connect_weechat(self.config.get('relay', 'server'),
                                         self.config.get('relay', 'port'),
                                         self.config.getboolean('relay',
                                                                'ssl'),
                                         self.config.get('relay', 'password'),
                                         self.config.get('relay', 'lines'))

        self.show()

    def apply_preferences(self):
        """Apply non-server options from preferences."""
        app = QtCore.QCoreApplication.instance()
        config.build_color_options(self.config)
        if self.config.getboolean('look', 'toolbar'):
            self.toolbar.show()
        else:
            self.toolbar.hide()
        # Change the height to avoid losing all hotkeys:
        if self.config.getboolean('look', 'menubar'):
            self.menu.setMaximumHeight(QtGui.QWIDGETSIZE_MAX)
        else:
            self.menu.setFixedHeight(1)
        # Apply the selected qt style here so it will update without a restart
        if self.config.get('look', 'style'):
            app.setStyle(QtGui.QStyleFactory.create(
                self.config.get('look', 'style')))
        # Statusbar:
        if self.config.getboolean('look', 'statusbar'):
            self.statusBar().show()
        else:
            self.statusBar().hide()
        # Move the buffer list / main buffer view:
        if self.config.get('buffers', 'position') == 'right':
            self.splitter.insertWidget(1, self.switch_buffers)
        else:
            self.splitter.insertWidget(1, self.stacked_buffers)
        # Update visibility of all nicklists/topics:
        for buffer in self.buffers:
            buffer.update_config()
        # Update toggle state for menubar:
        for name, action in list(self.toggles_def.items()):
            if len(action) == 5:
                ac = action[4].split(".")
                toggle = self.config.get(ac[0], ac[1])
                self.actions[name].setChecked(toggle == "on")
        self.toolbar.setToolButtonStyle(getattr(QtCore.Qt, self.config.get(
            "look", "toolbar_icons")))
        self.switch_buffers.renumber()
        if self.config.get("buffers", "look.mouse_move_buffer"):
            buffer_drag_drop_mode = QtGui.QAbstractItemView.InternalMove
        else:
            buffer_drag_drop_mode = QtGui.QAbstractItemView.NoDragDrop
        self.switch_buffers.setDragDropMode(buffer_drag_drop_mode)
        # Apply fonts -- TODO: change to creating a stylesheet
        custom_font = self.config.get("look", "custom_font")
        switch_font = self.config.get("buffers", "custom_font")
        chat_font = "monospace" if not custom_font else custom_font
        if not switch_font:
            switch_font = "" if not custom_font else custom_font
        self.stacked_buffers.setFont(utils.Font.str_to_qfont(chat_font))
        self.switch_buffers.setFont(utils.Font.str_to_qfont(switch_font))
        # Choose correct menubar/taskbar icon colors::
        # menu_palette = self.menu.palette()
        # toolbar_fg: menu_palette.text().color().name())
        # menubar_fg: menu_palette.windowText().color().name()
        # menubar_bg: menu_palette.window().color().name()

    def _menu_context(self, event):
        """Show a slightly nicer context menu for the menu/toolbar."""
        menu = QtGui.QMenu()
        menu.addActions([self.actions['show menubar'],
                         self.actions['show toolbar'],
                         self.actions['show status bar']])
        menu.exec_(self.mapToGlobal(event))

    def _toolbar_context(self, event):
        """Show a context menu when the toolbar is right clicked."""
        menu = QtGui.QMenu('&Text Position', self.toolbar)
        menu_group = QtGui.QActionGroup(menu, exclusive=True)

        actions = []
        opts = [('ToolButtonFollowStyle', 'Default'),
                ('ToolButtonIconOnly', '&Icon Only'),
                ('ToolButtonTextOnly', '&Text Only'),
                ('ToolButtonTextBesideIcon', 'Text &Alongside Icons'),
                ('ToolButtonTextUnderIcon', 'Text &Under Icons')]
        value = self.config.get("look", "toolbar_icons")
        for key, label in opts:
            action = QtGui.QAction(label, menu_group, checkable=True)
            actions.append(menu_group.addAction(action))
            action.setChecked(True if value == key else False)
            action.triggered.connect(
                lambda key=key: self.config_set('look', 'toolbar_icons', key))
        menu.addActions(actions)
        menu.exec_(self.mapToGlobal(event))

    def _buffer_switch(self, buf_item):
        """Switch to a buffer."""
        if buf_item:
            buf = buf_item.active.buf
            self.stacked_buffers.setCurrentWidget(buf.widget)
            if buf.hot or buf.highlight:
                self.buffer_hotlist_clear(buf.data["full_name"])
            buf.widget.input.setFocus()

    def buffer_hotlist_clear(self, full_name):
        """Set a buffer as read for the hotlist."""
        buf = self.buffers[self._buffer_index("full_name", full_name)[0]]
        if buf.pointer in self._hotlist:
            buf.highlight = False
            buf.hot = 0
            self._hotlist.remove(buf.pointer)
            self.switch_buffers.update_hot_buffers()
        if self.network.server_version >= 1:
            self.buffer_input(full_name, '/buffer set hotlist -1')
            self.buffer_input(full_name, '/input set_unread_current_buffer')
        else:
            self.buffer_input('core.weechat', '/buffer ' + full_name)

    def buffer_input(self, full_name, text):
        """Send buffer input to WeeChat."""
        if self.network.is_connected():
            message = 'input %s %s\n' % (full_name, text)
            self.network.send_to_weechat(message)
            self.debug_display(0, '<==', message, forcecolor='#AA0000')

    def open_preferences_dialog(self):
        """Open a dialog with preferences."""
        self.preferences_dialog = PreferencesDialog('Preferences', self)

    def save_connection(self):
        """Save connection configuration."""
        if self.network:
            options = self.network.get_options()
            for option in options.keys():
                self.config.set('relay', option, options[option])

    def debug_display(self, *args, **kwargs):
        """Display a debug message."""
        self.debug_lines.append((args, kwargs))
        self.debug_lines = self.debug_lines[-DEBUG_NUM_LINES:]
        if self.debug_dialog:
            self.debug_dialog.chat.display(*args, **kwargs)

    def open_debug_dialog(self):
        """Open a dialog with debug messages."""
        if not self.debug_dialog:
            self.debug_dialog = DebugDialog(self)
            self.debug_dialog.input.textSent.connect(
                self.debug_input_text_sent)
            self.debug_dialog.finished.connect(self._debug_dialog_closed)
            self.debug_dialog.display_lines(self.debug_lines)
            self.debug_dialog.chat.scroll_bottom()

    def debug_input_text_sent(self, text):
        """Send debug buffer input to WeeChat."""
        if self.network.is_connected():
            text = str(text)
            pos = text.find(')')
            if text.startswith('(') and pos >= 0:
                text = '(debug_%s)%s' % (text[1:pos], text[pos+1:])
            else:
                text = '(debug) %s' % text
            self.debug_display(0, '<==', text, forcecolor='#AA0000')
            self.network.send_to_weechat(text + '\n')

    def _debug_dialog_closed(self, result):
        """Called when debug dialog is closed."""
        self.debug_dialog = None

    def open_chat_source(self):
        """Open a dialog with chat buffer source."""
        item = self.switch_buffers.currentItem()
        if item and item.active.buf:
            buf = item.active.buf
            source_dialog = DebugDialog(self)
            source_dialog.chat.setPlainText(buf.widget.chat.toHtml())
            source_dialog.chat.setFocusPolicy(QtCore.Qt.WheelFocus)
            source_dialog.setWindowTitle(buf.data['full_name'])

    def open_about_dialog(self):
        """Open a dialog with info about QWeeChat."""
        messages = ['<b>%s</b> %s' % (NAME, qweechat_version()),
                    '&copy; 2011-2016 %s &lt;<a href="mailto:%s">%s</a>&gt;'
                    % (AUTHOR, AUTHOR_MAIL, AUTHOR_MAIL),
                    '',
                    'Running with %s' % ('PySide' if qt_compat.uses_pyside
                                         else 'PyQt4'),
                    '',
                    'WeeChat site: <a href="%s">%s</a>'
                    % (WEECHAT_SITE, WEECHAT_SITE),
                    '']
        self.about_dialog = AboutDialog(NAME, messages, self)

    def open_connection_dialog(self):
        """Open a dialog with connection settings."""
        values = {}
        for option in ('server', 'port', 'ssl', 'password', 'lines'):
            values[option] = self.config.get('relay', option)
        self.connection_dialog = ConnectionDialog(values, self)
        self.connection_dialog.dialog_buttons.accepted.connect(
            self.connect_weechat)

    def config_toggle(self, section, option):
        """Toggles any boolean setting."""
        val = self.config.getboolean(section, option)
        self.config_set(section, option, "off" if val else "on")

    def config_set(self, section, option, value):
        self.config.set(section, option, value)
        self.apply_preferences()
        config.write(self.config)

    def toggle_fullscreen(self):
        """Toggle fullscreen."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def connect_weechat(self):
        """Connect to WeeChat."""
        self.network.connect_weechat(
            self.connection_dialog.fields['server'].text(),
            self.connection_dialog.fields['port'].text(),
            self.connection_dialog.fields['ssl'].isChecked(),
            self.connection_dialog.fields['password'].text(),
            int(self.connection_dialog.fields['lines'].text()))
        self.connection_dialog.close()

    def _network_status_changed(self, status, extra):
        """Called when the network status has changed."""
        if self.config.getboolean('look', 'statusbar'):
            self.statusBar().showMessage(status)
        self.debug_display(0, '', status, forcecolor='#0000AA')
        self.network_status_set(status)

    def network_status_set(self, status):
        """Set the network status."""
        pal = self.network_status.palette()
        if status == self.network.status_connected:
            fg_color = QtGui.QColor('green')
        else:
            fg_color = self.menu.palette().windowText().color()
        pal.setColor(QtGui.QPalette.ButtonText, fg_color)
        ssl = ' (SSL)' if status != self.network.status_disconnected \
              and self.network.is_ssl() else ''
        self.network_status.setPalette(pal)
        icon = self.network.status_icon(status)
        if icon:
            qicon = utils.qicon_from_theme(icon)
            self.network_status.setIcon(qicon)
        self.network_status.setText(status.capitalize() + ssl)
        if status == self.network.status_disconnected:
            self.actions['connect'].setEnabled(True)
            self.actions['disconnect'].setEnabled(False)
        else:
            self.actions['connect'].setEnabled(False)
            self.actions['disconnect'].setEnabled(True)

    def _network_weechat_msg(self, message):
        """Called when a message is received from WeeChat."""
        self.debug_display(0, '==>',
                           'message (%d bytes):\n%s'
                           % (len(message),
                              protocol.hex_and_ascii(message, 20)),
                           forcecolor='#008800')
        try:
            proto = protocol.Protocol()
            message = proto.decode(str(message))
            if message.uncompressed:
                self.debug_display(
                    0, '==>',
                    'message uncompressed (%d bytes):\n%s'
                    % (message.size_uncompressed,
                       protocol.hex_and_ascii(message.uncompressed, 20)),
                    forcecolor='#008800')
            self.debug_display(0, '', 'Message: %s' % message)
            self.parse_message(message)
        except:
            print('Error while decoding message from WeeChat:\n%s'
                  % traceback.format_exc())
            self.network.disconnect_weechat()

    def _parse_listbuffers(self, message):
        """Parse a WeeChat with list of buffers."""
        for obj in message.objects:
            if obj.objtype != 'hda' or obj.value['path'][-1] != 'buffer':
                continue
            self.switch_buffers.clear()
            while self.stacked_buffers.count() > 0:
                buf = self.stacked_buffers.widget(0)
                self.stacked_buffers.removeWidget(buf)
            self.buffers = []
            for item in obj.value['items']:
                buf = self.create_buffer(item)
                self.insert_buffer(len(self.buffers), buf)
            self.switch_buffers.renumber(True)
            self.switch_buffers.setCurrentItem(
                self.switch_buffers.topLevelItem(0))

    def _parse_line(self, message):
        """Parse a WeeChat message with a buffer line."""
        for obj in message.objects:
            lines = []
            if obj.objtype != 'hda' or obj.value['path'][-1] != 'line_data':
                continue
            for item in obj.value['items']:
                if message.msgid == 'listlines':
                    ptrbuf = item['__path'][0]
                else:
                    ptrbuf = item['buffer']
                index = self._buffer_index("pointer", ptrbuf)
                if index:
                    if 'tags_array' in item and item['tags_array']:
                        if 'notify_private' in item['tags_array']:
                            pass
                        elif 'notify_message' in item['tags_array']:
                            pass
                        if 'no_notify' not in item['tags_array']:
                            if "irc_privmsg" in item['tags_array']:
                                self.buffers[index[0]].hot += 1
                                self._hotlist.append(ptrbuf)
                            # TODO: Colors for irc_join and irc_quit
                    if 'highlight' in item and item['highlight'] > 0:
                        self.buffers[index[0]].highlight = True
                        color = self.config.get('color', 'chat_highlight')
                    else:
                        self.buffers[index[0]].highlight = False
                        color = None
                    lines.append(
                        (index[0],
                         (item['date'], item['prefix'],
                          item['message'], color))
                    )
            if message.msgid == 'listlines':
                lines.reverse()
            for line in lines:
                self.buffers[line[0]].widget.chat.display(*line[1])
            self.switch_buffers.update_hot_buffers()

    def _parse_hotlist(self, message):
        """Parse a WeeChat message with a hotlist update."""
        for buf in self.buffers:
            buf.hot = 0
        hotlist = []
        for obj in message.objects:
            if obj.objtype != 'hda' or obj.value['path'][-1] != 'hotlist':
                continue
            for item in obj.value['items']:
                index = self._buffer_index("pointer", item['buffer'])
                if not index:
                    continue
                self.buffers[index[0]].hot += 1
                hotlist.append(item['buffer'])
        if hotlist != self._hotlist:
            self.switch_buffers.update_hot_buffers()
            self._hotlist = hotlist

    def _parse_nicklist(self, message):
        """Parse a WeeChat message with a buffer nicklist."""
        buffer_refresh = {}
        for obj in message.objects:
            if obj.objtype != 'hda' or \
               obj.value['path'][-1] != 'nicklist_item':
                continue
            group = '__root'
            for item in obj.value['items']:
                index = self._buffer_index("pointer", item['__path'][0])
                if index:
                    if not index[0] in buffer_refresh:
                        self.buffers[index[0]].nicklist = {}
                    buffer_refresh[index[0]] = True
                    if item['group']:
                        group = item['name']
                    self.buffers[index[0]].nicklist_add_item(
                        group, item['group'], item['prefix'], item['name'],
                        item['visible'])
        for index in buffer_refresh:
            self.buffers[index].nicklist_refresh()

    def _parse_nicklist_diff(self, message):
        """Parse a WeeChat message with a buffer nicklist diff."""
        buffer_refresh = {}
        for obj in message.objects:
            if obj.objtype != 'hda' or \
               obj.value['path'][-1] != 'nicklist_item':
                continue
            group = '__root'
            for item in obj.value['items']:
                index = self._buffer_index("pointer", item['__path'][0])
                if not index:
                    continue
                buffer_refresh[index[0]] = True
                if item['_diff'] == ord('^'):
                    group = item['name']
                elif item['_diff'] == ord('+'):
                    self.buffers[index[0]].nicklist_add_item(
                        group, item['group'], item['prefix'], item['name'],
                        item['visible'])
                elif item['_diff'] == ord('-'):
                    self.buffers[index[0]].nicklist_remove_item(
                        group, item['group'], item['name'])
                elif item['_diff'] == ord('*'):
                    self.buffers[index[0]].nicklist_update_item(
                        group, item['group'], item['prefix'], item['name'],
                        item['visible'])
        for index in buffer_refresh:
            self.buffers[index].nicklist_refresh()

    def _parse_buffer_opened(self, message):
        """Parse a WeeChat message with a new buffer (opened)."""
        for obj in message.objects:
            if obj.objtype != 'hda' or obj.value['path'][-1] != 'buffer':
                continue
            for item in obj.value['items']:
                buf = self.create_buffer(item)
                index = self.find_buffer_index_for_insert(item['next_buffer'])
                self.insert_buffer(index, buf)

    def _parse_buffer(self, message):
        """Parse a WeeChat message with a buffer event
        (anything except a new buffer).
        """
        for obj in message.objects:
            if obj.objtype != 'hda' or obj.value['path'][-1] != 'buffer':
                continue
            for item in obj.value['items']:
                index = self._buffer_index("pointer", item['__path'][0])
                if not index:
                    continue
                index = index[0]
                if message.msgid == '_buffer_type_changed':
                    self.buffers[index].data['type'] = item['type']
                elif message.msgid in ('_buffer_moved', '_buffer_merged',
                                       '_buffer_unmerged'):
                    buf = self.buffers[index]
                    self._buffer_reorder_from_msg(buf, item, message.msgid)
                    self.remove_buffer(index)
                    index2 = self.find_buffer_index_for_insert(
                        item['next_buffer'])
                    self.insert_buffer(index2, buf)
                elif message.msgid == '_buffer_renamed':
                    self.buffers[index].data['full_name'] = item['full_name']
                    self.buffers[index].data['short_name'] = item['short_name']
                elif message.msgid == '_buffer_title_changed':
                    self.buffers[index].data['title'] = item['title']
                    self.buffers[index].update_title()
                elif message.msgid == '_buffer_cleared':
                    self.buffers[index].widget.chat.clear()
                elif message.msgid.startswith('_buffer_localvar_'):
                    self.buffers[index].data['local_variables'] = \
                        item['local_variables']
                    self.buffers[index].update_prompt()
                elif message.msgid == '_buffer_closing':
                    buf = self.buffers[index]
                    self._buffer_reorder_from_msg(buf, item, message.msgid)
                    self.remove_buffer(index)

    def _buffer_reorder_from_msg(self, buf, item, msgid):
        """Reorder all the buffer numbers in response to an action."""
        # buf is the buffer that was reorganized; item is what we know
        # post-reorganization. msgid is what happened.
        renumber_queue = []
        for b in self.buffers:
            n = b.data['number']
            if msgid in ['_buffer_moved', '_buffer_opened',
                         '_buffer_unmerged'] and n >= item['number']:
                renumber_queue.append((b, 1, None))
            if msgid in ['_buffer_moved', '_buffer_closing',
                         '_buffer_merged'] and n >= buf.data['number']:
                renumber_queue.append((b, -1, None))
            if msgid == '_buffer_moved' and n == item['number']:
                if n >= buf.data['number']:
                    renumber_queue.append((b, -1, None))
            if n == buf.data['number']:
                if msgid == '_buffer_closing' and b.pointer != buf.pointer:
                    return
                elif msgid == '_buffer_moved':
                    renumber_queue.append((b, None, item['number']))
        for b, mod, rep in renumber_queue:
            b.data['number'] = rep if rep else (b.data['number'] + mod)
        buf.data['number'] = item['number'] if 'number' in item else 0

    def parse_message(self, message):
        """Parse a WeeChat message."""
        if message.msgid.startswith('debug'):
            self.debug_display(0, '', '(debug message, ignored)')
        elif message.msgid == 'listbuffers':
            self._parse_listbuffers(message)
        elif message.msgid in ('listlines', '_buffer_line_added'):
            self._parse_line(message)
        elif message.msgid in ('_nicklist', 'nicklist'):
            self._parse_nicklist(message)
        elif message.msgid == '_nicklist_diff':
            self._parse_nicklist_diff(message)
        elif message.msgid == '_buffer_opened':
            self._parse_buffer_opened(message)
        elif message.msgid.startswith('_buffer_'):
            self._parse_buffer(message)
        elif message.msgid == '_upgrade':
            self.network.desync_weechat()
        elif message.msgid == '_upgrade_ended':
            self.network.sync_weechat()
        elif message.msgid == 'hotlist':
            self._parse_hotlist(message)
        elif message.msgid == '_pong':
            # Workaround for "hotlist" not being sent when empty before 1.6
            if self._last_msgid != "hotlist":
                self._parse_hotlist(message)
        elif message.msgid == 'id':
            self.network.set_info(message)
        self._last_msgid = message.msgid

    def create_buffer(self, item):
        """Create a new buffer."""
        buf = Buffer(item)
        buf.bufferInput.connect(self.buffer_input)
        buf.widget.input.bufferSwitchPrev.connect(
            self.switch_buffers.switch_prev_buffer)
        buf.widget.input.bufferSwitchNext.connect(
            self.switch_buffers.switch_next_buffer)
        buf.widget.input.bufferSwitchActive.connect(
            self.switch_buffers.switch_active_buffer)
        buf.widget.input.bufferSwitchActivePrevious.connect(
            self.switch_buffers.switch_active_buffer_previous)
        return buf

    def insert_buffer(self, index, buf):
        """Insert a buffer in list."""
        self.buffers.insert(index, buf)
        self.stacked_buffers.insertWidget(index, buf.widget)
        self.switch_buffers.insert(index, buf)

    def remove_buffer(self, index):
        """Remove a buffer."""
        self.switch_buffers.take(self.buffers[index])
        self.stacked_buffers.removeWidget(self.stacked_buffers.widget(index))
        self.buffers.pop(index)

    def find_buffer_index_for_insert(self, next_buffer):
        """Find position to insert a buffer in list."""
        index = -1
        if next_buffer == '0x0':
            index = len(self.buffers)
        else:
            index = self._buffer_index("pointer", next_buffer)
            if index:
                index = index[0]
        if index < 0:
            print('Warning: unable to find position for buffer, using end of '
                  'list by default')
            index = len(self.buffers)
        return index

    def _buffer_index(self, key, value):
        if key == "pointer":
            l = [i for i, b in enumerate(self.buffers) if b.pointer == value]
        else:
            l = [i for i, b in enumerate(self.buffers) if b.data[key] == value]
        return l

    def closeEvent(self, event):
        """Called when QWeeChat window is closed."""
        self.network.disconnect_weechat()
        if self.debug_dialog:
            self.debug_dialog.close()
        config.write(self.config)
        QtGui.QMainWindow.closeEvent(self, event)


app = QtGui.QApplication(sys.argv)
app.setStyle(QtGui.QStyleFactory.create('Cleanlooks'))
app.setWindowIcon(utils.qicon_from_theme('weechat'))
main = MainWindow()
sys.exit(app.exec_())
