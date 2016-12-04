# -*- coding: utf-8 -*-
#
# network.py - I/O with WeeChat/relay
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

import struct
import qt_compat
import config

QtCore = qt_compat.import_module('QtCore')
QtNetwork = qt_compat.import_module('QtNetwork')
QtGui = qt_compat.import_module('QtGui')

_PROTO_INIT_CMD = ['init password=%(password)s']

_PROTO_SYNC_CMDS = [
    '(id) info version',
    '(listbuffers) hdata buffer:gui_buffers(*) number,full_name,short_name,'
    'type,nicklist,title,local_variables,notify,hidden,highlight',

    '(listlines) hdata buffer:gui_buffers(*)/own_lines/last_line(-%(lines)d)/'
    'data date,displayed,prefix,message,notify,hidden,highlight',

    '(nicklist) nicklist',

    '(hotlist) hdata hotlist:gui_hotlist(*) buffer, count',

    'sync',

    ''
]

_PROTO_PING_CMDS = [
    '(hotlist) hdata hotlist:gui_hotlist(*) buffer, count',

    '(ping) ping',

    ''
]


class Network(QtCore.QObject):
    """I/O with WeeChat/relay."""

    statusChanged = qt_compat.Signal(str, str)
    messageFromWeechat = qt_compat.Signal(QtCore.QByteArray)

    def __init__(self, *args):
        QtCore.QObject.__init__(*(self,) + args)
        self.status_disconnected = 'disconnected'
        self.status_connecting = 'connecting...'
        self.status_connected = 'connected'
        self.server_version = 0
        self._server = None
        self._port = None
        self._ssl = None
        self._password = None
        self._lines = config.CONFIG_DEFAULT_RELAY_LINES
        self._ping = config.CONFIG_DEFAULT_RELAY_PING
        self._response_qtime = QtCore.QTime()
        self._buffer = QtCore.QByteArray()
        self._socket = QtNetwork.QSslSocket()
        self._socket.connected.connect(self._socket_connected)
        self._socket.error.connect(self._socket_error)
        self._socket.readyRead.connect(self._socket_read)
        self._socket.disconnected.connect(self._socket_disconnected)
        self._hotlist_timer = QtCore.QTimer()
        self._hotlist_timer.timeout.connect(self.ping_weechat)

    def _reconnect_weechat(self):
        server = self._server
        port = self._port
        ssl = self._ssl
        password = self._password
        lines = self._lines
        ping = self._ping
        self.disconnect_weechat()
        self.connect_weechat(server, port, ssl, password, lines, ping)

    def _socket_connected(self):
        """Slot: socket connected."""
        self.statusChanged.emit(self.status_connected, None)
        if self._password:
            self.send_to_weechat('\n'.join(_PROTO_INIT_CMD + _PROTO_SYNC_CMDS)
                                 % {'password': str(self._password),
                                    'lines': self._lines})
        self._hotlist_timer.start(self._ping * 1000)

    def _socket_error(self, error):
        """Slot: socket error."""
        self._hotlist_timer.stop()
        self.statusChanged.emit(
            self.status_disconnected,
            'Failed, error: %s' % self._socket.errorString())
        if QtGui.QApplication.instance().config.getboolean(
                'relay', 'autoconnect'):
            self._reconnect_weechat()

    def _socket_read(self):
        """Slot: data available on socket."""
        data = self._socket.readAll()
        self._buffer.append(data)
        while len(self._buffer) >= 4:
            remainder = None
            length = struct.unpack('>i', self._buffer[0:4])[0]
            if len(self._buffer) < length:
                # partial message, just wait for end of message
                break
            # more than one message?
            if length < len(self._buffer):
                # save beginning of another message
                remainder = self._buffer[length:]
                self._buffer = self._buffer[0:length]
            self.messageFromWeechat.emit(self._buffer)
            if not self.is_connected():
                return
            self._buffer.clear()
            if remainder:
                self._buffer.append(remainder)
        self._response_qtime.start()

    def _socket_disconnected(self):
        """Slot: socket disconnected."""
        self._server = None
        self._port = None
        self._ssl = None
        self._password = None
        self._hotlist_timer.stop()
        self.statusChanged.emit(self.status_disconnected, None)

    def is_connected(self):
        """Return True if the socket is connected, False otherwise."""
        return self._socket.state() == QtNetwork.QAbstractSocket.ConnectedState

    def is_ssl(self):
        """Return True if SSL is used, False otherwise."""
        return self._ssl

    def connect_weechat(self, server, port, ssl, password, lines, ping):
        """Connect to WeeChat."""
        self._server = server
        try:
            self._port = int(port)
        except ValueError:
            self._port = 0
        self._ssl = ssl
        self._password = password
        try:
            self._lines = int(lines)
        except ValueError:
            self._lines = config.CONFIG_DEFAULT_RELAY_LINES
        try:
            self._ping = int(ping)
        except ValueError:
            self._ping = config.CONFIG_DEFAULT_RELAY_PING
        if self._socket.state() == QtNetwork.QAbstractSocket.ConnectedState:
            return
        if self._socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
            self._socket.abort()
        self._socket.connectToHost(self._server, self._port)
        if self._ssl:
            self._socket.ignoreSslErrors()
            self._socket.startClientEncryption()
        self.statusChanged.emit(self.status_connecting, None)

    def disconnect_weechat(self):
        """Disconnect from WeeChat."""
        if self._socket.state() == QtNetwork.QAbstractSocket.UnconnectedState:
            return
        if self._socket.state() == QtNetwork.QAbstractSocket.ConnectedState:
            self.send_to_weechat('quit\n')
            self._socket.waitForBytesWritten(1000)
        else:
            self.statusChanged.emit(self.status_disconnected, None)
        self._hotlist_timer.stop()
        self._socket.abort()

    def send_to_weechat(self, message):
        """Send a message to WeeChat."""
        self._socket.write(message.encode('utf-8'))

    def desync_weechat(self):
        """Desynchronize from WeeChat."""
        self.send_to_weechat('desync\n')

    def sync_weechat(self):
        """Synchronize with WeeChat."""
        self.send_to_weechat('\n'.join(_PROTO_SYNC_CMDS))

    def ping_weechat(self):
        """Ping WeeChat and recieve the hotlist if present."""
        if (self._response_qtime.elapsed() > (self._ping * 2000) and
                QtGui.QApplication.instance().config.getboolean(
                    'relay', 'autoconnect')):
            self._reconnect_weechat()
        self.send_to_weechat('\n'.join(_PROTO_PING_CMDS))

    def set_ping(self, ping):
        try:
            self._ping = int(ping)
        except ValueError:
            self._ping = config.CONFIG_DEFAULT_RELAY_PING
        self._response_qtime.start()
        if self._hotlist_timer.isActive():
            self._hotlist_timer.start(self._ping * 1000)

    def set_info(self, message):
        """Set server info (version)."""
        for obj in message.objects:
            if obj.objtype == "inf" and obj.value[0] == "version":
                self.server_version = float(obj.value[1])

    def status_icon(self, status):
        """Return the name of icon for a given status."""
        icon = {
            self.status_disconnected: 'dialog-close',
            self.status_connecting: 'dialog-close',
            self.status_connected: 'dialog-ok-apply',
        }
        return icon.get(status, '')

    def get_options(self):
        """Get connection options."""
        return {
            'server': self._server,
            'port': self._port,
            'ssl': 'on' if self._ssl else 'off',
            'password': self._password,
            'lines': str(self._lines),
            'ping': str(self._ping),
        }
