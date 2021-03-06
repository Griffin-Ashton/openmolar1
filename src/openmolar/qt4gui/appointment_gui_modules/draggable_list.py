#! /usr/bin/env python
# -*- coding: utf-8 -*-

# ########################################################################### #
# #                                                                         # #
# # Copyright (c) 2009-2015 Neil Wallace <neil@openmolar.com>               # #
# #                                                                         # #
# # This file is part of OpenMolar.                                         # #
# #                                                                         # #
# # OpenMolar is free software: you can redistribute it and/or modify       # #
# # it under the terms of the GNU General Public License as published by    # #
# # the Free Software Foundation, either version 3 of the License, or       # #
# # (at your option) any later version.                                     # #
# #                                                                         # #
# # OpenMolar is distributed in the hope that it will be useful,            # #
# # but WITHOUT ANY WARRANTY; without even the implied warranty of          # #
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           # #
# # GNU General Public License for more details.                            # #
# #                                                                         # #
# # You should have received a copy of the GNU General Public License       # #
# # along with OpenMolar.  If not, see <http://www.gnu.org/licenses/>.      # #
# #                                                                         # #
# ########################################################################### #

import cPickle
import logging

from PyQt4 import QtGui, QtCore

LOGGER = logging.getLogger("openmolar")


class DraggableList(QtGui.QListView):

    '''
    a listView whose items can be moved
    '''

    def __init__(self, parent=None):
        QtGui.QListView.__init__(self, parent)
        self.setDragEnabled(True)
        self.setMinimumHeight(100)

    def sizeHint(self):
        return QtCore.QSize(150, 200)

    def startDrag(self, event):
        LOGGER.debug("Starting drag from position %s", event.pos())
        index = self.indexAt(event.pos())
        if not index.isValid():
            event.ignore()
            return

        # selected is the relevant person object
        selectedApp = self.model().data(index, QtCore.Qt.UserRole)

        LOGGER.debug("Dragging appointment %s", selectedApp)
        if not selectedApp.unscheduled:
            event.ignore()
            return
        if index not in self.selectedIndexes():
            self.setCurrentIndex(index)

        # convert to  a bytestream
        bstream = cPickle.dumps(selectedApp)
        mimeData = QtCore.QMimeData()
        mimeData.setData("application/x-appointment", bstream)
        drag = QtGui.QDrag(self)

        drag.setMimeData(mimeData)
        drag.setDragCursor(QtGui.QPixmap(), QtCore.Qt.MoveAction)

        # allow for scroll area
        real_point = QtCore.QPoint(
            event.pos().x(), event.pos().y() - self.verticalOffset())
        index = self.indexAt(real_point)
        pixmap = QtGui.QPixmap()
        pixmap = pixmap.grabWidget(self, self.rectForIndex(index))
        drag.setPixmap(pixmap)
        drag.setHotSpot(QtCore.QPoint(-10, 0))

        drag.start(QtCore.Qt.CopyAction)

    def mouseMoveEvent(self, event):
        self.startDrag(event)
