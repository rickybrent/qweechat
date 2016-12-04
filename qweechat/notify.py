# -*- coding: utf-8 -*-
#
# notify.py - Notifications and systray / indicator
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
import datetime
from pkg_resources import resource_filename
import os
from subprocess import call
import utils
import weechat.color as color

QtCore = qt_compat.import_module('QtCore')
QtGui = qt_compat.import_module('QtGui')
Phonon = qt_compat.import_module('phonon').Phonon
Qt = QtCore.Qt


class NotificationManager(QtCore.QObject):
    """Notifications."""

    statusChanged = qt_compat.Signal(str, str)
    messageFromWeechat = qt_compat.Signal(QtCore.QByteArray)

    def __init__(self, parent, *args):
        QtCore.QObject.__init__(*(self,) + args)
        self.records = {}
        self.taskbar_activity = set()
        self._sounds = {}
        self.parent = parent
        self.tray_icon = QtGui.QSystemTrayIcon()
        self.tint_icons("#000000")
        self.menu = QtGui.QMenu(self.parent)
        self._update_context_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._activated)

    def update(self, event=None):
        """Called by the QMainWindow on show and hide events and to"""
        self._update_context_menu()

    def _toggle_parent_window(self):
        if self.parent.isHidden():
            if self.parent.isMinimized():
                self.parent.showNormal()
            self.parent.show()
        else:
            self.parent.hide()
        self._update_context_menu()

    def _update_context_menu(self):
        """Create a menu object for the context menu."""
        self.menu.clear()
        if self.parent.isHidden():
            self.menu.addAction("Restore Window", self._toggle_parent_window)
        else:
            self.menu.addAction("Hide Window", self._toggle_parent_window)
        self.menu.addAction(utils.separator(self.parent))
        if len(self.records):
            for full_name, records in self.records.items():
                for rec in records:
                    text = " ".join(rec[0:4])
                    action = self.menu.addAction(text[0:50])
                    action.triggered.connect(
                        lambda name=full_name: self._set_current_buffer(name))
            self.menu.addAction(utils.separator(self.parent))
        self.menu.addAction("Quit", QtGui.QApplication.instance().quit)

    def _activated(self, reason):
        self.menu.exec_(QtGui.QCursor.pos())

    def _update_taskbar_state(self):
        """Sets the taskbar to alert if there is taskbar activity."""
        # TODO: Support unity / dock manager counts.
        if len(self.taskbar_activity) > 0:
            QtGui.QApplication.instance().alert(self.parent)

    def tint_icons(self, tint_color):
        """Apply the given tint to the various tray icons."""
        self._tint = tint_color
        self._icons = {
            "connected": utils.qicon_tint("ic_connected", tint_color),
            "connecting": utils.qicon_tint("ic_connecting", tint_color),
            "disconnected": utils.qicon_tint("ic_disconnected", tint_color),
            "hot": utils.qicon_tint("ic_hot", tint_color),
        }
        self.set_icon("disconnected")
        self.update_config()

    def update_config(self):
        """Apply configuration."""
        config_tray_icon = self.config.get("notifications", "tray_icon")
        if config_tray_icon == "always" or self.parent.isHidden():
            self.tray_icon.show()
        elif config_tray_icon == "unread" and len(self.records) > 0:
            self.tray_icon.show()
        else:
            self.tray_icon.hide()
        self._time_format = self.config.get("look", "buffer_time_format")

    def parse_buffer(self, buf, lines=None):
        """Check the buffer object and send any needed notifications."""
        if ("local_variables" not in buf.data or 'notify' not in buf.data):
            return
        local_var = buf.data["local_variables"]
        if ((buf.data['notify'] == 0 and not buf.flag()) or not lines or
                'type' not in local_var or 'nick' not in local_var):
            return
        line = lines[-1][1]
        prefix = color.remove(line[1]).strip(" ")
        text = color.remove(line[2])
        if prefix == local_var["nick"] or (prefix == "*" and
                                           text.split(" ", 1)[0] == prefix):
            return
        d = datetime.datetime.fromtimestamp(float(line[0]))
        date_str = d.strftime(self._time_format)
        title = buf.data["full_name"] + " " + date_str
        cmd_str = title + " " + prefix + " " + text

        # Play a sound. Highlight has priority, then type, then buffer flag.
        if buf.highlight and self._config_get("highlight.sound"):
            self.play_sound(self._config_get("highlight.sound"))
        elif self._config_get(local_var["type"] + ".sound"):
            self.play_sound(self._config_get(local_var["type"] + ".sound"))
        elif buf.flag("beep"):
            self.play_sound(self.config.get("notifications", "beep_sound"))

        # Run a custom command.
        if buf.highlight and self._config_get("highlight.command"):
            call([self._config_get("highlight.command"), cmd_str])
        elif self._config_get(local_var["type"] + ".command"):
            call([self._config_get(local_var["type"] + ".command"), cmd_str])

        # Output to a file.
        if buf.highlight and self._config_get("highlight.file"):
            self._log(cmd_str, self._config_get("highlight.file"))
        elif self._config_get(local_var["type"] + ".file"):
            self._log(cmd_str, (self._config_get(local_var["type"] + ".file")))

        # Display tray activity.
        if (buf.highlight and self._config_get("highlight.tray") == "on" or
                self._config_get(local_var["type"] + ".tray") == "on" or
                buf.flag("tray")):
            if self.config.get("notifications", "tray_icon") == "unread":
                self.tray_icon.show()
            self.add_record(buf.data["full_name"], buf.data["short_name"],
                            date_str, prefix, text)
            self.set_icon("hot")

        # Display a notification message.
        if (buf.highlight and self._config_get("highlight.message") == "on" or
                self._config_get(local_var["type"] + ".message") == "on" or
                buf.flag("beep")):
            self.show_message(title, prefix + " " + text)

        # Flags the taskbar as highlighted.
        if (buf.highlight and self._config_get("highlight.taskbar") == "on" or
                self._config_get(local_var["type"] + ".taskbar") == "on" or
                buf.flag("taskbar")):
            self.taskbar_activity.add(buf.data["full_name"])
            self._update_taskbar_state()

    def _config_get(self, key):
        """Helper method to retrieve notification types with focused state."""
        if self.config.has_option("notifications", key):
            return self.config.get("notifications", key)
        return None

    def add_record(self, full_name, short_name, date_str, prefix, text):
        if full_name not in self.records:
            self.records[full_name] = []
        self.records[full_name].append((short_name, date_str, prefix, text))
        self.set_icon("hot")
        self._update_context_menu()

    def clear_record(self, full_name):
        if full_name in self.records:
            del(self.records[full_name])
            if len(self.records) == 0:
                self.set_icon("connected")
            self._update_context_menu()
        if full_name in self.taskbar_activity:
            self.taskbar_activity.remove(full_name)
            self._update_taskbar_state()

    def set_icon(self, icon_key):
        """Sets the tray icon."""
        self.tray_icon.setIcon(self._icons[icon_key.strip(".")])

    def _set_current_buffer(self, full_name):
        """Activate a buffer from the tray icon or a notice."""
        self.clear_record(full_name)
        self.parent.switch_buffers.set_current_buffer(full_name)

    def show_message(self, title, msg):
        """Show a balloon or notification message using the best method for
           the system. Currently only uses tray messages."""
        self.tray_icon.showMessage(title, msg, QtGui.QSystemTrayIcon.NoIcon)

    def play_sound(self, sound):
        """Play a sound using phonon."""
        if sound not in self._sounds:
            if os.path.isfile(sound):
                src = sound
            else:
                src = resource_filename(__name__, 'data/sounds/%s.ogg' % sound)
            media_src = Phonon.MediaSource(src)
            media_obj = Phonon.MediaObject(self)
            audio_out = Phonon.AudioOutput(Phonon.NotificationCategory, self)
            Phonon.createPath(media_obj, audio_out)
            media_obj.setCurrentSource(media_src)
            self._sounds[sound] = media_obj
        self._sounds[sound].seek(0)
        self._sounds[sound].play()

    def _log(self, text, filename):
        """Log output to a file."""
        f = open(filename, 'a')
        f.write(text + '\n')
        f.close()


    @property
    def config(self):
        """Return config object."""
        return QtGui.QApplication.instance().config
