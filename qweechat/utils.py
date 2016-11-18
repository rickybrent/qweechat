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
