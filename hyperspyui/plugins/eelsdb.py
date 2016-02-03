# -*- coding: utf-8 -*-
# Copyright 2014-2016 The HyperSpyUI developers
#
# This file is part of HyperSpyUI.
#
# HyperSpyUI is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HyperSpyUI is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HyperSpyUI.  If not, see <http://www.gnu.org/licenses/>.
"""
Created on Mon May 04 17:30:36 2015

@author: Vidar Tonaas Fauske
"""

from hyperspyui.plugins.plugin import Plugin

from python_qt_binding import QtGui, QtCore, QtWebKit, QtNetwork
from QtCore import *
from QtGui import *
from QtWebKit import *
from QtNetwork import *

try:
    assert(QSslSocket.supportsSsl())
except NameError, AssertionError:
    raise ImportError("Current platform doesn't support SSL. EELSDB plugin"
                      " disabled.")

from hyperspyui.widgets.extendedqwidgets import ExToolWindow
import os
import re
import urllib2
import tempfile

re_dl_url = re.compile(
    r'https?://eelsdb\.eu/wp-content/uploads/\d{4}/\d{2}/.+\.msa')


class EELSDBPlugin(Plugin):
    name = "EELSDB Plugin"

    def __init__(self, main_window):
        super(EELSDBPlugin, self).__init__(main_window)
        self.window = None
        self.view = None

    def create_actions(self):
        self.add_action(self.name + '.browse', "Browse EELSDB", self.default,
                        tip="Browse the EELSDB online database of standard"
                        "EEL spectra")

    def create_menu(self):
        self.add_menuitem('EELS', self.ui.actions[self.name + '.browse'])

    def _make_request(self, url):
        request = QNetworkRequest()
        request.setUrl(QUrl(url))
        return request

    def load_blocking(self, view, *args):
        loop = QEventLoop()
        view.loadFinished.connect(loop.quit)

        def unravel():
            view.loadFinished.disconnect(loop.quit)
            view.loadFinished.disconnect(unravel)

        view.loadFinished.connect(unravel)
        view.load(*args)
        loop.exec_()

    def _on_link(self, url):
        su = url.toString(QUrl.RemoveQuery)
        if "/spectra/" in su:
            view = QWebView(self.ui)
            wp = QWebPage()
            am = self.view.page().networkAccessManager()
            wp.setNetworkAccessManager(am)
            view.setPage(wp)
            request = self._make_request(url)
            response = am.get(request)

            def resp_finished():
                html = response.readAll()
                matches = re_dl_url.findall(html)
                self.download(str(matches[0]))
                response.deleteLater()
            response.finished.connect(resp_finished)
        else:
            self.view.load(url)

    def download(self, url):
        header = {'Accept': r'text/html,application/xhtml+xml,'
                  'application/xml;q=0.9,*/*;q=0.8',
                  'Accept-Encoding': r'gzip, deflate',
                  'User-Agent': r'Mozilla/5.0 (Windows NT 10.0; WOW64;'
                  ' rv:43.0)Gecko/20100101 Firefox/43.0',
                  }

        suffix = '.msa'

        req = urllib2.Request(url, headers=header)
        page = urllib2.urlopen(req)

        try:
            f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            fn = f.name
            f.write(page.read())
            fn = f.name
            f.close()
            self.ui.load([fn])
        finally:
            f.close()
            os.remove(fn)
        self.record_code("<p>.download(url='%s')" % url)

    def default(self):
        if self.window is None:
            self.window = ExToolWindow(self.ui)
            self.window.setWindowTitle("EELSDB")
            vbox = QVBoxLayout()
            self.window.setLayout(vbox)
            view = QWebView(self.ui)
            self.view = view
            vbox.addWidget(view)
            self.window.resize(self.view.sizeHint())
        # Load spectra browser
        browse_url = QUrl("https://eelsdb.eu/spectra")
        self.load_blocking(self.view, browse_url)
        # Remove header/footer
        frame = self.view.page().mainFrame()
        frame.findFirstElement(".footer").removeFromDocument()
        for el in frame.findAllElements(".navbar"):
            el.removeFromDocument()
        self.view.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.view.linkClicked.connect(self._on_link)
        self.window.show()
