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
        self.hide_nick_changes = False
        self.hide_join_and_part = False
        self.indent = False

        self.readOnly = True
        self.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse |
                                     QtCore.Qt.TextSelectableByMouse |
                                     QtCore.Qt.TextSelectableByKeyboard)
        self.setOpenExternalLinks(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        # Avoid setting the font family here so it can be changed elsewhere.
        self._textcolor = self.textColor()
        self._bgcolor = QtGui.QColor('#FFFFFF')
        self._setcolorcode = {
            'F': (self.setTextColor, self._textcolor),
            'B': (self.setTextBackgroundColor, self._bgcolor)
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
        if self.hide_join_and_part and prefix[-3:] in ('<--', '-->'):
            return
        if (self.hide_nick_changes and prefix[-2:] == '--' and
                text.find('is now known as')):
            return
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
        self.scroll_bottom()

    def _display_with_colors(self, string):
        self.setTextColor(self._textcolor)
        self.setTextBackgroundColor(self._bgcolor)
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
                            self._setcolorcode[action][0](
                                self._setcolorcode[action][1])
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
            QtGui.QTextEdit.insertHtml(self, link_item)
        else:
            QtGui.QTextEdit.insertPlainText(self, item)

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
