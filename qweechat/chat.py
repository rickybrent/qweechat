# -*- coding: utf-8 -*-
#
# chat.py - chat area
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

import cgi
import datetime
import qt_compat
import config
import re
import weechat.color as color
import utils

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')


class ChatTextEdit(QtGui.QTextBrowser):
    """Chat area."""

    def __init__(self, debug, *args):
        QtGui.QTextBrowser.__init__(*(self,) + args)
        self.debug = debug

        # Special config options:
        self._color = color.Color(config.color_options(), self.debug)
        self.time_format = '%H:%M'
        self.indent = False
        self._prefix_set = set()
        self.prefix_colors = dict()

        self.readOnly = True
        self.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse |
                                     QtCore.Qt.TextSelectableByMouse |
                                     QtCore.Qt.TextSelectableByKeyboard)
        self.setOpenExternalLinks(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context)
        # Avoid setting the font family here so it can be changed elsewhere.
        self._default_format = self.currentCharFormat()
        self._setcolorcode = {
            'F': (self.setTextColor, None),
            'B': (self.setTextBackgroundColor, None)
        }
        self._setfont = {
            '*': self.setFontWeight,
            '_': self.setFontUnderline,
            '/': self.setFontItalic
        }
        self._fontvalues = {
            False: {
                '*': QtGui.QFont.Normal,
                '_': False,
                '/': False
            },
            True: {
                '*': QtGui.QFont.Bold,
                '_': True,
                '/': True
            }
        }
        self._timestamp_color = QtGui.QColor('#999999')
        # Table format for indent mode:
        self._table_format = QtGui.QTextTableFormat()
        self._table_format.setBorderStyle(
            QtGui.QTextFrameFormat.BorderStyle_None)
        self._table_format.setBorder(0)
        self._table_format.setCellPadding(0)
        self._table_format.setCellSpacing(0)
        self._table_format.setCellSpacing(0)
        self._align_right = QtGui.QTextBlockFormat()
        self._align_right.setAlignment(QtCore.Qt.AlignRight)

        self.clear()

    def clear(self, *args):
        QtGui.QTextBrowser.clear(*(self,) + args)
        self._table = None

    def display(self, time, prefix, text, forcecolor=None):
        """Display a timestamped line."""
        bar = self.verticalScrollBar()
        bar_scroll = bar.maximum() - bar.value()
        move_anchor = QtGui.QTextCursor.MoveAnchor
        if not self.indent:  # Non-indented text; wraps under name/timestamp
            self._table = None  # Clear in case config changed
            cur = self.textCursor()
            cur.movePosition(QtGui.QTextCursor.End, move_anchor)
        else:  # Indented text; timestamp and names go in different columns.
            if not self._table:
                self._table = self.textCursor().insertTable(1, 3)
                self._table.setFormat(self._table_format)
            else:
                self._table.appendRows(1)
            cur = self._table.cellAt(self._table.rows() - 1,
                                     0).firstCursorPosition()
        if prefix[-3:] in ('<--', '-->'):
            # join/part
            pass
        if prefix[-2:] == '--' and text.find('is now known as') >= 0:
            # nick change
            pass
        self.setTextCursor(cur)
        if time == 0:
            d = datetime.datetime.now()
        else:
            d = datetime.datetime.fromtimestamp(float(time))
        self.setTextColor(self._timestamp_color)
        self.insertPlainText(d.strftime(self.time_format) + ' ')
        if self.indent:  # Move to the next cell if using indentation
            cur.movePosition(QtGui.QTextCursor.NextCell, move_anchor)
            cur.setBlockFormat(self._align_right)
            self.setTextCursor(cur)
        prefix = self._color.convert(prefix)
        text = self._color.convert(text)
        if forcecolor:
            if prefix:
                prefix = '\x01(F%s)%s' % (forcecolor, prefix)
            text = '\x01(F%s)%s' % (forcecolor, text)
        if prefix:
            if prefix not in self._prefix_set:
                self._prefix_set.add(prefix)
                pre_str = prefix.rsplit('\x01', 1)[-1]
                self.prefix_colors[pre_str[10:]] = QtGui.QColor(pre_str[2:9])
            self._display_with_colors(str(prefix).decode('utf-8') + ' ')
        if self.indent:  # Move to the next cell if using indentation
            cur.movePosition(QtGui.QTextCursor.NextCell, move_anchor)
            self.setTextCursor(cur)
        if text:
            self._display_with_colors(str(text).decode('utf-8'))
            if text[-1:] != '\n' and not self.indent:
                self.insertPlainText('\n')
        else:
            self.insertPlainText('\n')
        if bar_scroll < 10 and self.verticalScrollBar().maximum() > 0:
            self.scroll_bottom()

    def _display_with_colors(self, string):
        self._reset_colors()
        self._reset_attributes()
        items = string.split('\x01')
        for i, item in enumerate(items):
            if i > 0 and item.startswith('('):
                pos = item.find(')')
                if pos >= 2:
                    action = item[1]
                    code = item[2:pos]
                    if action == '+':
                        # set attribute
                        self._set_attribute(code[0], True)
                    elif action == '-':
                        # remove attribute
                        self._set_attribute(code[0], False)
                    else:
                        # reset attributes and color
                        if code == 'r':
                            self._reset_attributes()
                            self._reset_colors(action)
                        else:
                            # set attributes + color
                            while code.startswith(('*', '!', '/', '_', '|',
                                                   'r')):
                                if code[0] == 'r':
                                    self._reset_attributes()
                                elif code[0] in self._setfont:
                                    self._set_attribute(
                                        code[0],
                                        not self._font[code[0]])
                                code = code[1:]
                            if code:
                                self._setcolorcode[action][0](
                                    QtGui.QColor(code))
                    item = item[pos+1:]
            if len(item) > 0:
                self.insertPlainText(item)

    def insertPlainText(self, item):
        if "http://" in item or "https://" in item:
            link_item = self.replace_url_to_link(cgi.escape(item)) + " "
            # The extra space prevents the link from wrapping to the next line.
            QtGui.QTextBrowser.insertHtml(self, link_item)
        else:
            QtGui.QTextBrowser.insertPlainText(self, item)

    def resizeEvent(self, event):
        QtGui.QTextBrowser.resizeEvent(self, event)
        # bar = self.verticalScrollBar()
        # if (bar.maximum() - bar.value()) < bar.singleStep():
        self.scroll_bottom()

    @staticmethod
    def replace_url_to_link(value):
        # Replace url to link
        urls = re.compile(
            r"((https?):((//)|(\\\\))+[\w\d:#@%/;$()~_?\+-=\\\.&]*)",
            re.MULTILINE | re.UNICODE)
        value = urls.sub(r'<a href="\1" target="_blank">\1</a>', value)
        # Replace email to mailto
        urls = re.compile(
            r"([\w\-\.]+@(\w[\w\-]+\.)+[\w\-]+)", re.MULTILINE | re.UNICODE)
        value = urls.sub(r'<a href="mailto:\1">\1</a>', value)
        return value

    def _reset_colors(self, fgbg=None):
        self.setCurrentCharFormat(self._default_format)

    def _reset_attributes(self):
        self._font = {}
        for attr in self._setfont:
            self._set_attribute(attr, False)

    def _set_attribute(self, attr, value):
        self._font[attr] = value
        self._setfont[attr](self._fontvalues[self._font[attr]][attr])

    def scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def copy(self):
        """Override the copy method to improve the formatting."""
        cur = self.textCursor()
        text = None
        if cur.hasComplexSelection():
            first_row, num_rows, first_col, num_cols = cur.selectedTableCells()
            rowtext = []
            for row in range(num_rows):
                coltext = []
                for col in range(num_cols):
                    cell = self._table.cellAt(first_row + row, first_col + col)
                    text = cell.firstCursorPosition().block().text().strip()
                    if first_col + col == 1 and text != "*" and text:
                        coltext.append("<" + text + ">")
                    else:
                        coltext.append(text)
                rowtext.append(" ".join(coltext))
            text = "\n".join(rowtext)
        elif cur.hasSelection():
            text = cur.selectedText()
        if text:
            html = cur.selection().toHtml()
            clipboard = QtGui.QApplication.clipboard()
            mime_data = QtCore.QMimeData()
            mime_data.setHtml(html)
            mime_data.setText(text)
            clipboard.setMimeData(mime_data)

    def _context(self, event):
        """Show a context menu when the chat is right clicked."""
        menu = QtGui.QMenu()
        self.actions_def = {
            'copy':       ['edit-copy', False, False,
                           lambda: self.copy()],
            'select all': ['edit-select-all', False, False,
                           lambda: self.selectAll()],
            'clear':      ['edit-clear', False, False,
                           lambda: self.clear()],
        }
        actions = utils.build_actions(self.actions_def, self)
        menu.addActions([
            actions['copy'], actions['select all'], utils.separator(self),
            actions['clear'], utils.separator(self)])
        menu.exec_(self.mapToGlobal(event))
