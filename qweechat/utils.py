# -*- coding: utf-8 -*-
#
# utils.py - helper methods for QWeeChat
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


from pkg_resources import resource_filename
import qt_compat

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')


def build_actions(actions_def, widget):
    actions = {}
    for name, action in list(actions_def.items()):
        actions[name] = QtGui.QAction(name.capitalize(), widget)
        if name == "separator":
            actions[name].setSeparator(True)
            continue
        elif len(action) == 5:
            actions[name].setCheckable(True)
        elif action[0]:
            actions[name].setIcon(QtGui.QIcon(
                resource_filename(__name__, 'data/icons/%s' % action[0])))
        actions[name].setStatusTip(action[1])
        actions[name].setShortcut(action[2])
        actions[name].triggered.connect(action[3])
    return actions


def separator(widget):
    return build_actions({'separator': True}, widget)['separator']


class Font():
    """TODO: Change this to a wrapper or subclass of QtGui.QFont."""

    @staticmethod
    def qfont_to_str(qfont):
        """Create a human readable string from a QFont object."""
        font_str = qfont.family()
        if font_str.find(' ') >= 0:
            font_str = '"' + font_str + '"'
        if qfont.pointSizeF() < 0:
            font_str += " " + str(qfont.pixelSize()) + "px"
        else:
            if qfont.pointSizeF() == qfont.pointSize():
                font_str += " " + str(qfont.pointSize()) + "pt"
            else:
                font_str += " " + str(qfont.pointSizeF()) + "pt"
        font_str += (" bold" if qfont.bold() else "")
        font_str += (" italic" if qfont.italic() else "")
        font_str += (" underline" if qfont.underline() else "")
        font_str += (" strikeout" if qfont.strikeOut() else "")
        return font_str

    @staticmethod
    def str_to_qfont(font_str, qfont=None):
        """Create a QFont object from a human readable string."""
        if not font_str:
            return None
        if font_str[0] == '"':
            tup = font_str[1:].partition('"')
        else:
            tup = font_str.partition(' ')
        qfont = QtGui.QFont(tup[0])
        details = tup[2].strip().split(' ')
        for detail in details:
            if detail[-2:] == "px" and detail[:2].isdigit():
                qfont.setPixelSize(int(detail[:2]))
            elif detail[-2:] == "pt":
                if detail[:2].isdigit():
                    qfont.setPointSize(int(detail[:2]))
                elif detail[:2].replace(".", "").isdigit():
                    qfont.setPointSizeF(float(detail[:2]))
            elif hasattr(qfont, "set" + detail):
                getattr(qfont, "set" + detail)(True)
        return qfont

    @staticmethod
    def qfont_to_stylesheet(qfont):
        """Create a QFont object from a human readable string."""
        stylesheet = "font-family: " + qfont.family() + ";"
        if qfont.pointSizeF() < 0:
            stylesheet += " font-size: " + str(qfont.pixelSize()) + "px;"
        else:
            stylesheet += " font-size: " + str(qfont.pointSizeF()) + "pt;"
        stylesheet += (" font-weight: bold" if qfont.bold() else ";")
        stylesheet += (" font-style: italic" if qfont.italic() else ";")
        if qfont.underline() or qfont.strikeOut():
            stylesheet += " text-decoration:"
            stylesheet += (" underline" if qfont.underline() else "")
            stylesheet += (" line-through" if qfont.strikeOut() else "")

        return stylesheet
