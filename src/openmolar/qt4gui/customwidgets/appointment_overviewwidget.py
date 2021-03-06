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

from __future__ import division

import datetime
from gettext import gettext as _
import logging
import pickle

from PyQt4 import QtGui, QtCore
from openmolar.settings import localsettings
from openmolar.dbtools import appointments
from openmolar.qt4gui import colours

LOGGER = logging.getLogger("openmolar")

LINECOLOR = QtGui.QColor("#dddddd")
TRANSPARENT = QtCore.Qt.transparent
# APPTCOLORS = colours.APPT_OV_COLORS
APPTCOLORS = colours.APPTCOLORS
BGCOLOR = APPTCOLORS["BACKGROUND"]

RED_PEN = QtGui.QPen(QtCore.Qt.red, 2)
BIG_RED_PEN = QtGui.QPen(QtCore.Qt.red, 4)
GREY_PEN = QtGui.QPen(QtCore.Qt.gray, 1)
GREYLINE_PEN = QtGui.QPen(colours.APPT_LINECOLOUR, 1)
# GREYLINE_PEN.setStyle(QtCore.Qt.DashLine)
BLACK_PEN = QtGui.QPen(QtCore.Qt.black, 1)

CENTRE_OPTION = QtGui.QTextOption(QtCore.Qt.AlignCenter)
CENTRE_OPTION.setWrapMode(QtGui.QTextOption.WordWrap)

class BlinkTimer(QtCore.QTimer):
    '''
    A singleton shared accross all canvas widgets to ensure flashing
    appointments are synchronised.
    '''
    _instance = None
    _initiated = False
    state = True

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(
                BlinkTimer, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, parent=None):
        if not self._initiated:
            super(BlinkTimer, self).__init__(parent)
            self.start(1000)
            self.timeout.connect(self._toggle)
            self._initiated = True

    def _toggle(self):
        self.state = not self.state


