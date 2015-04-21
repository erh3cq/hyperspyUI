# -*- coding: utf-8 -*-
"""
Created on Mon Nov 17 14:16:41 2014

@author: Vidar Tonaas Fauske
"""


from python_qt_binding import QtGui, QtCore
from QtCore import *
from QtGui import *

import types

from hyperspyui.exceptions import ProcessCanceled


def tr(text):
    return QCoreApplication.translate("Threaded", text)


class Worker(QObject):
    progress = QtCore.Signal(int)
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, run):
        super(Worker, self).__init__()
        self.run_function = run

    def process(self):
        self.progress.emit(0)
        if isinstance(self.run_function, types.GeneratorType):
            p = 0
            self.progress.emit(p)
            while p < 100:
                p = self.run_function()
                self.progress.emit(p)
        else:
            self.run_function()
        self.progress.emit(100)
        self.finished.emit()


class Threaded(QObject):

    """
    Executes a user provided function in a new thread, and pops up a
    QProgressBar until it finishes. To have an updating progress bar,
    have the provided function be a generator, and yield completion rate
    in percent (int from 0 to 100).
    """

    pool = []

    def add_to_pool(instance):
        Threaded.pool.append(instance)

    def remove_from_pool(instance):
        Threaded.pool.remove(instance)

    def __init__(self, parent, run, finished=None):
        super(Threaded, self).__init__(parent)

        # Create thread/objects
        self.thread = QThread()
        worker = Worker(run)
        worker.moveToThread(self.thread)
        Threaded.add_to_pool(self)

        # Connect error reporting
        worker.error[str].connect(self.errorString)

        # Start up
        self.thread.started.connect(worker.process)

        # Clean up
        worker.finished.connect(self.thread.quit)
        worker.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        if finished is not None:
            worker.finished.connect(finished)

        def remove_ref():
            Threaded.remove_from_pool(self)
        self.thread.finished.connect(remove_ref)

        # Need to keep ref so they stay in mem
        self.worker = worker

    def errorString(self, error):
        print error

    def run(self):
        self.thread.start()


class ProgressThreaded(Threaded):

    def __init__(self, parent, run, finished=None, label=None, cancellable=False,
                 title=tr("Processing"), modal=True, generator_N=None):
        self.modal = modal
        self.generator_N = generator_N

        # Create progress bar.
        progressbar = QProgressDialog(parent)
        if isinstance(run, types.GeneratorType):
            progressbar.setMinimum(0)
            if generator_N is None:
                generator_N = 100
            elif generator_N <= 1:
                progressbar.setMaximum(0)
            else:
                progressbar.setMaximum(generator_N)
        else:
            progressbar.setMinimum(0)
            progressbar.setMaximum(0)

#        progressbar.hide()
        progressbar.setWindowTitle(title)
        progressbar.setLabelText(label)
        if not cancellable:
            progressbar.setCancelButtonText(None)

        if isinstance(run, types.GeneratorType):
            def run_gen():
                for p in run:
                    self.worker.progress[int].emit(p)
                    if self.progressbar.wasCanceled():
                        raise ProcessCanceled(tr("User cancelled operation"))

            super(ProgressThreaded, self).__init__(parent, run_gen, finished)
        else:
            super(ProgressThreaded, self).__init__(parent, run, finished)

        self.connect(self.thread, SIGNAL('started()'), self.display)
        self.connect(self.worker, SIGNAL('finished()'), self.close)
        self.connect(
            self.worker, SIGNAL('progress(int)'), progressbar.setValue)
        self.progressbar = progressbar

    def display(self):
        if not self.thread.isFinished():
            if self.modal:
                self.progressbar.exec_()
            else:
                self.progressbar.show()

    def close(self):
        self.progressbar.close()
        self.progressbar.deleteLater()
