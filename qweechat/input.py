# -*- coding: utf-8 -*-
#
# input.py - input line for chat and debug window
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
from inputlinespell import InputLineSpell

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')


class InputLineEdit(InputLineSpell):
    """Input line."""

    bufferSwitchPrev = qt_compat.Signal()
    bufferSwitchNext = qt_compat.Signal()
    bufferSwitchActive = qt_compat.Signal()
    bufferSwitchActivePrevious = qt_compat.Signal()
    specialKey = qt_compat.Signal(str)
    textSent = qt_compat.Signal(str)

    def __init__(self, scroll_widget):
        InputLineSpell.__init__(self, False)
        self.scroll_widget = scroll_widget
        self._history = []
        self._history_index = -1

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        scroll = self.scroll_widget.verticalScrollBar()
        text_cursor = self.textCursor()
        newline = (key == QtCore.Qt.Key_Enter or key == QtCore.Qt.Key_Return)
        if modifiers == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
            if key == QtCore.Qt.Key_Tab or key == QtCore.Qt.Key_Backtab:
                self.bufferSwitchPrev.emit()
            elif key == QtCore.Qt.Key_X and not text_cursor.hasSelection():
                self.bufferSwitchActivePrevious.emit()
            else:
                InputLineSpell.keyPressEvent(self, event)
        elif modifiers == QtCore.Qt.ControlModifier:
            if key == QtCore.Qt.Key_PageUp or key == QtCore.Qt.Key_Backtab:
                self.bufferSwitchPrev.emit()
            elif key == QtCore.Qt.Key_PageDown or key == QtCore.Qt.Key_Tab:
                self.bufferSwitchNext.emit()
            elif key == QtCore.Qt.Key_X and not text_cursor.hasSelection():
                self.bufferSwitchActive.emit()
            elif key == QtCore.Qt.Key_C and not text_cursor.hasSelection():
                # We might wish to copy text from the buffer above us:
                self.specialKey.emit("copy")
            elif key == QtCore.Qt.Key_K:
                pass  # TODO: Color
            elif key == QtCore.Qt.Key_Underscore:
                pass  # TODO: Underline
            elif key == QtCore.Qt.Key_B:
                pass  # TODO: Bold
            elif key == QtCore.Qt.Key_I:
                pass  # TODO: Italics
            elif key == QtCore.Qt.Key_R:
                pass  # TODO: Reverse
            else:
                InputLineSpell.keyPressEvent(self, event)
        elif modifiers == QtCore.Qt.AltModifier:
            if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Up):
                self.bufferSwitchPrev.emit()
            elif key in (QtCore.Qt.Key_Right, QtCore.Qt.Key_Down):
                self.bufferSwitchNext.emit()
            elif key == QtCore.Qt.Key_PageUp:
                scroll.setValue(scroll.value() - (scroll.pageStep() / 10))
            elif key == QtCore.Qt.Key_PageDown:
                scroll.setValue(scroll.value() + (scroll.pageStep() / 10))
            elif key == QtCore.Qt.Key_Home:
                scroll.setValue(scroll.minimum())
            elif key == QtCore.Qt.Key_End:
                scroll.setValue(scroll.maximum())
            else:
                InputLineSpell.keyPressEvent(self, event)
        elif key == QtCore.Qt.Key_PageUp:
            scroll.setValue(scroll.value() - scroll.pageStep())
        elif key == QtCore.Qt.Key_PageDown:
            scroll.setValue(scroll.value() + scroll.pageStep())
        elif key == QtCore.Qt.Key_Up or key == QtCore.Qt.Key_Down:
            # Compare position, optionally only nativate history if no change:
            pos1 = self.textCursor().position()
            InputLineSpell.keyPressEvent(self, event)
            pos2 = self.textCursor().position()
            if pos1 == pos2:
                if key == QtCore.Qt.Key_Up:
                    # Add to history if there is text like curses weechat:
                    txt = self.toPlainText().encode('utf-8')
                    if txt != "" and len(self._history) == self._history_index:
                        self._history.append(txt)
                    self._history_navigate(-1)
                elif key == QtCore.Qt.Key_Down:
                    self._history_navigate(1)
        elif newline and modifiers != QtCore.Qt.ShiftModifier:
            self._input_return_pressed()
        else:
            InputLineSpell.keyPressEvent(self, event)

    def _input_return_pressed(self):
        self._history.append(self.toPlainText().encode('utf-8'))
        self._history_index = len(self._history)
        self.textSent.emit(self.toPlainText())
        self.clear()

    def _history_navigate(self, direction):
        if self._history:
            self._history_index += direction
            if self._history_index < 0:
                self._history_index = 0
                return
            if self._history_index > len(self._history) - 1:
                self._history_index = len(self._history)
                self.clear()
                return
            self.setText(self._history[self._history_index])
            # End of line:
            text_cursor = self.textCursor()
            text_cursor.setPosition(len(self._history[self._history_index]))
            self.setTextCursor(text_cursor)

    def copy_history(self, input_line_edit):
        self._history = input_line_edit._history
        self._history_index = input_line_edit._history_index
        self.setHtml(input_line_edit.toHtml())
        prev_cursor = input_line_edit.textCursor()
        text_cursor = self.textCursor()
        text_cursor.setPosition(prev_cursor.position())
        self.setTextCursor(text_cursor)