class AppointmentOverviewWidget(QtGui.QWidget):

    '''
    a custom widget to provide a week view for a dental appointment book
    '''

    selected_serialno = None
    BROWSING_MODE = 0
    SCHEDULING_MODE = 1
    BLOCKING_MODE = 2
    mode = None

    active_slot = None

    slot_clicked_signal = QtCore.pyqtSignal(object)
    appt_dropped_signal = QtCore.pyqtSignal(object, object)
    header_clicked_signal = QtCore.pyqtSignal(object, object)
    cancel_appointment_signal = QtCore.pyqtSignal(
        object, object, object, object)
    clear_slot_signal = QtCore.pyqtSignal(object, object, object, object)

    def __init__(self, sTime, fTime, slotLength, textDetail, om_gui):
        '''
        useage is (day, startTime,finishTime,slotLength, textDetail, parent)
        startTime,finishTime in format HHMM or HMM or HH:MM or H:MM
        slotLength is the minimum slot length - typically 5 minutes
        textDetail is the number of slots to draw before writing the time text
        parentWidget =optional
        textDetail determines how many slots before a time is printed,
        I like 15minutes
        '''

        super(AppointmentOverviewWidget, self).__init__(om_gui)
        self.om_gui = om_gui
        self.setMinimumSize(self.minimumSizeHint())

        self.setSizePolicy(QtGui.QSizePolicy(
            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding))

        self.font = QtGui.QFont()
        self.font.setPointSize(10)
        fm = QtGui.QFontMetrics(self.font)
        self.timeOffset = fm.width(" 88:88 ")
        self.headingHeight = fm.height()
        # convert times to "minutes past midnight"
        self.startTime = localsettings.minutesPastMidnight(sTime)
        self.endTime = localsettings.minutesPastMidnight(fTime)
        self.slotLength = slotLength
        self.slotCount = (self.endTime - self.startTime) // slotLength
        self.slotHeight = ((self.height() - self.headingHeight) /
                           self.slotCount)
        self.textDetail = textDetail

        self.date = None
        self.dents = []
        self.daystart = {}
        self.dayend = {}
        self.memoDict = {}
        self.flagDict = {}
        self.highlightedRect = None
        self.setMouseTracking(True)
        self.clear()
        self.init_dicts()
        self.setAcceptDrops(True)
        self.drag_appt = None
        self.dropPos = None
        self.enabled_clinicians = ()
        self._mouse_drag_rects = None
        self.mouse_drag_rect = None

        self.blink_on = True  # for flashing effect
        self.blink_timer = BlinkTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)

    def clear(self):
        self.appts = {}
        self.eTimes = {}
        self.clearSlots()
        self.lunches = {}
        self._mouse_drag_rects = None

    def clearSlots(self):
        self.active_slots = []
        self.freeslots = {}
        for dent in self.dents:
            self.freeslots[dent.ix] = []
        self.enabled_clinicians = ()
        self._mouse_drag_rects = None

    def set_active_slots(self, primary_slot, secondary_slots):
        '''
        1 primary slot can be active, and multiple secondary slots
        '''
        self.active_slots = []
        self.active_slots.append(primary_slot)
        for slot in secondary_slots:
            self.active_slots.append(slot)

    def enable_clinician_slots(self, clinicians):
        self.enabled_clinicians = clinicians

    def init_dicts(self):
        for dent in self.dents:
            self.freeslots[dent.ix] = []
            self.appts[dent.ix] = ()
            self.eTimes[dent.ix] = ()
            self.lunches[dent.ix] = ()
            self.memoDict[dent.ix] = ""

    def setStartTime(self, dent):
        self.daystart[dent.ix] = localsettings.minutesPastMidnight(dent.start)

    def setEndTime(self, dent):
        self.dayend[dent.ix] = localsettings.minutesPastMidnight(dent.end)

    def setMemo(self, dent):
        self.memoDict[dent.ix] = dent.memo

    def addSlot(self, slot):
        try:
            self.freeslots[slot.dent].append(slot)
        except KeyError:
            LOGGER.warning(
                "unable to show a slot for clinician %s" % slot.dent)

    def setFlags(self, dent):
        self.flagDict[dent.ix] = dent.flag

    def sizeHint(self):
        return QtCore.QSize(40, 600)

    def minimumSizeHint(self):
        return QtCore.QSize(30, 200)

    def mouseMoveEvent(self, event):
        columnCount = len(self.dents)
        if columnCount == 0:
            return  # nothing to do... and division by zero errors!
        columnWidth = (self.width() - self.timeOffset) / columnCount
        rect = QtCore.QRectF(0, self.headingHeight, self.timeOffset,
                             self.height() - self.headingHeight)
        if rect.contains(event.pos()):    # mouse is over the time column
            self.leaveEvent(event)
            return
        for col, dent in enumerate(self.dents):
            leftx = self.timeOffset + col * columnWidth

            # headings
            rect = QtCore.QRectF(leftx, 0, columnWidth, self.headingHeight)
            if rect.contains(event.pos()):
                self.highlightedRect = rect
                QtGui.QToolTip.showText(event.globalPos(), dent.memo)
                return

            for slot in self.freeslots.get(dent.ix, []):
                slotstart = localsettings.pyTimeToMinutesPastMidnight(
                    slot.date_time.time())
                startcell = (
                    slotstart - self.startTime) / self.slotLength

                rect = QtCore.QRectF(
                    leftx,
                    startcell * self.slotHeight + self.headingHeight,
                    columnWidth,
                    (slot.length / self.slotLength) * self.slotHeight)

                if rect.contains(event.pos()):
                    self.highlightedRect = rect
                    feedback = '%d mins starting at %s with %s' % (
                        slot.length,
                        slot.date_time.strftime("%H:%M"), dent.initials)

                    QtGui.QToolTip.showText(event.globalPos(),
                                            QtCore.QString(feedback))
                    self.update()
                    return

            for appt in (self.appts[dent.ix] + self.eTimes[dent.ix] +
                         self.lunches[dent.ix]):
                if (self.daystart[dent.ix] <= appt.mpm <
                   self.dayend[dent.ix]):
                    startcell = (appt.mpm - self.startTime) / self.slotLength

                    rect = QtCore.QRectF(
                        leftx,
                        startcell * self.slotHeight +
                        self.headingHeight,
                        columnWidth,
                        (appt.length / self.slotLength) * self.slotHeight)

                    if rect.contains(event.pos()):
                        self.highlightedRect = rect
                        self.update()
                        return

        self.highlightedRect = None
        self.update()

    def mousePressEvent(self, event):
        '''
        catch the mouse press event -
        and if you have clicked on an appointment, emit a signal
        the signal has a LIST as argument -
        in case there are overlapping appointments or doubles etc...
        '''

        columnCount = len(self.dents)
        if columnCount == 0:
            return  # nothing to do... and division by zero errors!

        columnWidth = (self.width() - self.timeOffset) / columnCount

        for col, dent in enumerate(self.dents):  # did user click a heading?
            leftx = self.timeOffset + col * columnWidth
            rect = QtCore.QRect(leftx, 0, columnWidth, self.headingHeight)
            if rect.contains(event.pos()):
                self.highlightedRect = rect
                self.header_clicked_signal.emit(dent.ix, self.date)
                return
            for slot in self.freeslots.get(dent.ix, []):
                slotstart = localsettings.pyTimeToMinutesPastMidnight(
                    slot.date_time.time())
                startcell = (
                    slotstart - self.startTime) / self.slotLength

                rect = QtCore.QRect(
                    leftx,
                    startcell * self.slotHeight +
                    self.headingHeight,
                    columnWidth,
                    (slot.length / self.slotLength) * self.slotHeight)

                if rect.contains(event.pos()):
                    self.slot_clicked_signal.emit(slot)
                    return

            if event.type() == QtCore.QEvent.MouseButtonDblClick or \
                    event.button() == QtCore.Qt.RightButton:  # right click
                leftx = self.timeOffset + col * columnWidth

                for appt in self.appts[dent.ix]:
                    startcell = (appt.mpm - self.startTime) / self.slotLength

                    rect = QtCore.QRect(
                        leftx,
                        startcell * self.slotHeight +
                        self.headingHeight,
                        columnWidth,
                        (appt.length / self.slotLength) * self.slotHeight)

                    if rect.contains(event.pos()):
                        self.highlightedRect = rect
                        start_time = "%d:%02d" % (appt.mpm // 60,
                                                  appt.mpm % 60)
                        self.cancel_appointment_signal.emit(
                            (appt.serialno,),
                            start_time,
                            dent.ix,
                            self.date.toPyDate())
                        return

                for appt in self.lunches[dent.ix] + self.eTimes[dent.ix]:
                    startcell = (appt.mpm - self.startTime) / self.slotLength

                    rect = QtCore.QRect(
                        leftx,
                        startcell * self.slotHeight +
                        self.headingHeight,
                        columnWidth,
                        (appt.length / self.slotLength) * self.slotHeight)

                    if rect.contains(event.pos()):
                        self.highlightedRect = rect
                        start= "%d:%02d" % (appt.mpm // 60, appt.mpm % 60)
                        finish = "%d:%02d" % ((appt.mpm + appt.length) // 60,
                                              (appt.mpm + appt.length) % 60)
                        self.clear_slot_signal.emit(start, finish, dent.ix,
                                                    self.date.toPyDate())
                        return

    def leaveEvent(self, event):
        self.highlightedRect = None
        self.update()

    def dragEnterEvent(self, event):
        self._mouse_drag_rects is None
        self.mouse_drag_rect = None
        self.drag_appt = None
        if event.mimeData().hasFormat("application/x-appointment"):
            data = event.mimeData()
            bstream = data.retrieveData("application/x-appointment",
                                        QtCore.QVariant.ByteArray)
            appt = pickle.loads(bstream.toByteArray())
            if self.date >= localsettings.currentDay():
                self.drag_appt = appt
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    @property
    def is_dragging(self):
        return self.mouse_drag_rect is not None

    @property
    def mouse_drag_rects(self):
        if self._mouse_drag_rects is None:
            self._mouse_drag_rects = []

            columnCount = len(self.dents)
            if columnCount == 0:
                return self._mouse_drag_rects

            columnWidth = (self.width() - self.timeOffset) / columnCount

            for col, dent in enumerate(self.dents):
                left_x = self.timeOffset + (col) * columnWidth

                busy_times = [(0, dent.start_mpm)]
                for block in sorted(
                    self.eTimes[dent.ix] +
                    self.lunches[dent.ix] +
                    self.appts[dent.ix]
                ):
                    busy_times.append((block.mpm, block.end_mpm))
                busy_times.append((dent.end_mpm, 1440))

                for pos, (start, finish) in enumerate((busy_times)[:-1]):
                    next_start = busy_times[pos + 1][0]
                    if next_start - finish >= self.drag_appt.length:

                        startcell = (finish - self.startTime) / self.slotLength
                        top_y = startcell * \
                            self.slotHeight + self.headingHeight

                        height = ((next_start - finish)
                                  / self.slotLength) * self.slotHeight

                        rect = QtCore.QRectF(
                            left_x,
                            top_y,
                            columnWidth,
                            height)

                        self._mouse_drag_rects.append((dent.ix, rect))

        return self._mouse_drag_rects

    def dragMoveEvent(self, event):
        self.mouse_drag_rect = None
        if (self.date >= localsettings.currentDay() and
           event.mimeData().hasFormat("application/x-appointment")):

            self.dropPos = QtCore.QPointF(event.pos())
            for dent_ix, rect_f in self.mouse_drag_rects:
                if rect_f.contains(self.dropPos):
                    self.mouse_drag_rect = (dent_ix, rect_f)

                    # now handle the situation where the drag lower border
                    # is outwith the slot
                    height = (self.drag_appt.length / self.slotLength) \
                        * self.slotHeight
                    if self.dropPos.y() + height >= rect_f.bottom():
                        self.dropPos = QtCore.QPointF(
                            self.dropPos.x(), rect_f.bottom() - height)

                    break

            if self.is_dragging:
                event.accept()
            else:
                event.ignore()
            self.update()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.mouse_drag_rect = None
        self.update()
        event.accept()

    def dropEvent(self, event):
        if not self.is_dragging:
            event.ignore()

        LOGGER.debug("%s was dropped at %s", self.drag_appt, self.dropPos)

        date_time = datetime.datetime.combine(
            self.date.toPyDate(),
            localsettings.minutesPastMidnightToPyTime(self.drop_time()))
        dent = self.mouse_drag_rect[0]
        slot = appointments.FreeSlot(date_time, dent, self.drag_appt.length)
        self.appt_dropped_signal.emit(self.drag_appt, slot)

        self.mouse_drag_rect = None
        self.drag_appt = None
        event.accept()

    def drop_time(self):
        '''
        returns minutes past midnight of the drop.
        '''
        current_row = (self.dropPos.y() - self.headingHeight) / self.slotHeight
        mpm = self.startTime + (current_row * self.slotLength)
        mpm = int(5 * round(float(mpm) / 5))
        return mpm

    def paintEvent(self, event=None):
        '''
        draws the widget - recalled at any point by instance.update()
        '''

        if len(self.dents) == 0:
            return  # blank widget if no dents working
        self.dragLine = None

        painter = QtGui.QPainter(self)
        painter.setBrush(BGCOLOR)

        currentSlot = 0

        self.font.setPointSize(localsettings.appointmentFontSize)
        fm = QtGui.QFontMetrics(self.font)
        painter.setFont(self.font)

        self.timeOffset = fm.width(" 88:88 ")
        self.headingHeight = fm.height()

        self.slotHeight = (
            self.height() - self.headingHeight) / self.slotCount

        columnCount = len(self.dents)

        if columnCount == 0:
            columnCount = 1  # avoid division by zero!!
        columnWidth = (self.width() - self.timeOffset) / columnCount

        # put the times down the side

        while currentSlot < self.slotCount:
            # offset the first time.
            if (currentSlot + 2) % self.textDetail == 0:
                y = 0.8 * self.headingHeight + currentSlot * self.slotHeight
                trect = QtCore.QRect(
                    0,
                    y,
                    self.timeOffset,
                    self.textDetail * self.slotHeight
                )
                painter.setPen(BLACK_PEN)
                slot_time = self.startTime + currentSlot * self.slotLength
                painter.drawText(
                    trect, QtCore.Qt.AlignHCenter,
                    localsettings.humanTime(slot_time))

            currentSlot += 1
            col = 0

        for dent in self.dents:
            leftx = self.timeOffset + col * columnWidth
            rightx = self.timeOffset + (col + 1) * columnWidth
            # headings
            painter.setPen(BLACK_PEN)
            painter.setBrush(APPTCOLORS["HEADER"])
            rect = QtCore.QRect(leftx, 0, columnWidth, self.headingHeight)
            painter.drawRoundedRect(rect, 5, 5)
            initials = localsettings.apptix_reverse.get(dent.ix)
            if dent.memo != "":
                initials = "*%s*" % initials
            painter.drawText(rect, QtCore.Qt.AlignHCenter, initials)

            # dentist start/finish
            painter.setBrush(BGCOLOR)

            startcell = ((self.daystart[dent.ix] - self.startTime) /
                         self.slotLength)

            length = self.dayend[dent.ix] - self.daystart[dent.ix]

            startY = startcell * self.slotHeight + self.headingHeight
            endY = (length / self.slotLength) * self.slotHeight
            rect = QtCore.QRectF(leftx, startY, columnWidth, endY)

            if self.flagDict[dent.ix]:
                # don't draw a white canvas if dentist is out of office
                # a white canvas
                painter.save()
                painter.drawRect(rect)

                # grey lines
                painter.setPen(GREYLINE_PEN)
                y = startY
                while y < startY + endY:
                    painter.drawLine(leftx, y, rightx, y)
                    y += self.slotHeight / 2

                painter.restore()
                painter.setPen(BLACK_PEN)
                # emergencies
                for appt in self.eTimes[dent.ix]:
                    painter.save()
                    if (self.daystart[dent.ix] <= appt.mpm <
                            self.dayend[dent.ix]):
                        startcell = (
                            appt.mpm - self.startTime) / self.slotLength

                        rect = QtCore.QRectF(
                            leftx,
                            startcell * self.slotHeight +
                            self.headingHeight,
                            columnWidth,
                            (appt.length / self.slotLength) * self.slotHeight)
                        if self.mode == self.SCHEDULING_MODE:
                            painter.setBrush(APPTCOLORS["BUSY"])
                            painter.setPen(GREY_PEN)
                        elif appt.isEmergency:
                            painter.setBrush(APPTCOLORS["EMERGENCY"])
                        elif appt.name.upper() in APPTCOLORS:
                            painter.setBrush(APPTCOLORS[appt.name.upper()])
                        elif appt.cset in APPTCOLORS:
                            painter.setBrush(APPTCOLORS[appt.cset])
                        else:
                            painter.setBrush(APPTCOLORS["default"])

                        painter.drawRect(rect)
                        text = appt.name[:5]
                        if len(text) < len(appt.name):
                            text += ".."
                        painter.drawText(rect, QtCore.Qt.AlignLeft, text)

                    painter.restore()

                painter.save()
                painter.setBrush(APPTCOLORS["LUNCH"])
                for appt in self.lunches[dent.ix]:
                    if (self.daystart[dent.ix] <= appt.mpm <
                       self.dayend[dent.ix]):
                        startcell = (appt.mpm - self.startTime
                                     ) / self.slotLength

                        rect = QtCore.QRectF(
                            leftx,
                            startcell * self.slotHeight +
                            self.headingHeight,
                            columnWidth,
                            (appt.length / self.slotLength) * self.slotHeight)

                        if self.mode == self.SCHEDULING_MODE:
                            painter.setPen(GREY_PEN)
                        else:
                            painter.setPen(BLACK_PEN)

                        painter.drawRect(rect)
                        painter.drawText(rect, _("Lunch"), CENTRE_OPTION)
                painter.restore()

                # appts
                for appt in self.appts[dent.ix]:
                    if (self.om_gui.pt and
                       appt.serialno == self.om_gui.pt.serialno):
                        painter.setBrush(APPTCOLORS["current_patient"])
                    elif self.mode == self.SCHEDULING_MODE:
                        painter.setPen(GREY_PEN)
                        painter.setBrush(APPTCOLORS["BUSY"])
                    elif appt.name.upper() in APPTCOLORS:
                        painter.setBrush(APPTCOLORS[appt.name.upper()])
                    elif appt.cset in APPTCOLORS:
                        painter.setBrush(APPTCOLORS[appt.cset])
                    else:
                        painter.setBrush(APPTCOLORS["BUSY"])

                    startcell = (appt.mpm - self.startTime) / self.slotLength

                    rect = QtCore.QRectF(
                        leftx,
                        startcell * self.slotHeight + self.headingHeight,
                        columnWidth,
                        (appt.length / self.slotLength) * self.slotHeight
                    )

                    painter.drawRoundedRect(rect, 5, 5)

                    text = appt.trt[:5]
                    if len(text) < len(appt.trt):
                        text += ".."
                    painter.drawText(rect, text, CENTRE_OPTION)

                # slots

                painter.save()
                for slot in self.freeslots.get(dent.ix, []):
                    slotstart = localsettings.pyTimeToMinutesPastMidnight(
                        slot.date_time.time())
                    startcell = (
                        slotstart - self.startTime) / self.slotLength

                    rect = QtCore.QRectF(
                        leftx,
                        startcell * self.slotHeight +
                        self.headingHeight,
                        columnWidth,
                        (slot.length / self.slotLength) * self.slotHeight)

                    if slot.is_primary:
                        brush = APPTCOLORS["SLOT"]
                    else:
                        brush = APPTCOLORS["SLOT2"]
                    if slot in self.active_slots:
                        painter.setPen(BIG_RED_PEN)
                        if self.blink_on:
                            painter.setOpacity(1)
                        else:
                            painter.setOpacity(0.3)
                    else:
                        painter.setPen(RED_PEN)
                        painter.setOpacity(0.6)
                    painter.setBrush(brush)
                    painter.drawRoundedRect(
                        rect.adjusted(1, 0, -1, 0),
                        5, 5)
                    painter.setOpacity(1)
                    painter.drawText(rect,
                                     QtCore.Qt.AlignCenter,
                                     "%s" % slot.length)
                painter.restore()

                # drag drop

                if (self.is_dragging and
                   self.mouse_drag_rect[0] == dent.ix):
                    painter.save()

                    rect = self.mouse_drag_rect[1]

                    painter.setBrush(APPTCOLORS["ACTIVE_SLOT"])
                    painter.drawRect(rect)
                    painter.setPen(RED_PEN)

                    height = (self.drag_appt.length / self.slotLength) \
                        * self.slotHeight

                    rect = QtCore.QRectF(leftx,
                                         self.dropPos.y(),
                                         columnWidth - 1, height)
                    painter.drawRect(rect)

                    self.dragLine = QtCore.QLine(0,
                                                 self.dropPos.y(),
                                                 self.width(),
                                                 self.dropPos.y())

                    trect = QtCore.QRectF(0,
                                          self.dropPos.y(),
                                          self.timeOffset,
                                          height)

                    painter.drawRect(trect)
                    painter.drawText(trect, QtCore.Qt.AlignHCenter,
                                     localsettings.humanTime(self.drop_time()))

                    painter.restore()

            if col > 0:
                painter.save()
                painter.setPen(BLACK_PEN)
                painter.drawLine(leftx, 0, leftx, self.height())
                painter.restore()
            col += 1

        if self.highlightedRect is not None:
            painter.setPen(RED_PEN)
            painter.setBrush(TRANSPARENT)
            painter.drawRoundedRect(self.highlightedRect, 5, 5)
        if self.dragLine:
            painter.setPen(RED_PEN)
            painter.drawLine(self.dragLine)

    def toggle_blink(self):
        if not self.mode == self.SCHEDULING_MODE:
            return
        self.blink_on = self.blink_timer.state
        self.update()


if __name__ == "__main__":

    app = QtGui.QApplication([])
    form = AppointmentOverviewWidget("0800", "1900", 15, 2, None)

    form.show()
    app.exec_()
