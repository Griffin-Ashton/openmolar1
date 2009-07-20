# -*- coding: utf-8 -*-
# Copyright (c) 2009 Neil Wallace. All rights reserved.
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# See the GNU General Public License for more details.

'''
provides the main class which is my gui
'''

from __future__ import division

from PyQt4 import QtGui, QtCore
import os
import sys
import copy
import pickle
import time
import threading
import subprocess

####temp
import contract_gui_module

from openmolar.settings import localsettings, utilities
from openmolar.qt4gui import Ui_main, colours

#-- fee modules which interact with the gui
from openmolar.qt4gui.fees import fees_module, course_module, examdialog, \
perio_tx_dialog, add_tx_to_plan, complete_tx, manipulate_tx_plan, \
daybook_module

from openmolar.qt4gui import forum_gui_module

#--dialogs made with designer
from openmolar.qt4gui.dialogs import Ui_patient_finder, Ui_select_patient, \
Ui_enter_letter_text, Ui_phraseBook, Ui_changeDatabase, Ui_related_patients, \
Ui_options, Ui_surgeryNumber, \
Ui_specify_appointment, Ui_appointment_length, Ui_daylist_print, \
Ui_confirmDentist, Ui_showMemo

#--custom dialog modules
from openmolar.qt4gui.dialogs import finalise_appt_time, recall_app, \
medNotes, saveDiscardCancel, newBPE, \
addTreat, addToothTreat, saveMemo, permissions, alterAday

#-- secondary applications
from openmolar.qt4gui.dialogs import apptTools

#--database modules (do not even think of making db queries from ANYWHERE ELSE)
from openmolar.dbtools import daybook, patient_write_changes, recall, \
cashbook, writeNewPatient, patient_class, search, appointments, \
calldurr, docsprinted, memos, nhs_claims, \
daybookHistory, paymentHistory, courseHistory, estimatesHistory

#--modules which act upon the pt class type (and subclasses)
from openmolar.ptModules import patientDetails, notes, plan, referral, \
standardletter, debug_html, estimates

#--modules which use qprinter
from openmolar.qt4gui.printing import receiptPrint, notesPrint, chartPrint, \
bookprint, letterprint, recallprint, daylistprint, multiDayListPrint, \
accountPrint, estimatePrint, GP17, apptcardPrint, bookprint

#--custom widgets
from openmolar.qt4gui.customwidgets import chartwidget, appointmentwidget, \
toothProps, appointment_overviewwidget, toothProps, perioToothProps, \
perioChartWidget, estimateWidget, aptOVcontrol

#--the main gui class inherits from a lot of smaller classes to make the \
#--code more manageable. (supposedly!)
#--watch out for namespace clashes!!!!!


class historyClass():
    def addHistoryMenu(self):
        self.pastDataMenu=QtGui.QMenu()
        self.pastDataMenu.addAction("Payments history")
        self.pastDataMenu.addAction("Daybook history")
        self.pastDataMenu.addAction("Courses history")
        self.pastDataMenu.addAction("Estimates history")
        self.pastDataMenu.addAction("NHS claims history")

        self.ui.pastData_toolButton.setMenu(self.pastDataMenu)

        QtCore.QObject.connect(self.pastDataMenu,
        QtCore.SIGNAL("triggered (QAction *)"), self.pastData)

        self.debugMenu=QtGui.QMenu()
        self.debugMenu.addAction("Patient table data")
        self.debugMenu.addAction("Treatment table data")
        self.debugMenu.addAction("HDP table data")
        self.debugMenu.addAction("Estimates table data")
        self.debugMenu.addAction("Perio table data")
        self.debugMenu.addAction("Verbose (displays everything in memory)")

        self.ui.debug_toolButton.setMenu(self.debugMenu)

        QtCore.QObject.connect(self.debugMenu,
        QtCore.SIGNAL("triggered (QAction *)"), self.showPtAttributes)

        QtCore.QObject.connect(self.ui.ptAtts_checkBox,
        QtCore.SIGNAL("stateChanged (int)"), self.updateAttributes)

    def pastData(self, arg):
        '''
        called from pastData toolbutton
        '''
        txtype=str(arg.text()).split(" ")[0]
        if txtype == "NHS":
            self.showPastNHSclaims()
        elif txtype == "Payments":
            self.showPaymentHistory()
        elif txtype == "Daybook":
            self.showDaybookHistory()
        elif txtype == "Courses":
            self.showCoursesHistory()
        elif txtype == "Estimates":
            self.showEstimatesHistory()

    def showEstimatesHistory(self):
        html=estimatesHistory.details(self.pt.serialno)
        self.ui.debugBrowser.setText(html)

    def showCoursesHistory(self):
        html=courseHistory.details(self.pt.serialno)
        self.ui.debugBrowser.setText(html)

    def showPaymentHistory(self):
        html=paymentHistory.details(self.pt.serialno)
        self.ui.debugBrowser.setText(html)

    def showDaybookHistory(self):
        html=daybookHistory.details(self.pt.serialno)
        self.ui.debugBrowser.setText(html)

    def nhsClaimsShortcut(self):
        '''
        a convenience function called from the contracts page
        '''
        self.ui.tabWidget.setCurrentIndex(9)
        self.showPastNHSclaims()

    def showPastNHSclaims(self):
        html=nhs_claims.details(self.pt.serialno)
        self.ui.debugBrowser.setText(html)

    def updateAttributes(self, arg=None):
        '''
        refresh the table if the checkbox is toggled
        '''
        if debug_html.existing != "":
            self.showPtAttributes()

    def showPtAttributes(self, arg=None):
        #--load a table of self.pt.attributes
        if arg != None:
            txtype=str(arg.text()).split(" ")[0]
        else:
            txtype=debug_html.existing.split(" ")[0]

        changesOnly=self.ui.ptAtts_checkBox.isChecked()
        html=debug_html.toHtml(self.pt_dbstate, self.pt, txtype, changesOnly)
        self.ui.debugBrowser.setText(html)

class appointmentClass():

    def oddApptLength(self):
        '''
        this is called from within the a dialog when the appointment lenghts
        offered aren't enough!!
        '''
        Dialog = QtGui.QDialog(self)
        dl2 = Ui_appointment_length.Ui_Dialog()
        dl2.setupUi(Dialog)
        if Dialog.exec_():
            hours=dl2.hours_spinBox.value()
            mins=dl2.mins_spinBox.value()
            print hours, "hours", mins, "mins"
            return (hours, mins)

    def addApptLength(self, dl, hourstext, minstext):
        hours, mins=int(hourstext), int(minstext)
        if hours == 1:
            lengthText="1 hour "
        elif hours>1:
            lengthText="%d hours "%hours
        else: lengthText=""
        if mins>0:
            lengthText+="%d minutes"%mins
        lengthText=lengthText.strip(" ")
        try:
            dl.apptlength_comboBox.insertItem(0, QtCore.QString(lengthText))
            dl.apptlength_comboBox.setCurrentIndex(0)
            return
        except Exception, e:
            print e
            self.advise("unable to set the length of the appointment", 1)
            return

    def newAppt(self):
        '''this shows a dialog to get variables required for an appointment'''
        #--check there is a patient attached to this request!
        if self.pt.serialno == 0:
            self.advise(
            "You need to select a patient before performing this action.", 1)
            return

        #--a sub proc for a subsequent dialog
        def makeNow():
            dl.makeNow=True

        def oddLength(i):
            #-- last item of the appointment length combobox is "other length"
            if i == dl.apptlength_comboBox.count()-1:
                ol=self.oddApptLength()
                if ol:
                    QtCore.QObject.disconnect(dl.apptlength_comboBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)
                    self.addApptLength(dl, ol[0], ol[1])
                    QtCore.QObject.connect(dl.apptlength_comboBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)

        #--initiate a custom dialog
        Dialog = QtGui.QDialog(self)
        dl = Ui_specify_appointment.Ui_Dialog()
        dl.setupUi(Dialog)
        #--add an attribute to the dialog
        dl.makeNow=False

        #--add active appointment dentists to the combobox
        dents=localsettings.apptix.keys()
        for dent in dents:
            s=QtCore.QString(dent)
            dl.practix_comboBox.addItem(s)
        #--and select the patient's dentist
        if localsettings.apptix_reverse.has_key(self.pt.dnt1):
            if localsettings.apptix_reverse[self.pt.dnt1] in dents:
                pos=dents.index(localsettings.apptix_reverse[self.pt.dnt1])
                dl.practix_comboBox.setCurrentIndex(pos)
        else:
            dl.practix_comboBox.setCurrentIndex(-1)

        #--add appointment treatment types
        for apptType in localsettings.apptTypes:
            s=QtCore.QString(apptType)
            dl.trt1_comboBox.addItem(s)
            #--only offer exam as treatment1
            if apptType != "EXAM":
                dl.trt2_comboBox.addItem(s)
                dl.trt3_comboBox.addItem(s)
        #--default appt length is 15 minutes
        dl.apptlength_comboBox.setCurrentIndex(2)

        #--connect the dialogs "make now" buttons to the procs just coded
        QtCore.QObject.connect(dl.apptlength_comboBox,
        QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)

        QtCore.QObject.connect(dl.scheduleNow_pushButton,
        QtCore.SIGNAL("clicked()"), makeNow)
        ##TODO - fix this

        dl.scheduleNow_pushButton.setEnabled(False)
        if Dialog.exec_():
            #--practitioner
            practix=localsettings.apptix[str(dl.practix_comboBox.currentText())]
            #--length
            lengthText=str(dl.apptlength_comboBox.currentText())
            if "hour" in lengthText and not "hours " in lengthText:
                lengthText=lengthText.replace("hour", "hours ")
            if "hour" in lengthText:
                length=60*int(lengthText[:lengthText.index("hour")])
                lengthText=lengthText[lengthText.index(" ",
                                                    lengthText.index("hour")):]
            else:
                length=0
            if "minute" in lengthText:
                length+=int(lengthText[:lengthText.index("minute")])
            #--treatments
            code0=dl.trt1_comboBox.currentText()
            code1=dl.trt2_comboBox.currentText()
            code2=dl.trt3_comboBox.currentText()
            #--memo
            note=str(dl.lineEdit.text().toAscii())

            #--if the patients course type isn't present,
            #--we will have issues later
            if self.pt.cset == "":
                cst=32
            else:
                cst=ord(self.pt.cset[0])
            ##TODO - add datespec and joint appointment options

            #--attempt WRITE appointement to DATABASE
            if appointments.add_pt_appt(self.pt.serialno, practix, length,
            code0, -1, code1, code2, note, "", cst):
                self.layout_apptTable()
                if dl.makeNow:
                    self.makeApptButtonClicked()
            else:
                #--commit failed
                self.advise("Error saving appointment", 2)

    def clearApptButtonClicked(self):
        '''user is deleting an appointment'''
        #--selected row
        selectedAppt=self.ui.ptAppointment_treeWidget.currentItem()
        if selectedAppt == None:
            self.advise("No appointment selected", 1)
            return

        #--aprix is a UNIQUE, iterating field in the database starting at 1,
        aprix=int(selectedAppt.text(9))
        dateText=str(selectedAppt.text(0))
        checkdate=localsettings.uk_to_sqlDate(dateText)
        atime=selectedAppt.text(2)
        if atime == "":
            appttime=None
        else:
            appttime=int(atime.replace(":", ""))

        #--is appointment not is aslot (appt book proper) or in the past??
        if dateText == "TBA" or QtCore.QDate.fromString(dateText,
        "dd'/'MM'/'yyyy")<QtCore.QDate.currentDate():
            #--raise a dialog (centred on self)
            result=QtGui.QMessageBox.question(self, "Confirm",
            "Delete this Unscheduled or Past Appointment?",
            QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

            if result == QtGui.QMessageBox.No:
                return
            else:
                if appointments.delete_appt_from_apr(self.pt.serialno, aprix,
                checkdate, appttime):
                    self.advise("Sucessfully removed appointment")
                    self.layout_apptTable()
                else:
                    self.advise("Error removing proposed appointment", 2)
        else:
            #--get dentists number value
            dent=selectedAppt.text(1)
            #--raise a dialog
            result=QtGui.QMessageBox.question(self, "Confirm", \
            "Confirm Delete appointment at %s on %s  with %s"%(
            atime, dateText, dent), QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

            if result == QtGui.QMessageBox.Yes:
                #convert into database varaibles (dentist number)
                dent=localsettings.apptix[str(dent)]
                # time in 830 format (integer)
                start=localsettings.humanTimetoWystime(str(atime))
                #date in sqlformat
                adate=localsettings.uk_to_sqlDate(str(dateText))

                #--delete from the dentists book (aslot)
                if appointments.delete_appt_from_aslot(dent, start, adate,
                self.pt.serialno):
                    ##todo - if we deleted from the appt book,
                    ##we should add to notes
                    print "future appointment deleted - add to notes!!"

                    #--keep in apr? the patient's diary
                    result=QtGui.QMessageBox.question(self,
                    "Question",
                    "Removed from appointment book - keep for rescheduling?",
                    QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

                    if result == QtGui.QMessageBox.Yes:
                        #appointment "POSTPONED" - not totally cancelled
                        if not appointments.made_appt_to_proposed(
                        self.pt.serialno, aprix):
                            self.advise(
                            "Error removing Proposed appointment", 2)
                    else:
                        #remove from the patients diary
                        if not appointments.delete_appt_from_apr(
                        self.pt.serialno, aprix, checkdate, appttime):
                            self.advise(
                            "Error removing proposed appointment", 2)
                else:
                    #--aslot proc has returned False!
                    #let the user know, and go no further
                    self.advise("Error Removing from Appointment Book", 2)
                    return
                self.layout_apptTable()

    def modifyAppt(self):
        '''user is changing an appointment'''

        #--much of this code is a duplicate of make new appt
        selectedAppt=self.ui.ptAppointment_treeWidget.currentItem()

        def makeNow():
            ######temporarily disabled this
            self.advise(
            "this function has been temporarily disabled by Neil, sorry", 1)
            return

            dl.makeNow=True


        def oddLength(i):
            #-- odd appt length selected (see above)
            if i == dl.apptlength_comboBox.count()-1:
                ol=self.oddApptLength()
                if ol:
                    QtCore.QObject.disconnect(dl.apptlength_comboBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)

                    self.addApptLength(dl, ol[0], ol[1])

                    QtCore.QObject.connect(dl.apptlength_comboBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)

        if selectedAppt == None:
            self.advise("No appointment selected", 1)
        else:
            Dialog = QtGui.QDialog(self)
            dl = Ui_specify_appointment.Ui_Dialog()
            dl.setupUi(Dialog)
            dl.makeNow=False

            dents=localsettings.apptix.keys()
            for dent in dents:
                s=QtCore.QString(dent)
                dl.practix_comboBox.addItem(s)
            for apptType in localsettings.apptTypes:
                s=QtCore.QString(apptType)
                dl.trt1_comboBox.addItem(s)
                if apptType != "EXAM":
                    dl.trt2_comboBox.addItem(s)
                    dl.trt3_comboBox.addItem(s)
            length=int(selectedAppt.text(3))
            hours = length//60
            mins = length%60
            self.addApptLength(dl, hours, mins)
            dentist=str(selectedAppt.text(1))
            dateText=str(selectedAppt.text(0))
            if dateText != "TBA":
                for widget in (dl.apptlength_comboBox, dl.practix_comboBox,
                dl.scheduleNow_pushButton):
                    widget.setEnabled(False)
            trt1=selectedAppt.text(4)
            trt2=selectedAppt.text(5)
            trt3=selectedAppt.text(6)
            memo=str(selectedAppt.text(7).toAscii())
            if dentist in dents:
                pos=dents.index(dentist)
                dl.practix_comboBox.setCurrentIndex(pos)
            else:
                print "dentist not found"
            pos=dl.trt1_comboBox.findText(trt1)
            dl.trt1_comboBox.setCurrentIndex(pos)
            pos=dl.trt2_comboBox.findText(trt2)
            dl.trt2_comboBox.setCurrentIndex(pos)
            pos=dl.trt3_comboBox.findText(trt3)
            dl.trt3_comboBox.setCurrentIndex(pos)
            dl.lineEdit.setText(memo)

            QtCore.QObject.connect(dl.apptlength_comboBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"), oddLength)

            QtCore.QObject.connect(dl.scheduleNow_pushButton,
                                   QtCore.SIGNAL("clicked()"), makeNow)
            ##TODO fix this!!
            dl.scheduleNow_pushButton.setEnabled(False)

            if Dialog.exec_():
                practixText=str(dl.practix_comboBox.currentText())
                practix=localsettings.apptix[practixText]
                lengthText=str(dl.apptlength_comboBox.currentText())
                if "hour" in lengthText and not "hours " in lengthText:
                    lengthText=lengthText.replace("hour", "hours ")
                if "hour" in lengthText:
                    length=60*int(lengthText[:lengthText.index("hour")])
                    lengthText=lengthText[
                    lengthText.index(" ", lengthText.index("hour")):]

                else:
                    length=0
                if "minute" in lengthText:
                    length+=int(lengthText[:lengthText.index("minute")])
                code0=dl.trt1_comboBox.currentText()
                code1=dl.trt2_comboBox.currentText()
                code2=dl.trt3_comboBox.currentText()
                note=str(dl.lineEdit.text().toAscii())

                start=localsettings.humanTimetoWystime(str(
                selectedAppt.text(2)))

                aprix=int(selectedAppt.text(9))
                adate=localsettings.uk_to_sqlDate(dateText)

                if self.pt.cset == "":
                    cst=32
                else:
                    cst=ord(self.pt.cset[0])
                appointments.modify_pt_appt(aprix, self.pt.serialno,
                practix, length, code0, code1, code2, note, "", cst)
                if dateText == "TBA":
                    if dl.makeNow:
                        self.makeApptButtonClicked()
                else:
                    if not appointments.modify_aslot_appt(adate, practix, start,
                    self.pt.serialno, code0, code1, code2, note, cst, 0, 0, 0):
                        self.advise("Error putting into dentists book", 2)
                self.layout_apptTable()

    def makeApptButtonClicked(self):
        '''
        make an appointment - switch user to "scheduling mode" and present the
        appointment overview to show possible appointments'''
        selectedAppt=self.ui.ptAppointment_treeWidget.currentItem()
        if selectedAppt == None:
            self.advise("Please select an appointment to schedule", 1)
            return
        dateText=selectedAppt.text(0)
        if str(dateText) != "TBA":
            self.advise("appointment already scheduled for %s"%dateText, 1)
            return
        ##todo implement datespec  -
        ##datespec=self.ui.ptAppointmentTableWidget.item(rowno, 8).text()
        dent=localsettings.apptix[str(selectedAppt.text(1))]
        #--sets "schedule mode" - user is now adding an appointment
        self.aptOVviewMode(False)

        #--does the patient has a previous appointment booked?
        ########################################################################
        ##TODO
        print "NEW CODE NEEDED"
        #need new code here!!!
        '''
        previousApptRow = -1#    rowno-1
        if previousApptRow >= 0:
            #--get the date of preceeding appointment
            try:
                pdateText = str(self.ui.ptAppointmentTableWidget.item(
                                                previousApptRow, 0).text())
                qdate = QtCore.QDate.fromString(pdateText, "dd'/'MM'/'yyyy")
                #--if the date found is earlier than today... it is irrelevant
                if qdate < QtCore.QDate.currentDate():
                    qdate = QtCore.QDate.currentDate()
                self.ui.apptOV_calendarWidget.setSelectedDate(qdate)

            except TypeError:
                #--previous row had TBA as a date and the fromString
                #--raised a TypeError exception? so use today
                self.ui.apptOV_calendarWidget.setSelectedDate(
                                                QtCore.QDate.currentDate())
        else:
        '''
        self.ui.apptOV_calendarWidget.setSelectedDate(
        QtCore.QDate.currentDate())

        #--deselect ALL dentists and hygenists so only one "book" is viewable
        self.ui.aptOV_alldentscheckBox.setChecked(False)
        self.ui.aptOV_allhygscheckBox.setChecked(False)
        #--if previous 2 lines didn't CHANGE the state,
        #--these slots have to be fired manually
        self.apptOVdents()
        self.apptOVhygs()
        try:
            #--SELECT the appointment dentist
            self.ui.aptOVdent_checkBoxes[dent].setChecked(True)
        except KeyError:
            #--oops.. maybe it's a hygenist?
            self.ui.aptOVhyg_checkBoxes[dent].setChecked(True)

        #--compute first available appointment
        self.offerAppt(True)

    def offerAppt(self, firstRun=False):
        '''offer an appointment'''
        selectedAppt = self.ui.ptAppointment_treeWidget.currentItem()
        dateText = selectedAppt.text(0)
        dents = []
        for dent in self.ui.aptOVdent_checkBoxes.keys():
            if self.ui.aptOVdent_checkBoxes[dent].checkState():
                dents.append(dent)
        for hyg in self.ui.aptOVhyg_checkBoxes.keys():
            if self.ui.aptOVhyg_checkBoxes[hyg].checkState():
                dents.append(hyg)
        start = selectedAppt.text(2)
        length = selectedAppt.text(3)
        trt1 = selectedAppt.text(4)
        trt2 = selectedAppt.text(5)
        trt3 = selectedAppt.text(6)
        memo = selectedAppt.text(7)

        #-- self.ui.apptOV_calendarWidget date originally set when user
        #--clicked the make button
        seldate=self.ui.apptOV_calendarWidget.selectedDate()
        today=QtCore.QDate.currentDate()

        if seldate<today:
            self.advise("can't schedule an appointment in the past", 1)
            #-- change the calendar programatically (this will call THIS
            #--procedure again!)
            self.ui.apptOV_calendarWidget.setSelectedDate(today)
            return
        elif seldate.toPyDate()>localsettings.bookEnd:
            self.advise('''Reached %s<br />
            No suitable appointments found<br />
            Is the appointment very long?<br />
            If so, Perhaps cancel some emergency time?
            '''%localsettings.longDate(localsettings.bookEnd), 1)
            return

        else:
            #--select mon-saturday of the selected day
            dayno=seldate.dayOfWeek()
            weekdates=[]
            for day in range(1, 8):
                weekdates.append(seldate.addDays(day-dayno))
            if  today in weekdates:
                startday=today
            else:
                startday=weekdates[0] #--monday
            sunday=weekdates[6]     #--sunday

            #--check for suitable apts in the selected WEEK!
            possibleAppts=appointments.future_slots(int(length),
            startday.toPyDate(), sunday.toPyDate(), tuple(dents))

            if possibleAppts != ():
                #--found some
                for day in weekdates:
                    for apt in possibleAppts:
                        if apt[0] == day.toPyDate():
                            self.ui.apptoverviews[weekdates.index(day)].\
                            freeslots[apt[1]]= apt[2]

                            #--show the appointment overview tab
                            self.ui.main_tabWidget.setCurrentIndex(2)
            else:
                self.advise("no slots available for selected week")
                if firstRun:
                    #--we reached this proc to offer 1st appointmentm but
                    #--haven't found it
                    self.aptOV_weekForward()
                    self.offerAppt(True)

    def makeAppt(self, arg):
        '''
        called by a click on my custom overview slot -
        user has selected an offered appointment
        '''
        #--the pysig arg is in the format (1, (910, 20), 4)
        #-- where 1=monday, 910 = start, 20=length, dentist=4'''
        day=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday")[arg[0]]

        self.advise("offer appointment for %s %s"%(day, str(arg[1])))

        selectedAppt=self.ui.ptAppointment_treeWidget.currentItem()
        dentist=str(selectedAppt.text(1))
        start=selectedAppt.text(2)
        length=int(selectedAppt.text(3))
        trt1=selectedAppt.text(4)
        trt2=selectedAppt.text(5)
        trt3=selectedAppt.text(6)
        memo=str(selectedAppt.text(7).toAscii())
        #--aprix is a UNIQUE field in the database starting at 1,
        aprix=int(selectedAppt.text(9))
        caldate=self.ui.apptOV_calendarWidget.selectedDate()
        appointment_made=False
        dayno=caldate.dayOfWeek()
        selecteddate=caldate.addDays(1-dayno+arg[0])
        selectedtime=arg[1][0]
        slotlength=arg[1][1]
        selectedDent=localsettings.apptix_reverse[arg[2]]
        if selectedDent != dentist:
            #--the user has selected a slot with a different dentist
            #--raise a dialog to check this was intentional!!
            message='''You have chosen an appointment with %s<br />
            Is this correct?'''% selectedDent
            result=QtGui.QMessageBox.question(self, "Confirm", message,
            QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)

            if result == QtGui.QMessageBox.Cancel:
                #dialog rejected
                return

        if slotlength>length:
            #--the slot selected is bigger than the appointment length so
            #--fire up a dialog to allow for fine tuning
            Dialog = QtGui.QDialog(self)
            dl = finalise_appt_time.ftDialog(Dialog, selectedtime,
                                             slotlength, length)

            if Dialog.exec_():
                #--dialog accepted
                selectedtime=dl.selectedtime
                slotlength=length
            else:
                #--dialog cancelled
                return
        if slotlength == length:
            #--ok... suitable appointment found
            message="Confirm Make appointment at %s on %s with %s"%(
            localsettings.wystimeToHumanTime(selectedtime), localsettings.\
            formatDate(selecteddate.toPyDate()), selectedDent)

            #--get final confirmation
            result=QtGui.QMessageBox.question(self, "Confirm", message,
            QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)
            if result == QtGui.QMessageBox.Cancel:
                #dialog rejected
                return

            endtime=localsettings.minutesPastMidnighttoWystime(localsettings.\
            minutesPastMidnight(selectedtime)+length)

            name=self.pt.sname+" "+self.pt.fname[0]

            #--make name conform to the 30 character sql limitation
            #--on this field.
            name=name[:30]
            #--don't throw an exception with ord("")
            if self.pt.cset == "":
                cst=32
            else:
                cst=ord(self.pt.cset[0])

            #-- make appointment
            if appointments.make_appt(
                selecteddate.toPyDate(), localsettings.apptix[selectedDent],
                selectedtime, endtime, name, self.pt.serialno, trt1, trt2,
                trt3, memo, 1, cst, 0, 0):

                ##TODO use these flags for family and double appointments

                if appointments.pt_appt_made(self.pt.serialno, aprix,
                selecteddate.toPyDate(), selectedtime,
                localsettings.apptix[selectedDent]):
                    #-- proc returned True so....update the patient apr table
                    self.layout_apptTable()
                    #== and offer an appointment card
                    result=QtGui.QMessageBox.question(self, "Confirm",
                    "Print Appointment Card?", QtGui.QMessageBox.Ok,
                    QtGui.QMessageBox.Cancel)

                    if result == QtGui.QMessageBox.Ok:
                        self.printApptCard()
                else:
                    self.advise("Error putting appointment back onto patient "+
                    "record - it may be in the appointment book though?", 2)

                #--#cancel scheduling mode
                self.aptOVviewMode(True)
                #take user back to main page
                self.ui.main_tabWidget.setCurrentIndex(0)

            else:
                self.advise("Error making appointment - sorry!", 2)
        else:
            #Hopefully this should never happen!!!!
            self.advise(
            "error - the appointment doesn't fit there.. slotlength "+
            "is %d and we need %d"%(slotlength, length), 2)

    def apptOVheaderclick(self, arg):
        '''a click on the dentist portion of the appointment overview widget'''

        ##TODO doing this should offer the user better options than just this..
        result=QtGui.QMessageBox.question(self, "Confirm",
        "Confirm Print Daybook", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)

        if result == QtGui.QMessageBox.Ok:
            self.printBook(arg)

    def ptApptTableNav(self):
        '''called by signals from the patient's appointment table'''

        selected=self.ui.ptAppointment_treeWidget.currentItem()
        if selected is None or selected.childCount() != 0:
            self.ui.makeAppt_pushButton.setEnabled(False)
            self.ui.modifyAppt_pushButton.setEnabled(False)
            self.ui.clearAppt_pushButton.setEnabled(False)
            self.ui.findAppt_pushButton.setEnabled(False)
            #self.ui.printAppt_pushButton.setEnabled(False)
            return
        if selected.text(0) == "TBA":
            self.ui.makeAppt_pushButton.setEnabled(True)
            self.ui.modifyAppt_pushButton.setEnabled(True)
            self.ui.clearAppt_pushButton.setEnabled(True)
            self.ui.findAppt_pushButton.setEnabled(False)
            #self.ui.printAppt_pushButton.setEnabled(False)
        else:
            self.ui.makeAppt_pushButton.setEnabled(False)
            self.ui.modifyAppt_pushButton.setEnabled(True)
            self.ui.clearAppt_pushButton.setEnabled(True)
            self.ui.findAppt_pushButton.setEnabled(True)
            #self.ui.printAppt_pushButton.setEnabled(True)

    def layout_apptTable(self):
        '''populates the patients appointment table'''

        ##new
        headers=["Date", "Pract..", "Time", "Length", "Trt1", "Trt2", "Trt3",
        "MEMO", "date spec", "orderAdded"]
        self.ui.ptAppointment_treeWidget.clear()
        self.ui.ptAppointment_treeWidget.setHeaderLabels(headers)
        parents={}
        #hflag=QtCore.Qt.QItemFlags(QtCore.Qt.ItemIsSelectable)
        for heading in ("Past", "Unscheduled", "TODAY", "Future"):
            parents[heading]=QtGui.QTreeWidgetItem(
            self.ui.ptAppointment_treeWidget, [heading])

            parents[heading].setTextColor(0, colours.diary[heading])

        rows=appointments.get_pts_appts(self.pt.serialno)
        #--which will give us stuff like...
        #--(4820L, 7, 4, 'RCT', '', '', 'OR PREP', datetime.date(2008, 12, 15),
        #-- 1200, 60, 0, 73, 0, 0, 0, '')
        selectedrow=-1
        today=localsettings.ukToday()
        for row in rows:
            date=row[7]
            if date == None:
                #--appointment not yet scheduled
                date ="TBA"
            #convert dentist from int to initials
            dent=localsettings.apptix_reverse.get(row[2])
            if dent == None:
                self.advise("removing appointment dentist", 1)
                dent=""
            length=str(row[9])
            trt1, trt2, trt3=tuple(row[3:6])
            memo=str(row[6])
            datespec=row[15]
            if row[8] == None:
                start=""
            else:
                start=localsettings.wystimeToHumanTime(int(row[8]))
            appointmentList=[]
            appointmentList.append(date)
            appointmentList.append(dent)
            appointmentList.append(start)
            appointmentList.append(length)
            appointmentList.append(trt1)
            appointmentList.append(trt2)
            appointmentList.append(trt3)
            appointmentList.append(memo)
            appointmentList.append(datespec)
            appointmentList.append(str(row[1]))

            if date == "TBA":
                parent=parents["Unscheduled"]
            elif date == today:
                parent=parents["TODAY"]
            elif localsettings.uk_to_sqlDate(date)<localsettings.sqlToday():
                parent=parents["Past"]
            else:
                parent=parents["Future"]

            w=QtGui.QTreeWidgetItem(parent, appointmentList)
            for i in range (w.columnCount()):
                w.setTextColor(i, parent.textColor(0))
        self.ui.ptAppointment_treeWidget.expandAll()


        for i in range(self.ui.ptAppointment_treeWidget.columnCount()):
            self.ui.ptAppointment_treeWidget.resizeColumnToContents(i)

        if parents["Past"].childCount() != 0:
            parents["Past"].setExpanded(False)


        for parent in parents.values():
            if parent.childCount() == 0:
                self.ui.ptAppointment_treeWidget.removeItemWidget(parent, 0)
            else:
                parent.setFlags(QtCore.Qt.ItemIsEnabled)

        #self.ui.ptAppointment_treeWidget.setColumnWidth(9, 0)


        #--programmatically ensure the correct buttons are enabled
        self.ptApptTableNav()

    def apptTicker(self):
        ''''
        this moves a
        red line down the appointment books -
        note needs to run in a thread!
        '''

        while True:
            time.sleep(30)
            if self.ui.main_tabWidget.currentIndex() == 1:
                self.triangles

    def triangles(self):
        '''
        set the time on the appointment widgets...
        so they can display traingle pointers
        '''
        currenttime="%02d%02d"%(time.localtime()[3], time.localtime()[4])
        d=self.ui.appointmentCalendarWidget.selectedDate()
        if d == QtCore.QDate.currentDate():
            for book in self.ui.apptBookWidgets:
                book.setCurrentTime(currenttime)

    def getappointmentData(self, d, dents=()):
        '''
        gets appointment data for date d.
        '''
        ad=copy.deepcopy(self.appointmentData)
        adate="%d%02d%02d"%(d.year(), d.month(), d.day())
        workingdents=appointments.getWorkingDents(adate, dents)
        self.appointmentData= appointments.allAppointmentData(
        adate, workingdents)

        if self.appointmentData != ad:
            self.advise('appointment data modified on %s'%adate)
            return True
        else:
            self.advise('apointments on %s are unchanged'%adate)

    def calendar(self, sd):
        '''comes from click proceedures'''
        self.ui.main_tabWidget.setCurrentIndex(1)
        self.ui.appointmentCalendarWidget.setSelectedDate(sd)

    def aptFontSize(self, e):
        '''user selecting a different appointment book slot'''
        localsettings.appointmentFontSize=e
        for book in self.ui.apptBookWidgets:
            book.update()


    #--next five procs related to user clicking on the day
    #--buttons on the apptoverviewwidget
    def aptOVlabelClicked(self, sd):
        self.calendar(sd)

    def gotoToday(self):
        self.ui.appointmentCalendarWidget.setSelectedDate(
                                                    QtCore.QDate.currentDate())
    def gotoCurWeek(self):
        self.ui.apptOV_calendarWidget.setSelectedDate(
                                                    QtCore.QDate.currentDate())
    def aptOVviewMode(self, Viewmode=True):
        if Viewmode:
            self.ui.aptOVmode_label.setText("View Mode")
            self.ui.main_tabWidget.setCurrentIndex(0)
        else:
            self.ui.aptOVmode_label.setText("Scheduling Mode")
        for cb in (self.ui.aptOV_apptscheckBox, self.ui.aptOV_emergencycheckBox,
        self.ui.aptOV_lunchcheckBox):
            cb.setChecked(Viewmode)
    def aptOV_weekBack(self):
        date=self.ui.apptOV_calendarWidget.selectedDate()
        self.ui.apptOV_calendarWidget.setSelectedDate(date.addDays(-7))
    def aptOV_weekForward(self):
        date=self.ui.apptOV_calendarWidget.selectedDate()
        self.ui.apptOV_calendarWidget.setSelectedDate(date.addDays(7))
    def aptOV_monthBack(self):
        date=self.ui.apptOV_calendarWidget.selectedDate()
        self.ui.apptOV_calendarWidget.setSelectedDate(date.addMonths(-1))
    def aptOV_monthForward(self):
        date=self.ui.apptOV_calendarWidget.selectedDate()
        self.ui.apptOV_calendarWidget.setSelectedDate(date.addMonths(1))
    def apt_dayBack(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addDays(-1))
    def apt_dayForward(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addDays(1))
    def apt_weekBack(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addDays(-7))
    def apt_weekForward(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addDays(7))
    def apt_monthBack(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addMonths(-1))
    def apt_monthForward(self):
        date=self.ui.appointmentCalendarWidget.selectedDate()
        self.ui.appointmentCalendarWidget.setSelectedDate(date.addMonths(1))

    def clearTodaysEmergencyTime(self):
        '''clears emergency slots for today'''
        #-- raise a dialog to check
        result=QtGui.QMessageBox.question(self, "Confirm",
        "Clear today's emergency slots?",
        QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if result == QtGui.QMessageBox.Yes:
            self.advise("Cleared %d emergency slots"%
            appointments.clearEms(localsettings.sqlToday()), 1)

    def apptOVclinicians(self):
        '''everybody to be viewed'''
        value=self.ui.aptOV_everybody_checkBox.checkState()
        #--disconnect signal slots from the chechboxes temporarily
        self.connectAptOVdentcbs(False)
        #--change their values
        for dent in self.ui.aptOVdent_checkBoxes.keys():
            self.ui.aptOVdent_checkBoxes[dent].setCheckState(value)
        #--reconnect
        self.connectAptOVdentcbs()
        #--refresh Layout
        self.connectAptOVhygcbs(False)
        for dent in self.ui.aptOVhyg_checkBoxes.keys():
            self.ui.aptOVhyg_checkBoxes[dent].setCheckState(value)
        self.connectAptOVhygcbs()

        self.layout_apptOV()

    def apptOVhygs(self):
        '''called by checking the all hygenists checkbox on the apptov tab'''
        #-- coments as for above proc
        self.connectAptOVhygcbs(False)
        for dent in self.ui.aptOVhyg_checkBoxes.keys():
            self.ui.aptOVhyg_checkBoxes[dent].setCheckState(
            self.ui.aptOV_allhygscheckBox.checkState())
        self.connectAptOVhygcbs()
        self.layout_apptOV()

    def apptOVdents(self):
        '''called by checking the all dentists checkbox on the apptov tab'''

        #--disconnect signal slots from the chechboxes temporarily
        self.connectAptOVdentcbs(False)
        #--change their values
        for dent in self.ui.aptOVdent_checkBoxes.keys():
            self.ui.aptOVdent_checkBoxes[dent].setCheckState(
            self.ui.aptOV_alldentscheckBox.checkState())
        #--reconnect
        self.connectAptOVdentcbs()
        #--refresh Layout
        self.layout_apptOV()

    def findApptButtonClicked(self):
        selectedAppt=self.ui.ptAppointment_treeWidget.currentItem()
        ##TODO - whoops UK date format
        d=QtCore.QDate.fromString(selectedAppt.text(0), "dd'/'MM'/'yyyy")

        QtCore.QObject.disconnect(self.ui.main_tabWidget,
        QtCore.SIGNAL("currentChanged(int)"), self.handle_mainTab)

        self.ui.appointmentCalendarWidget.setSelectedDate(d)
        self.ui.main_tabWidget.setCurrentIndex(1)

        QtCore.QObject.connect(self.ui.main_tabWidget,
        QtCore.SIGNAL("currentChanged(int)"), self.handle_mainTab)


    def layout_apptOV(self):
        '''
        called by checking a dentist checkbox on apptov tab
        or by changeing the date on the appt OV calendar
        '''

        if self.ui.main_tabWidget.currentIndex() != 2:
            #--this is needed incase I programmatically
            #--change the checkboxes or diary date...
            #--I don't want a redraw every time
            return

        AllDentsChecked=True
        #--code to uncheck the all dentists checkbox if necessary
        for dent in self.ui.aptOVdent_checkBoxes.values():
            AllDentsChecked=AllDentsChecked and dent.checkState()

        if self.ui.aptOV_alldentscheckBox.checkState() != AllDentsChecked:
            QtCore.QObject.disconnect(self.ui.aptOV_alldentscheckBox,
            QtCore.SIGNAL("stateChanged(int)"), self.apptOVdents)

            self.ui.aptOV_alldentscheckBox.setChecked(AllDentsChecked)
            QtCore.QObject.connect(self.ui.aptOV_alldentscheckBox, QtCore.SIGNAL(
            "stateChanged(int)"), self.apptOVdents)

        AllHygsChecked=True
        #--same for the hygenists

        for hyg in self.ui.aptOVhyg_checkBoxes.values():
            AllHygsChecked=AllHygsChecked and hyg.checkState()
        if self.ui.aptOV_allhygscheckBox.checkState() != AllHygsChecked:
            QtCore.QObject.disconnect(self.ui.aptOV_allhygscheckBox,
            QtCore.SIGNAL("stateChanged(int)"), self.apptOVhygs)

            self.ui.aptOV_allhygscheckBox.setChecked(AllHygsChecked)
            QtCore.QObject.connect(self.ui.aptOV_allhygscheckBox, QtCore.SIGNAL(
            "stateChanged(int)"), self.apptOVhygs)

        if self.ui.aptOV_everybody_checkBox.checkState != (
        AllDentsChecked and AllHygsChecked):

            QtCore.QObject.disconnect(self.ui.aptOV_everybody_checkBox,
            QtCore.SIGNAL("stateChanged(int)"), self.apptOVclinicians)

            self.ui.aptOV_everybody_checkBox.setChecked(
            AllDentsChecked and AllHygsChecked)

            QtCore.QObject.connect(self.ui.aptOV_everybody_checkBox,
            QtCore.SIGNAL("stateChanged(int)"), self.apptOVclinicians)


        date=self.ui.apptOV_calendarWidget.selectedDate()
        dayno=date.dayOfWeek()
        weekdates=[]
        #--(monday to friday) #prevMonday=date.addDays(1-dayno),
        #--prevTuesday=date.addDays(2-dayno)
        for day in range(1, 6):
            weekday=(date.addDays(day-dayno))
            weekdates.append(weekday)
            self.ui.apptoverviewControls[day-1].setDate(weekday)

        if QtCore.QDate.currentDate() in weekdates:
            self.ui.apptOVtoday_pushButton.setEnabled(False)
        else:
            self.ui.apptOVtoday_pushButton.setEnabled(True)

        userCheckedDents=[]
        for dent in self.ui.aptOVdent_checkBoxes.keys():
            if self.ui.aptOVdent_checkBoxes[dent].checkState():
                userCheckedDents.append(dent)
        for dent in self.ui.aptOVhyg_checkBoxes.keys():
            if self.ui.aptOVhyg_checkBoxes[dent].checkState():
                userCheckedDents.append(dent)

        for ov in self.ui.apptoverviews:
            #--reset
            ov.date=weekdates[self.ui.apptoverviews.index(ov)]
            if userCheckedDents != []:
                workingdents=appointments.getWorkingDents(ov.date.toPyDate(),
                tuple(userCheckedDents))
                #--tuple like ((4, 840, 1900), (5, 830, 1400))

                dlist=[]
                for dent in workingdents:
                    dlist.append(dent[0])
                    ov.setStartTime(dent[0], dent[1])
                    ov.setEndTime(dent[0], dent[2])
                ov.dents=tuple(dlist)
            else:
                ov.dents=()
            ov.clear()

        if self.ui.aptOV_apptscheckBox.checkState():
            #--add appts
            for ov in self.ui.apptoverviews:
                for dent in ov.dents:
                    ov.appts[dent]=appointments.daysummary(ov.date.toPyDate(), dent)

        if self.ui.aptOV_emergencycheckBox.checkState():
            #--add emergencies
            for ov in self.ui.apptoverviews:
                for dent in ov.dents:
                    ov.eTimes[dent]=appointments.getBlocks(ov.date.toPyDate(), dent)

        if self.ui.aptOV_lunchcheckBox.checkState():
            #--add lunches
            ##todo - should really get these via mysql...
            #--but they never change in my practice...
            for ov in self.ui.apptoverviews[0:4]:
                ov.lunch=(1300, 60)
            self.ui.apptoverviews[4].lunch=(1230, 30)

        if str(self.ui.aptOVmode_label.text()) == "Scheduling Mode":
            #--user is scheduling an appointment so show 'slots'
            #--which match the apptointment being arranged
            self.offerAppt()
        for ov in self.ui.apptoverviews:
            #--repaint widgets
            ov.update()

    def layout_appointments(self):
        '''
        this populates the appointment book widgets (on maintab, pageindex 1)
        '''

        self.advise("Refreshing appointments")

        for book in self.ui.apptBookWidgets:
            book.clearAppts()
            book.setTime="None"

        d=self.ui.appointmentCalendarWidget.selectedDate()
        self.getappointmentData(d)
        todaysDents=[]
        todaysMemos=[]
        for dent in self.appointmentData[0]:
            todaysDents.append(dent[0])
            todaysMemos.append(dent[3])
        if d == (QtCore.QDate.currentDate()):
            self.ui.goTodayPushButton.setEnabled(False)
        else:
            self.ui.goTodayPushButton.setEnabled(True)
        i=0
        #-- clean past links to dentists
        for book in self.ui.apptBookWidgets:
            book.dentist=None
        for dent in todaysDents:
            try:
                self.ui.apptBookWidgets[i].dentist=\
                localsettings.apptix_reverse[dent]

                self.ui.apptBookWidgets[i].setStartTime(self.appointmentData[0][
                todaysDents.index(dent)][1])
                self.ui.apptBookWidgets[i].setEndTime(self.appointmentData[0][
                todaysDents.index(dent)][2])
            except IndexError, e:
                self.advise(
                "Damn! too many dentists today!! only 3 widgets available - "+
                "file a bug!<br /><br />%s"%str(e), 2)
                ####TODO - sort this out... no of widgets shouldn't be fixed.
            i+=1
        for label in (self.ui.apptFrameLabel1, self.ui.apptFrameLabel2,
        self.ui.apptFrameLabel3, self.ui.apptFrameLabel4):
            label.setText("")
        for label in (self.ui.book1memo_label, self.ui.book2memo_label,
        self.ui.book2memo_label, self.ui.book4memo_label):
            label.setText("")

        if i>0 :
            self.ui.apptFrameLabel1.setText(
                                localsettings.apptix_reverse[todaysDents[0]])
            self.ui.book1memo_label.setText(todaysMemos[0])
            if i>1 :
                self.ui.apptFrameLabel2.setText(
                                localsettings.apptix_reverse[todaysDents[1]])
                self.ui.book2memo_label.setText(todaysMemos[1])
            if i>2 :
                self.ui.apptFrameLabel3.setText(
                                localsettings.apptix_reverse[todaysDents[2]])
                self.ui.book3memo_label.setText(todaysMemos[2])
            if i>3 :
                self.ui.apptFrameLabel4.setText(
                                localsettings.apptix_reverse[todaysDents[3]])
                self.ui.book4memo_label.setText(todaysMemos[3])

            apps=self.appointmentData[1]
            for app in apps:
                dent=app[1]
                #--his will be a number
                book=self.ui.apptBookWidgets[todaysDents.index(dent)]

                book.setAppointment(str(app[2]), str(app[3]), app[4], app[5],
                app[6], app[7], app[8], app[9], app[10], chr(app[11]))
        else:
            self.advise("all off today")
        self.triangles()
        for book in self.ui.apptBookWidgets:
            book.update()
            if book.dentist == None:
                #--book has no data
                book.hide()
            else:
                book.show()

    def appointment_clicked(self, list_of_snos):
        if len(list_of_snos) == 1:

            sno=list_of_snos[0]
            self.advise("getting record %s"%sno)
            self.getrecord(sno)
        else:
            sno=self.final_choice(
                            search.getcandidates_from_serialnos(list_of_snos))
            if sno != None:
                self.getrecord(int(sno))
    def clearEmergencySlot(self, arg):
        '''
        this function is the slot for a signal invoked when the user clicks
        on a "blocked" slot.
        only question is... do they want to free it?
        it expects an arg like ('8:50', '11:00', 4)
        '''
        adate=self.ui.appointmentCalendarWidget.selectedDate().toPyDate()
        message="Do you want to unblock the selected slot?<br />"
        message+="%s - %s <br />"%(arg[0], arg[1])
        message+="%s<br />"%localsettings.longDate(adate)
        message+="with %s?"%localsettings.ops.get(arg[2])
        result=QtGui.QMessageBox.question(self, "Confirm",
        message,
        QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        if result == QtGui.QMessageBox.Yes:
            print "ok. unblocking"
            start=localsettings.humanTimetoWystime(arg[0])
            appointments.delete_appt_from_aslot(arg[2], start, adate, 0)
            self.layout_appointments()


    def blockEmptySlot(self, tup):
        print "block ", tup
        adate=self.ui.appointmentCalendarWidget.selectedDate().toPyDate()
        start=localsettings.humanTimetoWystime(tup[0])
        end=localsettings.humanTimetoWystime(tup[1])
        dent=tup[2]
        reason=tup[3]
        appointments.block_appt(adate, dent, start, end, reason)
        self.layout_appointments()

    def aptOVlabelRightClicked(self, d):
        '''
        user wants to change appointment overview properties for date d
        '''
        if permissions.granted(self):
            Dialog=QtGui.QDialog(self)
            dl=alterAday.alterDay(Dialog)
            dl.setDate(d)

            if dl.getInput():
                self.layout_apptOV()

    def appointmentTools(self):
        '''
        called from the main menu
        this just invokes a dialog which has a choice of options
        '''
        if permissions.granted(self):
            self.appointmentToolsWindow = QtGui.QMainWindow()
            self.ui2 = apptTools.apptTools(self.appointmentToolsWindow)
            self.appointmentToolsWindow.show()


class signals():
    def setupSignals(self):
        self.signals_miscbuttons()
        self.signals_admin()
        self.signals_reception()
        self.signals_printing()
        self.signals_menu()
        self.signals_estimates()
        self.signals_daybook()
        self.signals_accounts()
        self.signals_contract()
        self.signals_feesTable()
        self.signals_charts()
        self.signals_editPatient()
        self.signals_notesPage()
        self.signals_periochart()
        self.signals_tabs()
        self.signals_appointmentTab()
        self.signals_appointmentOVTab()
        self.signals_forum()
        self.signals_history()

    def signals_miscbuttons(self):
        
        QtCore.QObject.connect(self.ui.charge_pushButton,
        QtCore.SIGNAL("clicked()"), self.charge_pushButtonClicked)
        
        
        QtCore.QObject.connect(self.ui.saveButton,
                        QtCore.SIGNAL("clicked()"), self.okToLeaveRecord)
        
        QtCore.QObject.connect(self.ui.exampushButton,
        QtCore.SIGNAL("clicked()"), self.showExamDialog)
        QtCore.QObject.connect(self.ui.examTxpushButton,
        QtCore.SIGNAL("clicked()"), self.showExamDialog)

        QtCore.QObject.connect(self.ui.hygWizard_pushButton,
                        QtCore.SIGNAL("clicked()"), self.showHygDialog)
        QtCore.QObject.connect(self.ui.newBPE_pushButton,
                        QtCore.SIGNAL("clicked()"), self.newBPE_Dialog)
        QtCore.QObject.connect(self.ui.medNotes_pushButton,
                        QtCore.SIGNAL("clicked()"), self.showMedNotes)
        QtCore.QObject.connect(self.ui.phraseBook_pushButton,
                        QtCore.SIGNAL("clicked()"), self.phraseBookDialog)
        QtCore.QObject.connect(self.ui.memos_pushButton,
                        QtCore.SIGNAL("clicked()"), self.newCustomMemo)

    def signals_admin(self):
        #admin page
        QtCore.QObject.connect(self.ui.home_pushButton,
                        QtCore.SIGNAL("clicked()"), self.home)
        QtCore.QObject.connect(self.ui.newPatientPushButton,
                        QtCore.SIGNAL("clicked()"), self.enterNewPatient)
        QtCore.QObject.connect(self.ui.findButton,
                        QtCore.SIGNAL("clicked()"), self.find_patient)
        QtCore.QObject.connect(self.ui.reloadButton,
                        QtCore.SIGNAL("clicked()"), self.reload_patient)
        QtCore.QObject.connect(self.ui.backButton,
                        QtCore.SIGNAL("clicked()"), self.last_patient)
        QtCore.QObject.connect(self.ui.nextButton,
                        QtCore.SIGNAL("clicked()"), self.next_patient)
        QtCore.QObject.connect(self.ui.relatedpts_pushButton,
                        QtCore.SIGNAL("clicked()"), self.find_related)
        QtCore.QObject.connect(self.ui.daylistBox,
                    QtCore.SIGNAL("currentIndexChanged(int)"),self.todays_pts)
        QtCore.QObject.connect(self.ui.ptAppointment_treeWidget,
                QtCore.SIGNAL("itemSelectionChanged()"), self.ptApptTableNav)
        QtCore.QObject.connect(self.ui.printAccount_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printaccount)
        QtCore.QObject.connect(self.ui.printEst_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printEstimate)
        QtCore.QObject.connect(self.ui.printRecall_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printrecall)
        QtCore.QObject.connect(self.ui.takePayment_pushButton,
        QtCore.SIGNAL("clicked()"), self.takePayment_pushButton_clicked)
    def signals_reception(self):
        #admin summary widgets
        QtCore.QObject.connect(self.ui.newAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.newAppt)
        QtCore.QObject.connect(self.ui.makeAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.makeApptButtonClicked)
        QtCore.QObject.connect(self.ui.clearAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.clearApptButtonClicked)
        QtCore.QObject.connect(self.ui.modifyAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.modifyAppt)
        QtCore.QObject.connect(self.ui.findAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.findApptButtonClicked)
        QtCore.QObject.connect(self.ui.printAppt_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printApptCard)
        QtCore.QObject.connect(self.ui.printGP17_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printGP17)
    def signals_printing(self):
        #printing buttons
        QtCore.QObject.connect(self.ui.receiptPrintButton,
        QtCore.SIGNAL("clicked()"), self.printDupReceipt)
        
        QtCore.QObject.connect(self.ui.exportChartPrintButton,
        QtCore.SIGNAL("clicked()"), self.printChart)

        QtCore.QObject.connect(self.ui.simpleNotesPrintButton,
        QtCore.SIGNAL("clicked()"), self.printNotes)

        QtCore.QObject.connect(self.ui.detailedNotesPrintButton,
        QtCore.SIGNAL("clicked()"), self.printNotesV)

        QtCore.QObject.connect(self.ui.referralLettersPrintButton,
        QtCore.SIGNAL("clicked()"), self.printReferral)

        QtCore.QObject.connect(self.ui.standardLetterPushButton,
        QtCore.SIGNAL("clicked()"), self.printLetter)

        QtCore.QObject.connect(self.ui.recallpushButton,
        QtCore.SIGNAL("clicked()"), self.exportRecalls)

        QtCore.QObject.connect(self.ui.account2_pushButton,
        QtCore.SIGNAL("clicked()"), self.accountButton2Clicked)

        QtCore.QObject.connect(self.ui.previousCorrespondence_treeWidget,
        QtCore.SIGNAL("itemDoubleClicked (QTreeWidgetItem *,int)"), 
        self.showDoc)

        QtCore.QObject.connect(self.ui.recall_dateEdit,
        QtCore.SIGNAL("dateChanged (const QDate&)"), self.recallDate)
        
        
    def signals_menu(self):
        #menu
        QtCore.QObject.connect(self.ui.action_save_patient,
                        QtCore.SIGNAL("triggered()"), self.save_patient_tofile)
        QtCore.QObject.connect(self.ui.action_Open_Patient,
                    QtCore.SIGNAL("triggered()"), self.open_patient_fromfile)
        QtCore.QObject.connect(self.ui.actionSet_Clinician,
                    QtCore.SIGNAL("triggered()"), self.setClinician)
        QtCore.QObject.connect(self.ui.actionChoose_Database,
                               QtCore.SIGNAL("triggered()"), self.changeDB)
        QtCore.QObject.connect(self.ui.action_About,
                               QtCore.SIGNAL("triggered()"), self.aboutOM)
        QtCore.QObject.connect(self.ui.action_About_QT,
            QtCore.SIGNAL("triggered()"), QtGui.qApp, QtCore.SLOT("aboutQt()"))
        QtCore.QObject.connect(self.ui.action_Quit,
                               QtCore.SIGNAL("triggered()"), self.quit)
        QtCore.QObject.connect(self.ui.actionTable_View_For_Charting,
                        QtCore.SIGNAL("triggered()"), self.showChartTable)
        QtCore.QObject.connect(self.ui.actionClear_Today_s_Emergency_Slots,
                    QtCore.SIGNAL("triggered()"), self.clearTodaysEmergencyTime)
        QtCore.QObject.connect(self.ui.actionTest_Print_an_NHS_Form,
                               QtCore.SIGNAL("triggered()"), self.testGP17)
        QtCore.QObject.connect(self.ui.actionOptions,
                        QtCore.SIGNAL("triggered()"), self.userOptionsDialog)
        QtCore.QObject.connect(self.ui.actionLog_queries_in_underlying_terminal,
                    QtCore.SIGNAL("triggered()"), localsettings.setlogqueries)
        QtCore.QObject.connect(self.ui.actionAppointment_Tools,
                    QtCore.SIGNAL("triggered()"), self.appointmentTools)

    def signals_estimates(self):

        #Estimates and course ManageMent
        QtCore.QObject.connect(self.ui.newCourse_pushButton,
        QtCore.SIGNAL("clicked()"), self.newCourse_pushButton_clicked)
        QtCore.QObject.connect(self.ui.closeTx_pushButton,
        QtCore.SIGNAL("clicked()"), self.closeTx_pushButton_clicked)
        QtCore.QObject.connect(self.ui.estLetter_pushButton,
                        QtCore.SIGNAL("clicked()"), self.customEstimate)
        QtCore.QObject.connect(self.ui.recalcEst_pushButton,
                        QtCore.SIGNAL("clicked()"), self.recalculateEstimate)
        QtCore.QObject.connect(self.ui.xrayTxpushButton,
                               QtCore.SIGNAL("clicked()"), self.addXrayItems)
        QtCore.QObject.connect(self.ui.perioTxpushButton,
                               QtCore.SIGNAL("clicked()"), self.addPerioItems)
        QtCore.QObject.connect(self.ui.otherTxpushButton,
                               QtCore.SIGNAL("clicked()"), self.addOtherItems)
        QtCore.QObject.connect(self.ui.customTx_pushButton,
                               QtCore.SIGNAL("clicked()"), self.addCustomItem)

        QtCore.QObject.connect(self.ui.estWidget,
        QtCore.SIGNAL("applyFeeNow"), self.estWidget_applyFeeNowCalled)
        QtCore.QObject.connect(self.ui.estWidget,
        QtCore.SIGNAL("completedItem"), self.estwidget_completeItem)
        QtCore.QObject.connect(self.ui.estWidget,
        QtCore.SIGNAL("unCompletedItem"), self.estwidget_unCompleteItem)
        QtCore.QObject.connect(self.ui.estWidget,
        QtCore.SIGNAL("deleteItem"), self.estwidget_deleteTxItem)

        QtCore.QObject.connect(self.ui.plan_treeWidget, QtCore.SIGNAL(
        "itemDoubleClicked (QTreeWidgetItem *,int)"), self.planItemClicked)
        QtCore.QObject.connect(self.ui.comp_treeWidget, QtCore.SIGNAL(
        "itemDoubleClicked (QTreeWidgetItem *,int)"), self.cmpItemClicked)

    def signals_forum(self):
        QtCore.QObject.connect(self.ui.forum_treeWidget, QtCore.SIGNAL(
        "itemSelectionChanged ()"), self.forum_treeWidget_selectionChanged)
        QtCore.QObject.connect(self.ui.forumDelete_pushButton, QtCore.SIGNAL(
        "clicked()"), self.forumDeleteItem_clicked)
        QtCore.QObject.connect(self.ui.forumReply_pushButton, QtCore.SIGNAL(
        "clicked()"), self.forumReply_clicked)
        QtCore.QObject.connect(self.ui.forumNewTopic_pushButton, QtCore.SIGNAL(
        "clicked()"), self.forumNewTopic_clicked)

    def signals_history(self):
        QtCore.QObject.connect(self.ui.historyPrint_pushButton, QtCore.SIGNAL(
        "clicked()"), self.historyPrint)

    def signals_daybook(self):

        #daybook - cashbook
        QtCore.QObject.connect(self.ui.daybookGoPushButton,
                               QtCore.SIGNAL("clicked()"), self.daybookTab)
        QtCore.QObject.connect(self.ui.cashbookGoPushButton,
                               QtCore.SIGNAL("clicked()"), self.cashbookTab)
        QtCore.QObject.connect(self.ui.daybookEndDateEdit, QtCore.SIGNAL(
        "dateChanged ( const QDate & )"), self.datemanage)
        QtCore.QObject.connect(self.ui.daybookStartDateEdit, QtCore.SIGNAL(
        "dateChanged ( const QDate & )"), self.datemanage)
        QtCore.QObject.connect(self.ui.cashbookEndDateEdit, QtCore.SIGNAL(
        "dateChanged ( const QDate & )"), self.datemanage)
        QtCore.QObject.connect(self.ui.cashbookStartDateEdit, QtCore.SIGNAL(
        "dateChanged ( const QDate & )"), self.datemanage)
        QtCore.QObject.connect(self.ui.cashbookPrintButton, QtCore.SIGNAL(
        "clicked()"), self.cashbookPrint)
        QtCore.QObject.connect(self.ui.daybookPrintButton, QtCore.SIGNAL(
        "clicked()"), self.daybookPrint)
    def signals_accounts(self):
        #accounts
        QtCore.QObject.connect(self.ui.loadAccountsTable_pushButton,
        QtCore.SIGNAL("clicked()"), self.loadAccountsTable_clicked)
        QtCore.QObject.connect(self.ui.printSelectedAccounts_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printSelectedAccounts)
        QtCore.QObject.connect(self.ui.printAccountsTable_pushButton,
                        QtCore.SIGNAL("clicked()"), self.printAccountsTable)

        QtCore.QObject.connect(self.ui.accounts_tableWidget,
        QtCore.SIGNAL("cellDoubleClicked (int,int)"), self.accountsTableClicked)

    def signals_contract(self):
        #contract
        QtCore.QObject.connect(self.ui.badDebt_pushButton,
        QtCore.SIGNAL("clicked()"), self.makeBadDebt_clicked)
        QtCore.QObject.connect(self.ui.contract_tabWidget,
        QtCore.SIGNAL("currentChanged(int)"), self.contractTab_navigated)

        QtCore.QObject.connect(self.ui.dnt1comboBox, QtCore.
        SIGNAL("activated(const QString&)"), self.dnt1comboBox_clicked)
        
        QtCore.QObject.connect(self.ui.dnt2comboBox, QtCore.
        SIGNAL("activated(const QString&)"), self.dnt2comboBox_clicked)
        
        QtCore.QObject.connect(self.ui.cseType_comboBox,
        QtCore.SIGNAL("activated(const QString&)"), 
        self.cseType_comboBox_clicked)
        
        QtCore.QObject.connect(self.ui.editNHS_pushButton,
        QtCore.SIGNAL("clicked()"), self.editNHS_pushButton_clicked)
        
        QtCore.QObject.connect(self.ui.editPriv_pushButton,
        QtCore.SIGNAL("clicked()"), self.editPriv_pushButton_clicked)

        QtCore.QObject.connect(self.ui.nhsclaims_pushButton,
        QtCore.SIGNAL("clicked()"), self.nhsclaims_pushButton_clicked)

        QtCore.QObject.connect(self.ui.editHDP_pushButton,
        QtCore.SIGNAL("clicked()"), self.editHDP_pushButton_clicked)

        QtCore.QObject.connect(self.ui.editRegDent_pushButton,
        QtCore.SIGNAL("clicked()"), self.editRegDent_pushButton_clicked)


    def signals_feesTable(self):

        #feesTable
        ##TODO bring this functionality back
        #QtCore.QObject.connect(self.ui.printFeescale_pushButton,
        #QtCore.SIGNAL("clicked()"), self.printFeesTable)
        QtCore.QObject.connect(self.ui.chooseFeescale_comboBox,
        QtCore.SIGNAL("currentIndexChanged(int)"), 
        self.chooseFeescale_comboBox_changed)

        QtCore.QObject.connect(self.ui.feeItems_comboBox,
        QtCore.SIGNAL("currentIndexChanged(int)"), 
        self.feeItems_comboBox_changed)

        QtCore.QObject.connect(self.ui.feesColumn_comboBox,
        QtCore.SIGNAL("currentIndexChanged(int)"), 
        self.feesColumn_comboBox_changed)

        QtCore.QObject.connect(self.ui.feeExpand_radioButton,
        QtCore.SIGNAL("clicked()"), self.feeExpand_radiobuttons_clicked)
                        
        QtCore.QObject.connect(self.ui.feeCompress_radioButton,
        QtCore.SIGNAL("clicked()"), self.feeExpand_radiobuttons_clicked)
        
        QtCore.QObject.connect(self.ui.nhsRegs_pushButton,
        QtCore.SIGNAL("clicked()"), self.nhsRegs_pushButton_clicked)
        QtCore.QObject.connect(self.ui.feeSearch_lineEdit,
        QtCore.SIGNAL("editingFinished ()"), self.feeSearch_lineEdit_edited)
        QtCore.QObject.connect(self.ui.feeSearch_pushButton,
        QtCore.SIGNAL("clicked()"), self.feeSearch_pushButton_clicked)

    def signals_charts(self):


        #charts (including underlying table)
        QtCore.QObject.connect(self.ui.chartsview_pushButton,
                            QtCore.SIGNAL("clicked()"), self.showChartCharts)
        QtCore.QObject.connect(self.ui.summaryChartWidget,
                               QtCore.SIGNAL("showHistory"), self.toothHistory)
        QtCore.QObject.connect(self.ui.staticChartWidget,
                               QtCore.SIGNAL("showHistory"), self.toothHistory)
        QtCore.QObject.connect(self.ui.staticChartWidget,
                    QtCore.SIGNAL("toothSelected"), self.static_chartNavigation)
        QtCore.QObject.connect(self.ui.planChartWidget,
                    QtCore.SIGNAL("toothSelected"), self.plan_chartNavigation)
        QtCore.QObject.connect(self.ui.completedChartWidget,
                    QtCore.SIGNAL("toothSelected"), self.comp_chartNavigation)

        QtCore.QObject.connect(self.ui.planChartWidget,
        QtCore.SIGNAL("completeTreatment"), self.planChartWidget_completed)
        
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                               QtCore.SIGNAL("NextTooth"), self.navigateCharts)
        #--fillings have changed!!
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                        QtCore.SIGNAL("Changed_Properties"), self.updateCharts)
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                        QtCore.SIGNAL("DeletedComments"), self.deleteComments)

        QtCore.QObject.connect(self.ui.toothPropsWidget,
                               QtCore.SIGNAL("static"), self.editStatic)
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                               QtCore.SIGNAL("plan"), self.editPlan)
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                               QtCore.SIGNAL("completed"), self.editCompleted)
        QtCore.QObject.connect(self.ui.toothPropsWidget,
                        QtCore.SIGNAL("FlipDeciduousState"), self.flipDeciduous)
    def signals_editPatient(self):
        #edit page
        QtCore.QObject.connect(self.ui.editMore_pushButton,
                        QtCore.SIGNAL("clicked()"), self.showAdditionalFields)
        QtCore.QObject.connect(self.ui.defaultNP_pushButton,
                               QtCore.SIGNAL("clicked()"), self.defaultNP)
    def signals_notesPage(self):
        #notes page
        QtCore.QObject.connect(self.ui.notesMaximumVerbosity_radioButton,
                               QtCore.SIGNAL("clicked()"), self.updateNotesPage)
        QtCore.QObject.connect(self.ui.notesMinimumVerbosity_radioButton,
                               QtCore.SIGNAL("clicked()"), self.updateNotesPage)
        QtCore.QObject.connect(self.ui.notesMediumVerbosity_radioButton,
                               QtCore.SIGNAL("clicked()"), self.updateNotesPage)
    def signals_periochart(self):

        #periochart
        #### defunct  QtCore.QObject.connect(self.ui.perioChartWidget,
        ####QtCore.SIGNAL("toothSelected"), self.periocharts)

        QtCore.QObject.connect(self.ui.perioChartDateComboBox, QtCore.
                    SIGNAL("currentIndexChanged(int)"), self.layoutPerioCharts)
        QtCore.QObject.connect(self.ui.bpeDateComboBox, QtCore.SIGNAL
                               ("currentIndexChanged(int)"), self.bpe_table)
    def signals_tabs(self):
        #tab widget
        QtCore.QObject.connect(self.ui.main_tabWidget,
                QtCore.SIGNAL("currentChanged(int)"), self.handle_mainTab)
        QtCore.QObject.connect(self.ui.tabWidget,
                QtCore.SIGNAL("currentChanged(int)"), self.handle_patientTab)
    def signals_appointmentTab(self):
        #main appointment tab
        QtCore.QObject.connect(self.ui.appointmentCalendarWidget, QtCore.SIGNAL(
        "selectionChanged()"), self.layout_appointments)
        QtCore.QObject.connect(self.ui.goTodayPushButton,
                               QtCore.SIGNAL("clicked()"), self.gotoToday)
        QtCore.QObject.connect(self.ui.printBook1_pushButton,
                               QtCore.SIGNAL("clicked()"), self.book1print)
        QtCore.QObject.connect(self.ui.printBook2_pushButton,
                               QtCore.SIGNAL("clicked()"), self.book2print)
        QtCore.QObject.connect(self.ui.printBook3_pushButton,
                               QtCore.SIGNAL("clicked()"), self.book3print)
        QtCore.QObject.connect(self.ui.apptPrevDay_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_dayBack)
        QtCore.QObject.connect(self.ui.apptNextDay_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_dayForward)
        QtCore.QObject.connect(self.ui.apptPrevWeek_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_weekBack)
        QtCore.QObject.connect(self.ui.apptNextWeek_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_weekForward)
        QtCore.QObject.connect(self.ui.apptPrevMonth_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_monthBack)
        QtCore.QObject.connect(self.ui.apptNextMonth_pushButton,
                               QtCore.SIGNAL("clicked()"), self.apt_monthForward)
        QtCore.QObject.connect(self.ui.fontSize_spinBox,
                        QtCore.SIGNAL("valueChanged (int)"), self.aptFontSize)
        for book in self.ui.apptBookWidgets:
            book.connect(book, QtCore.SIGNAL("PySig"), self.appointment_clicked)
            book.connect(book, QtCore.SIGNAL("ClearEmergencySlot"),
                         self.clearEmergencySlot)
            book.connect(book, QtCore.SIGNAL("BlockEmptySlot"),
                         self.blockEmptySlot)
    def signals_appointmentOVTab(self):
        #appointment overview tab
        QtCore.QObject.connect(self.ui.apptOV_calendarWidget,
                    QtCore.SIGNAL("selectionChanged()"), self.layout_apptOV)
        QtCore.QObject.connect(self.ui.aptOVprevweek,
                               QtCore.SIGNAL("clicked()"), self.aptOV_weekBack)
        QtCore.QObject.connect(self.ui.aptOVnextweek,
                        QtCore.SIGNAL("clicked()"), self.aptOV_weekForward)
        QtCore.QObject.connect(self.ui.aptOVprevmonth,
                            QtCore.SIGNAL("clicked()"), self.aptOV_monthBack)
        QtCore.QObject.connect(self.ui.aptOVnextmonth,
                        QtCore.SIGNAL("clicked()"), self.aptOV_monthForward)
        QtCore.QObject.connect(self.ui.aptOV_apptscheckBox,
                        QtCore.SIGNAL("stateChanged(int)"), self.layout_apptOV)
        QtCore.QObject.connect(self.ui.aptOV_emergencycheckBox,
                        QtCore.SIGNAL("stateChanged(int)"), self.layout_apptOV)
        QtCore.QObject.connect(self.ui.aptOV_lunchcheckBox,
                    QtCore.SIGNAL("stateChanged(int)"), self.layout_apptOV)
        QtCore.QObject.connect(self.ui.aptOV_everybody_checkBox,
            QtCore.SIGNAL("stateChanged(int)"), self.apptOVclinicians)
        QtCore.QObject.connect(self.ui.aptOV_alldentscheckBox,
                        QtCore.SIGNAL("stateChanged(int)"), self.apptOVdents)
        QtCore.QObject.connect(self.ui.aptOV_allhygscheckBox,
                        QtCore.SIGNAL("stateChanged(int)"), self.apptOVhygs)
        QtCore.QObject.connect(self.ui.apptOVtoday_pushButton,
                               QtCore.SIGNAL("clicked()"), self.gotoCurWeek)

        for widg in self.ui.apptoverviews:
            widg.connect(widg, QtCore.SIGNAL("PySig"), self.makeAppt)
            widg.connect(widg, QtCore.SIGNAL("DentistHeading"),
                         self.apptOVheaderclick)

        self.connectAptOVdentcbs()
        self.connectAptOVhygcbs()

        for i in range(5):
            self.connect(self.ui.apptoverviewControls[i],
            QtCore.SIGNAL("clicked"), self.aptOVlabelClicked)

            self.connect(self.ui.apptoverviewControls[i],
            QtCore.SIGNAL("right-clicked"), self.aptOVlabelRightClicked)


        #appointment manage
        QtCore.QObject.connect(self.ui.printDaylists_pushButton,
                            QtCore.SIGNAL("clicked()"), self.daylistPrintWizard)


    def connectAptOVdentcbs(self, con=True):
        for cb in self.ui.aptOVdent_checkBoxes.values():
            #--aptOVdent_checkBoxes is a dictionary of
            #-- (keys=dents,values=checkboxes)
            if con:
                QtCore.QObject.connect(cb, QtCore.SIGNAL("stateChanged(int)"),
                                                            self.layout_apptOV)
            else:
                QtCore.QObject.disconnect(cb, QtCore.SIGNAL("stateChanged(int)"),
                                                            self.layout_apptOV)
    def connectAptOVhygcbs(self, con=True):
        for cb in self.ui.aptOVhyg_checkBoxes.values():
            #--aptOVhyg_checkBoxes is a dictionary of
            #--(keys=dents,values=checkboxes)
            if con:
                QtCore.QObject.connect(cb, QtCore.SIGNAL("stateChanged(int)"),
                                                        self.layout_apptOV)
            else:
                QtCore.QObject.disconnect(cb, QtCore.SIGNAL("stateChanged(int)"),
                                                            self.layout_apptOV)

class customWidgets():
    def addCustomWidgets(self):
        print "adding custom widgets"
        ##statusbar

        if localsettings.clinicianNo == 0:
            if localsettings.station == "surgery":
                op_text = " <b>NO CLINICIAN SET</b> - "
            else:
                op_text = ""
        else:
            op_text = " <b>CLINICIAN (%s)</b> - "%localsettings.clinicianInits
        if "/" in localsettings.operator:
            op_text += " team "
        op_text += " %s using %s mode. "%(localsettings.operator,
        localsettings.station)

        self.ui.operatorLabel = QtGui.QLabel()
        self.ui.operatorLabel.setText(op_text)
        self.ui.statusbar.addPermanentWidget(self.ui.operatorLabel)

        ##summary chart
        self.ui.summaryChartWidget=chartwidget.chartWidget()
        self.ui.summaryChartWidget.setShowSelected(False)
        hlayout=QtGui.QHBoxLayout(self.ui.staticSummaryPanel)
        hlayout.addWidget(self.ui.summaryChartWidget)
        ##perio chart
        self.ui.perioChartWidget=chartwidget.chartWidget()
        hlayout=QtGui.QHBoxLayout(self.ui.perioChart_frame)
        hlayout.addWidget(self.ui.perioChartWidget)

        ##static
        self.ui.staticChartWidget=chartwidget.chartWidget()
        hlayout=QtGui.QHBoxLayout(self.ui.static_groupBox)
        hlayout.addWidget(self.ui.staticChartWidget)
        ##plan
        self.ui.planChartWidget=chartwidget.chartWidget()
        self.ui.planChartWidget.isStaticChart=False
        self.ui.planChartWidget.isPlanChart=True
        hlayout=QtGui.QHBoxLayout(self.ui.plan_groupBox)
        hlayout.addWidget(self.ui.planChartWidget)
        ##completed
        self.ui.completedChartWidget=chartwidget.chartWidget()
        self.ui.completedChartWidget.isStaticChart=False
        hlayout=QtGui.QHBoxLayout(self.ui.completed_groupBox)
        hlayout.addWidget(self.ui.completedChartWidget)

        ##TOOTHPROPS
        self.ui.toothPropsWidget=toothProps.tpWidget()
        hlayout=QtGui.QHBoxLayout(self.ui.toothProps_frame)
        hlayout.setMargin(0)
        hlayout.addWidget(self.ui.toothPropsWidget)
        ##PERIOPROPS
        self.ui.perioToothPropsWidget=perioToothProps.tpWidget()
        hlayout=QtGui.QHBoxLayout(self.ui.perioToothProps_frame)
        hlayout.addWidget(self.ui.perioToothPropsWidget)

        self.ui.perioChartWidgets=[]
        self.ui.perioGroupBoxes=[]
        hlayout=QtGui.QVBoxLayout(self.ui.perioChartData_frame)
        hlayout.setMargin(2)
        for i in range(8):
            gbtitle=("Recession", "Pocketing", "Plaque", "Bleeding", "Other",
            "Suppuration", "Furcation", "Mobility")[i]
            periogb=QtGui.QGroupBox(gbtitle)
            periogb.setCheckable(True)
            periogb.setChecked(True)
            #periogb.setMinimumSize(0, 120)
            pchart=perioChartWidget.chartWidget()
            pchart.type=gbtitle
            gblayout=QtGui.QVBoxLayout(periogb)
            gblayout.setMargin(2)
            gblayout.addWidget(pchart)
            hlayout.addWidget(periogb)

            #make these widgets accessible
            self.ui.perioGroupBoxes.append(periogb)
            self.ui.perioChartWidgets.append(pchart)
        ##############################add more here!!!!#####
        ##appt books
        self.ui.apptBookWidgets=[]
        self.ui.apptBookWidgets.append(appointmentwidget.
                                       appointmentWidget("0800", "1900", 5, 3))
        self.ui.appt1scrollArea.setWidget(self.ui.apptBookWidgets[0])
        self.ui.apptBookWidgets.append(appointmentwidget.
                                       appointmentWidget("0800", "1900", 5, 3))
        self.ui.appt2scrollArea.setWidget(self.ui.apptBookWidgets[1])
        self.ui.apptBookWidgets.append(appointmentwidget.
                                       appointmentWidget("0800", "1900", 5, 3))
        self.ui.appt3scrollArea.setWidget(self.ui.apptBookWidgets[2])

        self.ui.apptBookWidgets.append(appointmentwidget.
                                       appointmentWidget("0800", "1900", 5, 3))
        self.ui.appt4scrollArea.setWidget(self.ui.apptBookWidgets[3])

        ##aptOV
        self.ui.apptoverviews=[]

        for day in range(5):
            if day == 4: #friday
                self.ui.apptoverviews.append(appointment_overviewwidget.
                            appointmentOverviewWidget(day, "0800", "1900", 15, 2))
            elif day == 1: #Tuesday:
                self.ui.apptoverviews.append(appointment_overviewwidget.
                            appointmentOverviewWidget(day, "0800", "1900", 15, 2))
            else:
                self.ui.apptoverviews.append(appointment_overviewwidget.\
                appointmentOverviewWidget(day, "0800", "1900", 15, 2))

        hlayout=QtGui.QHBoxLayout(self.ui.appt_OV_Frame1)
        hlayout.setMargin(2)
        hlayout.addWidget(self.ui.apptoverviews[0])
        hlayout=QtGui.QHBoxLayout(self.ui.appt_OV_Frame2)
        hlayout.setMargin(2)
        hlayout.addWidget(self.ui.apptoverviews[1])
        hlayout=QtGui.QHBoxLayout(self.ui.appt_OV_Frame3)
        hlayout.setMargin(2)
        hlayout.addWidget(self.ui.apptoverviews[2])
        hlayout=QtGui.QHBoxLayout(self.ui.appt_OV_Frame4)
        hlayout.setMargin(2)
        hlayout.addWidget(self.ui.apptoverviews[3])
        hlayout=QtGui.QHBoxLayout(self.ui.appt_OV_Frame5)
        hlayout.setMargin(2)
        hlayout.addWidget(self.ui.apptoverviews[4])

        self.ui.apptoverviewControls=[]

        for widg in (self.ui.day1_frame, self.ui.day2_frame,
        self.ui.day3_frame, self.ui.day4_frame, self.ui.day5_frame):
            hlayout=QtGui.QHBoxLayout(widg)
            hlayout.setMargin(0)
            control=aptOVcontrol.control()
            self.ui.apptoverviewControls.append(control)
            hlayout.addWidget(control)

        self.ui.aptOVdent_checkBoxes={}
        self.ui.aptOVhyg_checkBoxes={}

        #vlayout=QtGui.QVBoxLayout(self.ui.aptOVdents_frame)
        glayout = QtGui.QGridLayout(self.ui.aptOVdents_frame)
        glayout.setSpacing(0)
        self.ui.aptOV_everybody_checkBox = QtGui.QCheckBox(
                                            QtCore.QString("All Clinicians"))
        self.ui.aptOV_everybody_checkBox.setChecked(True)
        row=0
        glayout.addWidget(self.ui.aptOV_everybody_checkBox, row, 0, 1, 2)

        hl=QtGui.QFrame(self.ui.aptOVdents_frame)
        #--Draw a line here.... but room doesn;t permit
        hl.setFrameShape(QtGui.QFrame.HLine)
        hl.setFrameShadow(QtGui.QFrame.Sunken)
        row+=1
        glayout.addWidget(hl, row, 0, 1, 2)

        self.ui.aptOV_alldentscheckBox = QtGui.QCheckBox(
                                            QtCore.QString("All Dentists"))
        self.ui.aptOV_alldentscheckBox.setChecked(True)
        row+=1
        glayout.addWidget(self.ui.aptOV_alldentscheckBox, row, 0, 1, 2)
        for dent in localsettings.activedents:
            cb=QtGui.QCheckBox(QtCore.QString(dent))
            cb.setChecked(True)
            self.ui.aptOVdent_checkBoxes[localsettings.apptix[dent]]=cb
            row+=1
            glayout.addWidget(cb, row, 1, 1, 1)

        self.ui.aptOV_allhygscheckBox= QtGui.QCheckBox(
                                        QtCore.QString("All Hygenists"))
        self.ui.aptOV_allhygscheckBox.setChecked(True)
        row+=1
        glayout.addWidget(self.ui.aptOV_allhygscheckBox, row, 0, 1, 2)
        for hyg in localsettings.activehygs:
            cb=QtGui.QCheckBox(QtCore.QString(hyg))
            cb.setChecked(True)
            self.ui.aptOVhyg_checkBoxes[localsettings.apptix[hyg]]=cb
            row+=1
            glayout.addWidget(cb, row, 1, 1, 1)

        #--updates the current time in appointment books
        self.ui.referralLettersComboBox.clear()
        #--start a thread for the triangle on the appointment book
        self.thread1=threading.Thread(target=self.apptTicker)
        self.thread1.start()

        self.thread2=threading.Thread(target = self.checkForNewForumPosts)
        self.thread2.start()

        self.enableEdit(False)
        for desc in referral.getDescriptions():
            s=QtCore.QString(desc)
            self.ui.referralLettersComboBox.addItem(s)

        #-- add a header to the estimates page
        self.ui.estWidget=estimateWidget.estWidget()
        self.ui.estimate_scrollArea.setWidget(self.ui.estWidget)


        #--history
        self.addHistoryMenu()

class chartsClass():

    def navigateCharts(self, e):
        '''
        called by a keypress in the tooth prop LineEdit or a click on one of
        the tooth prop buttons.
        '''

        if self.selectedChartWidget == "cmp":
            widg=self.ui.completedChartWidget
            column=4
        elif self.selectedChartWidget == "pl":
            widg=self.ui.planChartWidget
            column=3
        else:
            widg=self.ui.staticChartWidget
            column=2
        [x, y]=widg.selected

        if y == 0:
            #--upper teeth
            if e == "up":
                if x != 0:
                    x -= 1
            else:
                if x == 15:
                    x, y=15, 1
                else:
                    x += 1
        else:
            #--lower teeth
            if e == "up":
                if x == 15:
                    x, y=15, 0
                else:
                    x += 1
            else:
                if x != 0:
                    x -= 1
        widg.setSelected(x, y)
    def chart_navigate(self):
        print "chart_navigate",
        '''this is called when the charts TABLE is navigated'''
        userPerformed=self.ui.chartsTableWidget.isVisible()
        if userPerformed:
            print "performed by user"
        else:
            print "performed programatically"
            row=self.ui.chartsTableWidget.currentRow()
            tString=str(self.ui.chartsTableWidget.item(row, 0).text().toAscii())
            self.chartNavigation(tString, userPerformed)

    def deleteComments(self):
        tooth=str(self.ui.chartsTableWidget.item(
                            self.ui.chartsTableWidget.currentRow(), 0).text())
        if tooth in self.ui.staticChartWidget.commentedTeeth:
            self.ui.staticChartWidget.commentedTeeth.remove(tooth)
            self.ui.staticChartWidget.update()

    def updateCharts(self, arg):
        '''called by a signal from the toothprops widget -
        args are the new tooth properties eg modbl,co'''
        print "update charts arg =", arg
        tooth=str(self.ui.chartsTableWidget.item(
                            self.ui.chartsTableWidget.currentRow(), 0).text())
        if self.selectedChartWidget == "st":
            self.pt.__dict__[tooth+self.selectedChartWidget]=arg
            #--update the patient!!
            self.ui.staticChartWidget.setToothProps(tooth, arg)
            self.ui.staticChartWidget.update()
        elif self.selectedChartWidget == "pl":
            if course_module.newCourseNeeded(self):
                return
            self.toothTreatAdd(tooth, arg)
        elif self.selectedChartWidget == "cmp":
            self.advise(
            "for the moment, please enter treatment into plan first, "+
            "then complete it.", 1)
        else:
            self.advise("unable to update chart - this shouldn't happen!!!", 2)
            #--should never happen

    def updateChartsAfterTreatment(self, tooth, newplan, newcompleted):
        self.ui.planChartWidget.setToothProps(tooth, newplan)
        self.ui.planChartWidget.update()
        self.ui.completedChartWidget.setToothProps(tooth, newcompleted)
        self.ui.completedChartWidget.update()


    def flipDeciduous(self):
        if self.selectedChartWidget == "st":
            selectedCells=self.ui.chartsTableWidget.selectedIndexes()
            for cell in selectedCells:  #=self.ui.chartsTableWidget.currentRow()
                row=cell.row()
                selectedTooth=str(
                            self.ui.chartsTableWidget.item(row, 0).text().toAscii())
                print "flipping tooth ", selectedTooth
                self.pt.flipDec_Perm(selectedTooth)
            for chart in (self.ui.staticChartWidget, self.ui.planChartWidget,
            self.ui.completedChartWidget, self.ui.perioChartWidget,
            self.ui.summaryChartWidget):
                chart.chartgrid=self.pt.chartgrid
                #--necessary to restore the chart to full dentition
                chart.update()
        else:
            self.advise(
            "you need to be in the static chart to change tooth state", 1)
    def static_chartNavigation(self, tstring):
        '''called by the static chartwidget'''
        self.selectedChartWidget="st"

        self.chartNavigation(tstring)
    def plan_chartNavigation(self, tstring):
        '''called by the plan chartwidget'''
        self.selectedChartWidget="pl"
        self.chartNavigation(tstring)
    def comp_chartNavigation(self, tstring):
        '''called by the completed chartwidget'''
        self.selectedChartWidget="cmp"
        self.chartNavigation(tstring)
    def editStatic(self):
        '''called by the static button on the toothprops widget'''
        self.selectedChartWidget="st"
        self.chart_navigate()
    def editPlan(self):
        '''called by the plan button on the toothprops widget'''
        self.selectedChartWidget="pl"
        self.chart_navigate()
    def editCompleted(self):
        '''called by the cmp button on the toothprops widget'''
        self.selectedChartWidget="cmp"
        self.chart_navigate()

    def chartNavigation(self, tstring, callerIsTable=False):
        '''
        one way or another, a tooth has been selected...
        this updates all relevant widgets
        '''
        #--called by a navigating a chart or the underlying table
        #--convert from QString
        tooth=str(tstring)

        grid = (["ur8", "ur7", "ur6", "ur5", 'ur4', 'ur3', 'ur2', 'ur1',
        'ul1', 'ul2', 'ul3', 'ul4', 'ul5', 'ul6', 'ul7', 'ul8'],
        ["lr8", "lr7", "lr6", "lr5", 'lr4', 'lr3', 'lr2', 'lr1',
        'll1', 'll2', 'll3', 'll4', 'll5', 'll6', 'll7', 'll8'])

        if tooth in grid[0]:
            y=0
        else:
            y=1
        if int(tooth[2])>3:
            self.ui.toothPropsWidget.tooth.setBacktooth(True)
        else:
            self.ui.toothPropsWidget.tooth.setBacktooth(False)
        if tooth[1] == "r":
            self.ui.toothPropsWidget.tooth.setRightSide(True)
        else:
            self.ui.toothPropsWidget.tooth.setRightSide(False)
        if tooth[0] == "u":
            self.ui.toothPropsWidget.tooth.setUpper(True)
        else:
            self.ui.toothPropsWidget.tooth.setUpper(False)
        self.ui.toothPropsWidget.tooth.clear()
        self.ui.toothPropsWidget.tooth.update()

        #--calculate x, y co-ordinates for the chartwisdgets
        x=grid[y].index(tooth)
        self.ui.toothPropsWidget.tooth_label.setText(
                                            self.pt.chartgrid[tooth].upper())
        #--ALLOWS for deciduos teeth

        if self.selectedChartWidget == "st":
            self.ui.toothPropsWidget.isStatic(True)
            self.ui.toothPropsWidget.setExistingProps(
                                                self.pt.__dict__[tooth+"st"])
            self.ui.staticChartWidget.selected=[x, y]
            self.ui.staticChartWidget.update()
            if self.ui.planChartWidget.selected != [-1, -1]:
                self.ui.planChartWidget.setSelected(-1, -1)
                self.ui.planChartWidget.update()
            if self.ui.completedChartWidget.selected != [-1, -1]:
                self.ui.completedChartWidget.setSelected(-1, -1)
                self.ui.completedChartWidget.update()
            column=2
        elif self.selectedChartWidget == "pl":
            self.ui.toothPropsWidget.isStatic(False)
            self.ui.toothPropsWidget.setExistingProps(
                                                self.pt.__dict__[tooth+"pl"])
            self.ui.planChartWidget.selected=[x, y]
            self.ui.planChartWidget.update()
            if self.ui.staticChartWidget.selected != [-1, -1]:
                self.ui.staticChartWidget.setSelected(-1, -1)
                self.ui.staticChartWidget.update()
            if self.ui.completedChartWidget.selected != [-1, -1]:
                self.ui.completedChartWidget.setSelected(-1, -1)
                self.ui.completedChartWidget.update()
            column=3
        elif self.selectedChartWidget == "cmp":
            self.ui.toothPropsWidget.isStatic(False)
            self.ui.toothPropsWidget.lineEdit.setText(
                                                self.pt.__dict__[tooth+"cmp"])
            self.ui.completedChartWidget.selected=[x, y]
            self.ui.completedChartWidget.update()
            if self.ui.staticChartWidget.selected != [-1, -1]:
                self.ui.staticChartWidget.setSelected(-1, -1)
                self.ui.staticChartWidget.update()
            if self.ui.planChartWidget.selected != [-1, -1]:
                self.ui.planChartWidget.setSelected(-1, -1)
                self.ui.planChartWidget.update()
            column=4

        else:
            #--shouldn't happen??
            self.advise ("ERROR IN chartNavigation- please report", 2)
            column=0
            #-- set this otherwise this variable will
            #-- create an error in 2 lines time!
        if not callerIsTable:
            #-- keep the table correct
            print "updating charts table"
            self.ui.chartsTableWidget.setCurrentCell(x+y*16, column)

    def bpe_dates(self):
        #--bpe = "basic periodontal exam"
        self.ui.bpeDateComboBox.clear()
        self.ui.bpe_textBrowser.setPlainText("")
        if self.pt.bpe == []:
            self.ui.bpeDateComboBox.addItem(QtCore.QString("NO BPE"))
        else:
            l=copy.deepcopy(self.pt.bpe)
            l.reverse() #show newest first
            for sets in l:
                self.ui.bpeDateComboBox.addItem(QtCore.QString((sets[0])))

    def bpe_table(self, arg):
        '''updates the BPE chart on the clinical summary page'''
        if self.pt.bpe != []:
            self.ui.bpe_groupBox.setTitle("BPE "+self.pt.bpe[-1][0])
            l=copy.deepcopy(self.pt.bpe)
            l.reverse()
            bpestring=l[arg][1]
            bpe_html='<table width="100%" border="1"><tr>'
            for i in range(len(bpestring)):
                if i == 3:
                    bpe_html+="</tr><tr>"
                bpe_html+='<td align="center">%s</td>'%bpestring[i]
            for i in range(i+1, 6):
                if i == 3:
                    bpe_html+="</tr><tr>"
                bpe_html+='<td align="center">_</td>'
            bpe_html+='</tr></table>'
            self.ui.bpe_textBrowser.setHtml(bpe_html)
        else:
            #--necessary in case of the "NO DATA FOUND" option
            self.ui.bpe_groupBox.setTitle("BPE")
            self.ui.bpe_textBrowser.setHtml("")

    def periochart_dates(self):
        '''
        multiple perio charts on multiple dates....
        display those dates in a combo box
        '''
        self.ui.perioChartDateComboBox.clear()
        for date in self.pt.perioData.keys():
            self.ui.perioChartDateComboBox.addItem(QtCore.QString(date))
        if self.pt.perioData == {}:
            self.ui.perioChartDateComboBox.addItem(QtCore.QString("NO CHARTS"))

    def layoutPerioCharts(self):
        '''layout the perio charts'''
        #--convert from QString
        selected_date=str(self.ui.perioChartDateComboBox.currentText())
        if self.pt.perioData.has_key(selected_date):
            perioD=self.pt.perioData[selected_date]
            #--headers=("Recession", "Pocketing", "Plaque", "Bleeding", "Other",
            #--"Suppuration", "Furcation", "Mobility")
            for key in perioD.keys():
                for i in range(8):
                    self.ui.perioChartWidgets[i].setProps(key, perioD[key][i])
        else:
            self.advise("no perio data found for", selected_date)
            for i in range(8):
                self.ui.perioChartWidgets[i].props={}
        for chart in self.ui.perioChartWidgets:
            chart.update()

    def chartsTable(self):
        self.advise("filling charts table")
        self.ui.chartsTableWidget.clear()
        self.ui.chartsTableWidget.setSortingEnabled(False)
        self.ui.chartsTableWidget.setRowCount(32)
        headers=["Tooth", "Deciduous", "Static", "Plan", "Completed"]
        self.ui.chartsTableWidget.setColumnCount(5)
        self.ui.chartsTableWidget.setHorizontalHeaderLabels(headers)
        w=self.ui.chartsTableWidget.width()-40
        #-- set column widths but allow for scrollbar
        self.ui.chartsTableWidget.setColumnWidth(0, .1*w)
        self.ui.chartsTableWidget.setColumnWidth(1, .1*w)
        self.ui.chartsTableWidget.setColumnWidth(2, .4*w)
        self.ui.chartsTableWidget.setColumnWidth(3, .2*w)
        self.ui.chartsTableWidget.setColumnWidth(4, .2*w)
        self.ui.chartsTableWidget.verticalHeader().hide()

        for chart in (self.ui.summaryChartWidget, self.ui.staticChartWidget,
        self.ui.planChartWidget, self.ui.completedChartWidget,
        self.ui.perioChartWidget):
            chart.chartgrid=self.pt.chartgrid
            #--sets the tooth numbering
        row=0

        for tooth in self.grid:
            item1=QtGui.QTableWidgetItem(tooth)
            #-- I use this a lot. Every class has a  hidden __dict__ attribute
            #-- to access attributes programatically self.pt.ur8st etc..
            static_text=self.pt.__dict__[tooth+"st"]
            staticitem=QtGui.QTableWidgetItem(static_text)
            decidousitem=QtGui.QTableWidgetItem(self.pt.chartgrid[tooth])
            self.ui.chartsTableWidget.setRowHeight(row, 15)
            self.ui.chartsTableWidget.setItem(row, 0, item1)
            self.ui.chartsTableWidget.setItem(row, 1, decidousitem)
            self.ui.chartsTableWidget.setItem(row, 2, staticitem)
            row+=1
            stl=static_text.lower()
            self.ui.summaryChartWidget.setToothProps(tooth, stl)
            self.ui.staticChartWidget.setToothProps(tooth, stl)
            pItem=self.pt.__dict__[tooth+"pl"]
            cItem=self.pt.__dict__[tooth+"cmp"]
            planitem=QtGui.QTableWidgetItem(pItem)
            cmpitem=QtGui.QTableWidgetItem(cItem)
            self.ui.chartsTableWidget.setItem(row, 3, planitem)
            self.ui.chartsTableWidget.setItem(row, 4, cmpitem)
            self.ui.planChartWidget.setToothProps(tooth, pItem.lower())
            self.ui.completedChartWidget.setToothProps(tooth, cItem.lower())

            if stl[:2] in ("at", "tm", "ue"):
                self.ui.perioChartWidget.setToothProps(tooth, stl)
            self.ui.chartsTableWidget.setCurrentCell(0, 0)

    def toothHistory(self, arg):
        '''show history of %s at position %s"%(arg[0], arg[1])'''
        th="<br />"
        for item in self.pt.dayBookHistory:
            if arg[0].upper() in item[2].strip():
                th+="%s - %s - %s<br />"%(
                item[0], localsettings.ops[int(item[1])], item[2].strip())
        if th == "<br />":
            th+="No History"
        th=th.rstrip("<br />")
        QtGui.QToolTip.showText(arg[1], arg[0]+th)


class cashbooks():
    def cashbookTab(self):
        dent1=self.ui.cashbookDentComboBox.currentText()
        d=self.ui.cashbookStartDateEdit.date()
        sdate="%s_%s_%s"%(d.year(), d.month(), d.day())
        d=self.ui.cashbookEndDateEdit.date()
        edate="%s_%s_%s"%(d.year(), d.month(), d.day())
        html=cashbook.details(dent1, sdate, edate)
        self.ui.cashbookTextBrowser.setHtml('<html><body>'
        +html+"</body></html>")

    def daybookTab(self):
        dent1=str(self.ui.daybookDent1ComboBox.currentText())
        dent2=str(self.ui.daybookDent2ComboBox.currentText())
        d=self.ui.daybookStartDateEdit.date()
        sdate="%s_%s_%s"%(d.year(), d.month(), d.day())
        d=self.ui.daybookEndDateEdit.date()
        edate="%s_%s_%s"%(d.year(), d.month(), d.day())
        html=daybook.details(dent1, dent2, sdate, edate)
        self.ui.daybookTextBrowser.setHtml('<html><body>'
        +html+"</body></html>")

    def historyPrint(self):
        html=self.ui.debugBrowser.toHtml()
        myclass=bookprint.printBook(html)
        myclass.printpage()

    def daybookPrint(self):
        dent1=str(self.ui.daybookDent1ComboBox.currentText())
        dent2=str(self.ui.daybookDent2ComboBox.currentText())
        d=self.ui.daybookStartDateEdit.date()
        sdate="%s_%s_%s"%(d.year(), d.month(), d.day())
        d=self.ui.daybookEndDateEdit.date()
        edate="%s_%s_%s"%(d.year(), d.month(), d.day())
        html=daybook.details(dent1, dent2, sdate, edate)
        myclass=bookprint.printBook('<html><body>'+html+\
        "</body></html>")
        myclass.printpage()

    def cashbookPrint(self):
        dent1=self.ui.cashbookDentComboBox.currentText()
        d=self.ui.cashbookStartDateEdit.date()
        sdate="%s_%s_%s"%(d.year(), d.month(), d.day())
        d=self.ui.cashbookEndDateEdit.date()
        edate="%s_%s_%s"%(d.year(), d.month(), d.day())
        html=cashbook.details(dent1, sdate, edate)
        myclass=bookprint.printBook('<html><body>'+html+\
        "</body></html>")
        myclass.printpage()

    def printSelectedAccounts(self):
        if self.ui.accounts_tableWidget.rowCount() == 0:
            self.advise("Please load the table first", 1)
            return
        firstPage=True
        no_printed=0
        for row in range(self.ui.accounts_tableWidget.rowCount()):
            for col in range(13, 16):
                item=self.ui.accounts_tableWidget.item(row, col)
                if item.checkState():
                    tone=("A", "B", "C")[col-13]
                    sno=int(self.ui.accounts_tableWidget.item(row, 1).text())
                    print "Account tone %s letter to %s"%(tone, sno)
                    printpt=patient_class.patient(sno)

                    doc=accountPrint.document(printpt.title,
                    printpt.fname, printpt.sname, (printpt.addr1,
                    printpt.addr2, printpt.addr3, printpt.town,
                    printpt.county), printpt.pcde,
                    localsettings.formatMoney(printpt.fees))
                    doc.setTone(tone)

                    if firstPage:
                        #--raise a print dialog for the first letter of the run
                        #--only
                        if not doc.dialogExec():
                            #-- user has abandoned the print run
                            return
                        chosenPrinter=doc.printer
                        chosenPageSize=doc.printer.pageSize()
                        firstPage=False
                    else:
                        doc.printer=chosenPrinter
                        doc.printer.setPageSize(chosenPageSize)
                    doc.requireDialog=False
                    if tone == "B":
                        doc.setPreviousCorrespondenceDate(printpt.billdate)
                    if doc.print_():
                        printpt.updateBilling(tone)
                        printpt.addHiddenNote(
                        "printed", "account - tone %s"%tone)

                        patient_write_changes.discreet_changes(printpt, (
                        "billct", "billdate", "billtype"))
                        patient_write_changes.toNotes(
                                                sno, printpt.HIDDENNOTES)
                        self.commitPDFtoDB("Account tone%s"%tone, printpt.serialno)
                        no_printed+=1
        self.advise("%d letters printed"%no_printed, 1)

    def datemanage(self):
        if self.ui.daybookStartDateEdit.date() > \
        self.ui.daybookEndDateEdit.date():
            self.ui.daybookStartDateEdit.setDate(self.\
                                                 ui.daybookEndDateEdit.date())

        if self.ui.cashbookStartDateEdit.date() > \
        self.ui.cashbookEndDateEdit.date():
            self.ui.cashbookStartDateEdit.setDate(self.\
                                                  ui.cashbookEndDateEdit.date())

class newPatientClass():
    def enterNewPatient(self):
        '''called by the user clicking the new patient button'''

        #--check for unsaved changes
        if not self.okToLeaveRecord():
            print "not entering new patient - still editing current record"
            return

        #--disable the newPatient Button
        #--THE STATE OF THIS BUTTON IS USED TO MONITOR USER ACTIONS
        #--DO NOT CHANGE THIS LINE
        self.ui.newPatientPushButton.setEnabled(False)

        #--disable the tabs which are normalyy enabled by default
        self.ui.tabWidget.setTabEnabled(4, False)
        self.ui.tabWidget.setTabEnabled(3, False)

        #--clear any current record
        self.clearRecord()

        #--disable the majority of widgets
        self.enableEdit(False)

        #--change the function of the save button
        QtCore.QObject.disconnect(self.ui.saveButton, QtCore.\
                                  SIGNAL("clicked()"), self.save_changes)
        QtCore.QObject.connect(self.ui.saveButton, QtCore.\
                               SIGNAL("clicked()"), self.checkNewPatient)
        self.ui.saveButton.setEnabled(True)
        self.ui.saveButton.setText("SAVE NEW PATIENT")

        #--move to the edit patient details page
        self.ui.tabWidget.setCurrentIndex(0)
        self.ui.patientEdit_groupBox.setTitle("Enter New Patient")

        #--set default sex ;)
        self.ui.sexEdit.setCurrentIndex(0)

        #--give some help
        self.ui.detailsBrowser.setHtml('<div align="center">'
        +'<h3>Enter New Patient</h3>Please enter at least the required fields, '
        +'then use the Save Changes button to commit '
        +'this patient to the database.</div>')

    def enteringNewPatient(self):
        '''determines if the patient is entering a new patient'''

        #--is user entering a new patient? the state of this button will tell
        if self.ui.newPatientPushButton.isEnabled():
            return False

        #--so they are.. do they wish to cancel the edit?'''
        else:
            #--ensure patient details tab is visible so user can
            #--see that they are entering a pt
            self.ui.main_tabWidget.setCurrentIndex(0)
            self.ui.tabWidget.setCurrentIndex(0)

            #--offer abort and return a result
            return not self.abortNewPatientEntry()

    def checkNewPatient(self):
        '''
        check to see what the user has entered for a new patient
        before commiting to database
        '''

        atts=[]
        allfields_entered=True

        #-- check these widgets for entered text.
        for widg in (self.ui.snameEdit, self.ui.titleEdit, self.ui.fnameEdit,
        self.ui.addr1Edit, self.ui.pcdeEdit):
            if len(widg.text()) == 0:
                allfields_entered=False

        if allfields_entered:
            #--update 'pt'
            self.apply_editpage_changes()

            if self.saveNewPatient():
                #--sucessful save
                self.ui.newPatientPushButton.setEnabled(True)
                #--reset the gui
                self.finishedNewPatientInput()
                #--reload the patient from the db.
                self.reload_patient()
            else:
                self.advise("Error saving new patient, sorry!", 2)
        else:
            #-- prompt user for more info
            self.advise("insufficient data to create a new record... "+
            "please fill in all highlighted fields", 2)

    def saveNewPatient(self):
        '''User has entered a new patient'''

        #--write to the database
        #--the next available serialno is returned or -1 if problems
        sno=writeNewPatient.commit(self.pt)
        if sno == -1:
            self.advise("Error saving patient", 2)
            return False
        else:
            #--set that serialno
            self.pt.serialno=sno
            #--messy, but avoids a "previous pt has changed"
            #--dialog when reloaded
            self.pt_dbstate=copy.deepcopy(self.pt)
            return True

    def finishedNewPatientInput(self):
        '''restore GUI to normal mode after a new patient has been entered'''
        #--remove my help prompt
        self.ui.detailsBrowser.setText("")
        #--reset the state of the newPatient button
        self.ui.newPatientPushButton.setEnabled(True)

        #--enable the default tabs, and go to the appropriate one
        self.ui.tabWidget.setTabEnabled(4, True)
        self.ui.tabWidget.setTabEnabled(3, True)
        self.gotoDefaultTab()

        #--disable the edit tab
        self.ui.tabWidget.setTabEnabled(0, False)

        #--restore default functionality to the save button
        QtCore.QObject.disconnect(self.ui.saveButton, QtCore.SIGNAL("clicked()"),
                                                        self.checkNewPatient)
        QtCore.QObject.connect(self.ui.saveButton, QtCore.SIGNAL("clicked()"),
                                                            self.save_changes)
        self.ui.saveButton.setText("SAVE CHANGES")

    def abortNewPatientEntry(self):
        '''get user response 'abort new patient entry?' '''

        #--let user see what they were up to
        self.ui.main_tabWidget.setCurrentIndex(0)

        #--ask the question (centred over self)
        result=QtGui.QMessageBox.question(self, "Confirm",
        "New Patient not saved. Abandon Changes?",
        QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        #--act on the answer
        if result == QtGui.QMessageBox.No:
            return False
        else:
            self.finishedNewPatientInput()
            return True

    def defaultNP(self):
        '''default NP has been pressed - so apply the address and surname
        from the previous patient'''

        dup_tup=localsettings.defaultNewPatientDetails
        self.ui.snameEdit.setText(dup_tup[0])
        self.ui.addr1Edit.setText(dup_tup[1])
        self.ui.addr2Edit.setText(dup_tup[2])
        self.ui.addr3Edit.setText(dup_tup[3])
        self.ui.townEdit.setText(dup_tup[4])
        self.ui.countyEdit.setText(dup_tup[5])
        self.ui.pcdeEdit.setText(dup_tup[6])
        self.ui.tel1Edit.setText(dup_tup[7])


class printingClass():
    def commitPDFtoDB(self, descr, serialno=None):
        '''
        grabs "temp.pdf" and puts into the db.
        '''
        print "comitting pdf to db"
        if serialno == None:
            serialno=self.pt.serialno
        try:
            ##todo - this try/catch is naff.
            pdfDup=utilities.getPDF()
            if pdfDup == None:
                self.advise("PDF is NONE - (tell Neil this happened)")
            else:
                #-field is 20 chars max.. hence the [:14]
                docsprinted.add(serialno, descr[:14] + " (pdf)", pdfDup)
                #--now refresh the docprinted widget (if visible)
                if self.ui.previousCorrespondence_treeWidget.isVisible():
                    self.docsPrinted()
        except Exception, e:
            self.advise("Error saving PDF copy %s"% e, 2)

    def printDupReceipt(self):
        dupdate=self.ui.dupReceiptDate_lineEdit.text()
        amount=self.ui.receiptDoubleSpinBox.value()*100
        self.printReceipt({"Professional Services":amount}, True, dupdate)
        self.pt.addHiddenNote("printed", "duplicate receipt for %.02f"%amount)

    def printReceipt(self, valDict, duplicate=False, dupdate=""):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        myreceipt=receiptPrint.receipt(self)

        myreceipt.setProps(self.pt.title, self.pt.fname, self.pt.sname,
        self.pt.addr1, self.pt.addr2, self.pt.addr3, self.pt.town,
        self.pt.county, self.pt.pcde)

        myreceipt.receivedDict=valDict
        if duplicate:
            myreceipt.isDuplicate=duplicate
            myreceipt.dupdate=dupdate
            self.pt.addHiddenNote("printed", "dup receipt")
        else:
            self.pt.addHiddenNote("printed", "receipt")

        if myreceipt.print_():
            if duplicate:
                self.commitPDFtoDB("dup receipt")
            else:
                self.commitPDFtoDB("receipt")


    def printLetter(self):
        '''prints a letter to the patient'''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        html=standardletter.getHtml(self.pt)
        Dialog = QtGui.QDialog(self)
        dl = Ui_enter_letter_text.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.textEdit.setHtml(html)
        if Dialog.exec_():
            html=dl.textEdit.toHtml()
            myclass=letterprint.letter(html)
            myclass.printpage()
            html=str(html.toAscii())
            docsprinted.add(self.pt.serialno, "std letter (html)", html)
            self.pt.addHiddenNote("printed", "std letter")
            if self.ui.previousCorrespondence_treeWidget.isVisible():
                self.docsPrinted()

    def printAccountsTable(self):
        '''
        print the table
        '''
        #-- set a pointer for readability
        table=self.ui.accounts_tableWidget
        rowno=table.rowCount()
        colno=table.columnCount()
        if rowno == 0:
            self.advise("Nothing to print - have you loaded the table?", 1)
            return()
        total=0.0
        html='<html><body><table border="1">'
        html+='''<tr><th>Dent</th><th>SerialNo</th><th>Cset</th><th>FName</th>
        <th>Sname</th><th>DOB</th><th>Memo</th><th>Last Appt</th>
        <th>Last Bill</th><th>Type</th><th>Number</th><th>Complete</th>
        <th>Amount</th></tr>'''
        for row in range(rowno):
            if row%2 == 0:
                html+='<tr bgcolor="#eeeeee">'
            else:
                html+='<tr>'
            for col in range(13):
                item=table.item(row, col)
                if item:
                    if col == 1:
                        html+='<td align="right">%s</td>'%item.text()
                    elif col == 12:
                        html+='<td align="right">&pound;%s</td>'%item.text()
                        total+=float(item.text())
                    else:
                        html+='<td>%s</td>'%item.text()
                else:
                    html+='<td> </td>'
            html+='</tr>\n'

        html+='''<tr><td colspan="11"></td><td><b>TOTAL</b></td>
        <td align="right"><b>&pound; %.02f</b></td></tr>
        </table></body></html>'''%total

        #--test code
        #f=open("/home/neil/Desktop/accounts.html", "w")
        #f.write(html)
        #f.close()
        myclass=letterprint.letter(html)
        myclass.printpage()

    def printEstimate(self):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        est=estimatePrint.estimate()
        est.setProps(self.pt.title, self.pt.fname, self.pt.sname, self.pt.serialno)
        est.estItems=estimates.sorted(self.pt.estimates)

        if est.print_():
            self.commitPDFtoDB("auto estimate")
        self.pt.addHiddenNote("printed", "estimate")


    def customEstimate(self, html="", version=0):
        '''
        prints a custom estimate to the patient
        '''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        if html == "":
            html=standardletter.getHtml(self.pt)
            pt_total=0
            ehtml="<br />Estimate for your current course of treatment."
            ehtml+="<br />"*4
            ehtml+='<table width=400>'
            for est in estimates.sorted(self.pt.estimates):
                pt_total+=est.ptfee
                number=est.number
                item=est.description
                amount=est.ptfee
                mult=""
                if number>1:
                    mult="s"
                item=item.replace("*", mult)
                if "^" in item:
                    item=item.replace("^", "")

                ehtml+='<tr><td>%s</td><td>%s</td><td align="right">\xa3%s</td></tr>'%(
                number, item, localsettings.formatMoney(amount))
            ehtml+='<tr><td></td><td><b>TOTAL</b></td>'
            ehtml+='<td align="right">\xa3%s</td></tr>'%(
            localsettings.formatMoney(pt_total))
            ehtml+="</table>"
            ehtml+="<br />"*4
            html=html.replace("<br />"*(12), ehtml)
            html+="<i>Please note, this estimate may be subject to change if "
            html+="clinical circumstances dictate.</i>"
        else:
            print "html", html
        Dialog = QtGui.QDialog(self)
        dl = Ui_enter_letter_text.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.textEdit.setHtml(html)
        if Dialog.exec_():
            html=dl.textEdit.toHtml()
            myclass=letterprint.letter(html)
            myclass.printpage()

            html=str(dl.textEdit.toHtml().toAscii())

            docsprinted.add(self.pt.serialno,
            "cust estimate (html)", html, version+1)

            self.pt.addHiddenNote("printed", "cust estimate")

    def printReferral(self):
        '''prints a referal letter controlled by referal.xml file'''
        ####TODO this file should really be in the sql database
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        desc=self.ui.referralLettersComboBox.currentText()
        html=referral.getHtml(desc, self.pt)
        Dialog = QtGui.QDialog(self)
        dl = Ui_enter_letter_text.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.textEdit.setHtml(html)
        if Dialog.exec_():
            html=dl.textEdit.toHtml()
            myclass=letterprint.letter(html)
            myclass.printpage()
            docsprinted.add(self.pt.serialno, "referral (html)", html)
            self.pt.addHiddenNote("printed", "referral")
            if self.ui.previousCorrespondence_treeWidget.isVisible():
                self.docsPrinted()

    def printChart(self):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        chartimage=QtGui.QPixmap
        staticimage=chartimage.grabWidget(self.ui.summaryChartWidget)
        myclass=chartPrint.printChart(self.pt, staticimage)
        myclass.printpage()
        self.pt.addHiddenNote("printed", "static chart")

    def printApptCard(self):
        iter=QtGui.QTreeWidgetItemIterator(self.ui.ptAppointment_treeWidget,
        QtGui.QTreeWidgetItemIterator.Selectable)

        futureAppts=()
        while iter.value():
            #self.ui.ptAppointment_treeWidget.setItemSelected(iter)
            i=iter.value() #self.ui.ptAppointment_treeWidget.currentItem()
            adate=str(i.text(0))
            if localsettings.uk_to_sqlDate(adate)>localsettings.sqlToday():
                futureAppts+=((adate, str(i.text(2)), str(i.text(1))), )
            iter+=1
        card=apptcardPrint.card(self.ui)
        card.setProps(self.pt.title, self.pt.fname, self.pt.sname,
                      self.pt.serialno, futureAppts)
        card.print_()
        self.pt.addHiddenNote("printed", "appt card")

    def printaccount(self, tone="A"):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
        else:
            doc=accountPrint.document(self.pt.title, self.pt.fname, self.pt.sname,
            (self.pt.addr1, self.pt.addr2, self.pt.addr3, self.pt.town, self.\
            pt.county), self.pt.pcde, localsettings.formatMoney(self.pt.fees))
            doc.setTone(tone)
            if tone == "B":
                doc.setPreviousCorrespondenceDate(self.pt.billdate)
                ####TODO unsure if this is correct date! - p
                ####lease print one and try it!
            if doc.print_():
                self.pt.updateBilling(tone)
                self.pt.addHiddenNote("printed", "account - tone %s"%tone)
                self.addNewNote("Account Printed")
                self.commitPDFtoDB("Account tone%s"%tone)

    def testGP17(self):
        self.printGP17(True)


    def printGP17(self, test=False):
        #-- if test is true.... you also get boxes

        #--check that the form is goin gto have the correct dentist
        if self.pt.dnt2 != 0:
            dent=self.pt.dnt2
        else:
            dent=self.pt.dnt1

        Dialog = QtGui.QDialog(self)
        dl = Ui_confirmDentist.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.dents_comboBox.addItems(localsettings.activedents)
        if localsettings.apptix_reverse[dent] in localsettings.activedents:
            pos=localsettings.activedents.index(localsettings.apptix_reverse[dent])
            dl.dents_comboBox.setCurrentIndex(pos)
        else:
            dl.dents_comboBox.setCurrentIndex(-1)

        if Dialog.exec_():
            #-- see if user has overridden the dentist
            chosenDent=str(dl.dents_comboBox.currentText())
            dent=localsettings.ops_reverse[chosenDent]
            form=GP17.gp17(self.pt, dent, test)
            form.print_()
            if not test:
                self.pt.addHiddenNote("printed", "GP17 %s"%chosenDent)

    def accountButton2Clicked(self):
        if self.ui.accountB_radioButton.isChecked():
            self.printaccount("B")
        elif self.ui.accountC_radioButton.isChecked():
            print "harsh letter"
            self.printaccount("C")
        else:
            self.printaccount()

    def printdaylists(self, args, expanded=False):
        #-args is a tuple (dent, date)
        '''prints the single book pages'''
        dlist=daylistprint.printDaylist()
        something_to_print=False
        for arg in args:
            data=appointments.printableDaylistData(arg[1].toPyDate(), arg[0])
            #note arg[1]=Qdate
            if data != []:
                something_to_print=True
                dlist.addDaylist(arg[1], arg[0], data)
        if something_to_print:
            dlist.print_(expanded)

    def printmultiDayList(self, args):
        '''prints the multiday pages'''
        #-- args= ((dent, date), (dent, date)...)
        dlist=multiDayListPrint.printDaylist()
        something_to_print=False
        for arg in args:
            data=appointments.printableDaylistData(arg[1].toPyDate(), arg[0])
            #note arg[1]=Qdate
            if data != []:
                something_to_print=True
                dlist.addDaylist(arg[1], arg[0], data)
        if something_to_print:
            dlist.print_()
    def book1print(self):
        try:
            dent=localsettings.apptix[self.ui.apptBookWidgets[0].dentist]
            date=self.ui.appointmentCalendarWidget.selectedDate()
            books=((dent, date), )
            self.printdaylists(books)
        except KeyError:
            self.advise("error printing book", 1)
    def book2print(self):
        try:
            dent=localsettings.apptix[self.ui.apptBookWidgets[1].dentist]
            date=self.ui.appointmentCalendarWidget.selectedDate()
            books=((dent, date), )
            self.printdaylists(books)
        except KeyError:
                self.advise("error printing book", 1)

    def book3print(self):
        try:
            dent=localsettings.apptix[self.ui.apptBookWidgets[2].dentist]
            date=self.ui.appointmentCalendarWidget.selectedDate()
            books=((dent, date), )
            self.printdaylists(books)
        except KeyError:
                self.advise("error printing book", 1)

    def daylistPrintWizard(self):
        def checkAll(arg):
            for cb in checkBoxes.values():
                cb.setChecked(arg)
        Dialog = QtGui.QDialog(self)
        dl = Ui_daylist_print.Ui_Dialog()
        dl.setupUi(Dialog)
        vlayout = QtGui.QGridLayout(dl.scrollArea)
        dl.alldentscheckBox = QtGui.QCheckBox(QtCore.QString("All Books"))
        dl.alldentscheckBox.setChecked(True)
        dl.alldentscheckBox.connect(dl.alldentscheckBox,
                                    QtCore.SIGNAL("stateChanged(int)"), checkAll)
        row=0
        vlayout.addWidget(dl.alldentscheckBox, row, 0, 1, 2)
        checkBoxes={}
        for dent in localsettings.activedents+localsettings.activehygs:
            cb=QtGui.QCheckBox(QtCore.QString(dent))
            cb.setChecked(True)
            checkBoxes[localsettings.apptix[dent]]=cb
            row+=1
            vlayout.addWidget(cb, row, 1, 1, 1)
        dl.start_dateEdit.setDate(QtCore.QDate.currentDate())
        dl.end_dateEdit.setDate(QtCore.QDate.currentDate())
        if Dialog.exec_():
            sday=dl.start_dateEdit.date()
            eday=dl.end_dateEdit.date()
            books=[]
            while sday<=eday:
                for dent in localsettings.activedents+localsettings.activehygs:
                    if checkBoxes[localsettings.apptix[dent]].checkState():
                        books.append((localsettings.apptix[dent], sday))
                sday=sday.addDays(1)
            if dl.allOnePage_radioButton.isChecked():
                self.printmultiDayList(books)
            else:
                self.printdaylists(books, dl.onePageFull_radioButton.isChecked())

    def printrecall(self):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
        else:
            args=((self.pt.title, self.pt.fname, self.pt.sname, self.pt.dnt1,
            self.pt.serialno, self.pt.addr1, self.pt.addr2, self.pt.addr3, \
            self.pt.town, self.pt.county, self.pt.pcde), )

            recallprint.printRecall(args)
            self.pt.addHiddenNote("printed", "recall - non batch")

    def printNotesV(self):
        '''verbose notes print'''
        self.printNotes(1)

    def printNotes(self, detailed=False):
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        note=notes.notes(self.pt.notestuple, detailed)
        #--not verbose...
        myclass=notesPrint.printNotes(note)
        myclass.printpage()
        self.pt.addHiddenNote("printed", "notes")


class pageHandlingClass():

    def handle_mainTab(self):
        '''procedure called when user navigates the top tab'''
        ci=self.ui.main_tabWidget.currentIndex()
        if ci != 2 and self.ui.aptOVmode_label.text() == "Scheduling Mode":
            self.advise("Appointment not made", 1)
            self.aptOVviewMode(True)

        #--user is viewing appointment book
        if ci == 1:
            today=QtCore.QDate.currentDate()
            if self.ui.appointmentCalendarWidget.selectedDate() != today:
                self.ui.appointmentCalendarWidget.setSelectedDate(today)
            else:
                self.layout_appointments()
            self.triangles()
            for book in self.ui.apptBookWidgets:
                book.update()

        #--user is viewing apointment overview
        if ci == 2:
            self.layout_apptOV()

        if ci == 7:
            if not self.feestableLoaded:
                fees_module.loadFeesTable(self)
        if ci == 8:
            forum_gui_module.loadForum(self)

    def handle_patientTab(self):
        '''handles navigation of patient record'''
        ci=self.ui.tabWidget.currentIndex()
        #--admin tab selected

        if ci == 0:
            self.ui.patientEdit_groupBox.setTitle(
            "Edit Patient %d"%self.pt.serialno)

            if self.load_editpage():
                self.editPageVisited=True
        if ci == 1:
            self.updateStatus()
            self.ui.badDebt_pushButton.setEnabled(self.pt.fees>0)
            contract_gui_module.handle_ContractTab(self)
            
        if ci == 2:
            self.docsPrinted()

        if ci == 3:
            self.load_receptionSummaryPage()
        if ci == 4:
            self.load_clinicalSummaryPage()

        if ci == 5:
            self.updateNotesPage()

        #--perio tab
        if ci == 8:
            self.periochart_dates()
            #load the periocharts (if the patient has data)
            self.layoutPerioCharts()
            #--select the UR8 on the perioChartWidget
            self.ui.perioChartWidget.selected=[0, 0]

        if ci == 7:
            #-- estimate/plan page.
            self.load_newEstPage()
            self.load_treatTrees()
        #--debug tab
        ##TODO - this is a development tab- remove eventually
        if ci == 9:
            pass
            #-- this was causing issues when user went "home".. it was getting
            #-- triggered
            #self.ui.pastData_toolButton.showMenu()


    def home(self):
        '''
        User has clicked the homw push_button -
        clear the patient, and blank the screen
        '''
        if self.enteringNewPatient():
            return
        if not self.okToLeaveRecord():
            print "not clearing record"
            return
        self.clearRecord()
        #--disable much of the UI
        self.enableEdit(False)

        #--go to either "reception" or "clinical summary"
        self.gotoDefaultTab()

    def clearRecord(self):
        '''
        clears the memory of all references to the last patient.. and
        ensures that tab pages for reception and clinical summary are cleared.
        Other pages are disabled.
        '''
        if self.pt.serialno != 0:
            self.ui.dobEdit.setDate(QtCore.QDate(1900, 1, 1))
            self.ui.detailsBrowser.setText("")
            self.ui.notesBrowser.setText("")
            self.ui.notesSummary_textBrowser.setText("")
            self.ui.bpe_groupBox.setTitle("BPE")
            self.ui.bpe_textBrowser.setText("")
            self.ui.planSummary_textBrowser.setText("")

            #--restore the charts to full dentition
            ##TODO - perhaps handle this with the tabwidget calls?
            for chart in (self.ui.staticChartWidget, self.ui.planChartWidget,
            self.ui.completedChartWidget, self.ui.perioChartWidget,
            self.ui.summaryChartWidget):
                chart.clear()
                chart.update()
            self.ui.notesSummary_textBrowser.setHtml(localsettings.message)
            self.ui.moneytextBrowser.setHtml(localsettings.message)
            self.ui.chartsTableWidget.clear()
            self.ui.ptAppointment_treeWidget.clear()
            self.ui.notesEnter_textEdit.setHtml("")

            #--load a blank version of the patient class
            self.pt_dbstate=patient_class.patient(0)
            #--and have the comparison copy identical (to check for changes)
            self.pt=copy.deepcopy(self.pt_dbstate)
            if self.editPageVisited:
                self.load_editpage()####################is this wise???????

    def gotoDefaultTab(self):
        '''
        go to either "reception" or "clinical summary"
        '''
        if localsettings.station == "surgery":
            self.ui.tabWidget.setCurrentIndex(4)
        else:
            self.ui.tabWidget.setCurrentIndex(3)

    def load_clinicalSummaryPage(self):
        self.ui.planSummary_textBrowser.setHtml(plan.summary(self.pt))

    def load_receptionSummaryPage(self):
        estimateHtml=estimates.toBriefHtml(self.pt.estimates)
        self.ui.moneytextBrowser.setText(estimateHtml)
        self.layout_apptTable()

    def load_newEstPage(self):
        '''
        populate my custom widget (estWidget)
        this is probably quite computationally expensive
        so should only be done if the widget is visible
        '''
        self.ui.estWidget.setEstimate(self.pt.estimates)

    def load_treatTrees(self):
        self.ui.plan_treeWidget.clear()
        pdict=plan.plannedDict(self.pt)
        #-- pdict is a dictionary in the format
        #-- {'Perio': ['perio - SP'], Diagnosis': ['xray - 2S', 'xray - M']}
        #-- so the keys are treatment categories... and they contain a list
        #-- of treatments within that category
        #-- display as a tree view

        #-- PLANNED ITEMS
        itemToCompress=None
        for category in pdict.keys():
            items=pdict[category]
            header=category + '(%d items)'%len(items)
            parent = QtGui.QTreeWidgetItem(
                    self.ui.plan_treeWidget, [header])
            if category == "Tooth":
                itemToCompress=parent
            for item in items:
                child = QtGui.QTreeWidgetItem(parent, [item])
            #-- next line causes drawing errors?
            #self.ui.plan_treeWidget.expandItem(parent)
        self.ui.plan_treeWidget.expandAll()
        self.ui.plan_treeWidget.resizeColumnToContents(0)
        if itemToCompress:
            itemToCompress.setExpanded(False)
        #--COMPLETED ITEMS

        self.ui.comp_treeWidget.clear()
        pdict=plan.completedDict(self.pt)
        for category in pdict.keys():
            items=pdict[category]
            header=category + '(%d items)'%len(items)
            parent = QtGui.QTreeWidgetItem(
                    self.ui.comp_treeWidget, [header])
            if category == "Tooth":
                itemToCompress=parent
            for item in items:
                child = QtGui.QTreeWidgetItem(parent, [item])
        self.ui.comp_treeWidget.expandAll()
        self.ui.comp_treeWidget.resizeColumnToContents(0)
        if itemToCompress:
            itemToCompress.setExpanded(False)

    def load_editpage(self):
        self.ui.titleEdit.setText(self.pt.title)
        self.ui.fnameEdit.setText(self.pt.fname)
        self.ui.snameEdit.setText(self.pt.sname)
        self.ui.dobEdit.setDate(QtCore.
                                QDate.fromString(self.pt.dob, "dd'/'MM'/'yyyy"))
        self.ui.addr1Edit.setText(self.pt.addr1)
        self.ui.addr2Edit.setText(self.pt.addr2)
        self.ui.addr3Edit.setText(self.pt.addr3)
        self.ui.townEdit.setText(self.pt.town)
        self.ui.countyEdit.setText(self.pt.county)
        if self.pt.sex == "M":
            self.ui.sexEdit.setCurrentIndex(0)
        else:
            self.ui.sexEdit.setCurrentIndex(1)
        self.ui.pcdeEdit.setText(self.pt.pcde)
        self.ui.memoEdit.setText(self.pt.memo)
        self.ui.tel1Edit.setText(self.pt.tel1)
        self.ui.tel2Edit.setText(self.pt.tel2)
        self.ui.mobileEdit.setText(self.pt.mobile)
        self.ui.faxEdit.setText(self.pt.fax)
        self.ui.email1Edit.setText(self.pt.email1)
        self.ui.email2Edit.setText(self.pt.email2)
        self.ui.occupationEdit.setText(self.pt.occup)
        return True
    def load_dentComboBoxes(self):
        print "loading dnt comboboxes."
        try:
            self.ui.dnt1comboBox.setCurrentIndex(
            localsettings.activedents.index(localsettings.ops[self.pt.dnt1]))

            self.ui.dnt2comboBox.setCurrentIndex(
            localsettings.activedents.index(localsettings.ops[self.pt.dnt1]))

        except Exception, e:
            self.ui.dnt1comboBox.setCurrentIndex(-1)
            if self.pt.dnt1 != 0:
                print "self.pt.dnt1 error - record %d"%self.pt.serialno
                if localsettings.ops.has_key(self.pt.dnt1):
                    self.advise(
                    "%s is no longer an active dentist in this practice"%\
                    localsettings.ops[self.pt.dnt1], 2)
                else:
                    print "unknown dentist number", self.pt.dnt1
                    self.advise(
                    "unknown contract dentist - please correct this", 2)
        if self.pt.dnt2>0:
            try:
                self.ui.dnt2comboBox.setCurrentIndex(localsettings.activedents.\
                                        index(localsettings.ops[self.pt.dnt2]))
            except KeyError, e:
                print "self.pt.dnt2 error - record %d"
                self.ui.dnt2comboBox.setCurrentIndex(-1)
                if localsettings.ops.has_key(self.pt.dnt1):
                    self.advise("%s (dentist 2) "%localsettings.\
                    ops[self.pt.dnt2]+"is no longer an active dentist i"
                    +"n this practice", 1)
                else:
                    self.advise(
                    "unknown course dentist - please correct this", 2)

class openmolarGui(QtGui.QMainWindow, customWidgets, chartsClass,
pageHandlingClass, newPatientClass, appointmentClass, signals, 
printingClass, cashbooks, historyClass):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui=Ui_main.Ui_MainWindow()
        self.ui.setupUi(self)

        #--initiate a blank version of the patient class this
        #--is used to check for state.
        self.pt_dbstate=patient_class.patient(0)
        #--make a deep copy to check for changes
        self.pt=copy.deepcopy(self.pt_dbstate)
        self.selectedChartWidget="st" #other values are "pl" or "cmp"
        self.grid = ("ur8", "ur7", "ur6", "ur5", 'ur4', 'ur3', 'ur2', 'ur1', 'ul1',
        'ul2', 'ul3', 'ul4', 'ul5', 'ul6', 'ul7', 'ul8', "lr8", "lr7", "lr6", "lr5",
        'lr4', 'lr3', 'lr2', 'lr1', 'll1', 'll2', 'll3', 'll4', 'll5', 'll6', 'll7', 'll8')
        self.labels_and_tabs()
        self.addCustomWidgets()
        self.setValidators()
        self.setupSignals()
        self.loadDentistComboboxes()
        self.feestableLoaded=False

        #--adds items to the daylist comboBox
        self.load_todays_patients_combobox()
        self.appointmentData=()
        self.editPageVisited=False

    def advise(self, arg, warning_level=0):
        '''
        inform the user of events -
        warning level0 = status bar only.
        warning level 1 advisory
        warning level 2 critical (and logged)
        '''
        if warning_level == 0:
            self.ui.statusbar.showMessage(arg, 5000) #5000 milliseconds=5secs
        elif warning_level == 1:
            QtGui.QMessageBox.information(self, "Advisory", arg)
        elif warning_level == 2:
            now=QtCore.QTime.currentTime()
            QtGui.QMessageBox.warning(self, "Error", arg)
            #--for logging purposes
            print "%d:%02d ERROR MESSAGE"%(now.hour(), now.minute()), arg

    def quit(self):
        '''
        function called by the quit button in the menu
        '''
        self.app.closeAllWindows()

    def closeEvent(self, event=None):
        '''
        overrule QMaindow's close event
        check for unsaved changes then politely close the app if appropriate
        '''
        print "quit called"
        if self.okToLeaveRecord():
            #TODO - save some settings here????
            pass
        else:
            print "user overuled"
            event.ignore()

    def aboutOM(self):
        '''
        called by menu - help - about openmolar
        '''
        self.advise('''<p>%s</p><p>%s</p>'''%(localsettings.about,
        localsettings.license), 1)

    def setClinician(self):
        self.advise("To change practitioner, please login again", 1)


    def okToLeaveRecord(self):
        '''
        leaving a pt record - has state changed?
        '''
        if self.pt.serialno == 0:
            return True
        #--a debug print statement
        print "leaving record checking to see if save is required...",

        #--apply changes to patient details
        if self.editPageVisited:
            self.apply_editpage_changes()

        #--check pt against the original loaded state
        #--this returns a LIST of changes ie [] if none.
        uc=self.unsavedChanges()
        if uc != []:
            #--raise a custom dialog to get user input
            #--(centred over self)
            Dialog = QtGui.QDialog(self)
            dl = saveDiscardCancel.sdcDialog(Dialog, self.pt.fname+" "+\
                        self.pt.sname+" (%s)"%self.pt.serialno, uc)
            if Dialog.exec_():
                if dl.result == "discard":
                    print "user discarding changes"
                    return True
                elif dl.result == "save":
                    print "user is saving"
                    self.save_changes(True)
                    return True
                #--cancelled action
                else:
                    print "user chose to continue editing"
                    return False
        else:
            print "no changes"
            return True

    def showAdditionalFields(self):
        '''
        more Fields Button has been pressed
        '''
        self.advise("not yet available", 1)
        #TODO - add more code here!!

    def docsPrinted(self):
        '''
        load the docsprinted listWidget
        '''
        self.ui.previousCorrespondence_treeWidget.clear()
        self.ui.previousCorrespondence_treeWidget.setHeaderLabels(["Date", "Type", "Version", "Index"])
        docs=docsprinted.previousDocs(self.pt.serialno)
        for d in docs:
            doc=[str(d[0]), str(d[1]), str(d[2]), str(d[3])]
            i=QtGui.QTreeWidgetItem(
            self.ui.previousCorrespondence_treeWidget, doc)
        self.ui.previousCorrespondence_treeWidget.expandAll()
        for i in range(self.ui.previousCorrespondence_treeWidget.columnCount()):
            self.ui.previousCorrespondence_treeWidget.resizeColumnToContents(i)
        #-- hide the index column
        self.ui.previousCorrespondence_treeWidget.setColumnWidth(3, 0)

    def showDoc(self, item, index):
        '''
        called by a double click on the documents listview
        '''
        print "showDoc"

        ix=int(item.text(3))
        if "html" in item.text(1):
            print "html file found!"
            result=QtGui.QMessageBox.question(self, "Re-open",
            "Do you want to review and/or reprint this item?",
                    QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if result == QtGui.QMessageBox.Yes:
                html, version=docsprinted.getData(ix)
                self.customEstimate(html, version)

        elif "pdf" in item.text(1):
            result=QtGui.QMessageBox.question(self, "Re-open",
            "Do you want to review and/or reprint this item?",
                    QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if result == QtGui.QMessageBox.Yes:
                try:
                    data, version=docsprinted.getData(ix)
                    f=open("temp.pdf", "w")
                    f.write(data)
                    f.close()
                    subprocess.Popen(["%s"%localsettings.pdfProg, "temp.pdf"])
                except Exception, e:
                    print "view PDF error"
                    print Exception, e
                    self.advise("error reviewing PDF file<br />"
                    +"tried to open with evince on Linux"
                    +" or default PDF reader on windows", 1)
        else: #unknown data type... probably plain text.
            print "other type of doc"
            data=docsprinted.getData(ix)[0]
            if data == None:
                data="No information available about this document, sorry"
            self.advise(data, 1)

    def load_todays_patients_combobox(self):
        '''
        loads the quick select combobox, with all of todays's
        patients - if a list(tuple) of dentists is passed eg ,(("NW"))
        then only pt's of that dentist show up
        '''
        if localsettings.clinicianNo != 0:
            dents=(localsettings.clinicianInits, )
            visibleItem="Today's Patients (%s)"%dents
        else:
            dents=("*", )
            visibleItem="Today's Patients (ALL)"
        self.advise("loading today's patients")
        self.ui.daylistBox.addItem(visibleItem)

        for pt in appointments.todays_patients(dents):
            val=pt[1]+" -- " + str(pt[0])
            #--be wary of changing this -- is used as a marker some
            #--pt's have hyphonated names!
            self.ui.daylistBox.addItem(QtCore.QString(val))

    def todays_pts(self):
        arg=str(self.ui.daylistBox.currentText())
        if arg[0:7] !="Today's":
            self.ui.daylistBox.setCurrentIndex(0)
            serialno=int(arg[arg.index("--")+2:])
            #--see above comment
            self.getrecord(serialno)

    def loadDentistComboboxes(self):
        '''
        populate several comboboxes with the activedentists
        '''
        s=["*ALL*"] + localsettings.ops.values()
        self.ui.daybookDent1ComboBox.addItems(s)
        self.ui.daybookDent2ComboBox.addItems(s)
        self.ui.cashbookDentComboBox.addItems(s)
        self.ui.dnt1comboBox.addItems(localsettings.activedents)
        self.ui.dnt2comboBox.addItems(localsettings.activedents)

    def find_related(self):
        '''
        looks for patients with similar name, family or address
        to the current pt
        '''
        if self.pt.serialno == 0:
            self.advise("No patient to compare to", 2)
            return
        def family_navigated():
            dl.selected = dl.family_tableWidget.item(dl.family_tableWidget.\
                                                     currentRow(), 0).text()
        def address_navigated():
            dl.selected = dl.address_tableWidget.item(dl.address_tableWidget.\
                                                      currentRow(), 0).text()
        def soundex_navigated():
            dl.selected = dl.soundex_tableWidget.item(dl.soundex_tableWidget.\
                                                      currentRow(), 0).text()

        candidates=search.getsimilar(self.pt.serialno, self.pt.addr1, self.\
                                     pt.sname, self.pt.familyno)
        if candidates != ():
            Dialog = QtGui.QDialog(self)
            dl = Ui_related_patients.Ui_Dialog()
            dl.setupUi(Dialog)
            dl.selected=0

            dl.thisPatient_label.setText(
            "Possible Matches for patient - %d - %s %s - %s"%(
            self.pt.serialno, self.pt.fname, self.pt.sname, self.pt.addr1))

            Dialog.setFixedSize(self.width()-50, self.height()-50)
            headers=['Serialno', 'Surname', 'Forename', 'dob', 'Address1',\
            'Address2', 'POSTCODE']
            tableNo=0
            for table in (dl.family_tableWidget, dl.address_tableWidget,
            dl.soundex_tableWidget):
                table.clear()
                table.setSortingEnabled(False)
                #--good practice to disable this while loading
                table.setRowCount(len(candidates[tableNo]))
                table.setColumnCount(len(headers))
                table.setHorizontalHeaderLabels(headers)
                #table.verticalHeader().hide()
                row=0
                for candidate in candidates[tableNo]:
                    col=0
                    for attr in candidate:
                        item=QtGui.QTableWidgetItem(str(attr))
                        table.setItem(row, col, item)
                        col+=1
                    row+=1
                table.resizeColumnsToContents()
                table.setSortingEnabled(True)
                #--allow user to sort pt attributes
                tableNo+=1
            QtCore.QObject.connect(dl.family_tableWidget, QtCore.SIGNAL(
            "itemSelectionChanged()"), family_navigated)
            QtCore.QObject.connect(dl.address_tableWidget, QtCore.SIGNAL(
            "itemSelectionChanged()"), address_navigated)
            QtCore.QObject.connect(dl.soundex_tableWidget, QtCore.SIGNAL(
            "itemSelectionChanged()"), soundex_navigated)

            if Dialog.exec_():
                self.getrecord(int(dl.selected))
        else:
            self.advise("no similar patients found")

    def next_patient(self):
        '''
        cycle forwards through the list of recently visited records
        '''
        cp= self.pt.serialno
        recent=localsettings.recent_snos
        try:
            last_serialno=recent[recent.index(cp)+1]
            self.getrecord(last_serialno)
        except ValueError:
            self.advise("Reached End of  List")
        except Exception, e:
            print "Exception in maingui.next_patient", e

    def last_patient(self):
        '''
        cycle backwards through recently visited records
        '''
        cp= self.pt.serialno
        recent=localsettings.recent_snos
        if cp == 0 and len(recent)>0:
            last_serialno=recent[-1]
            self.getrecord(last_serialno)
        else:
            try:
                last_serialno=recent[recent.index(cp)-1]
                self.getrecord(last_serialno)
            except ValueError:
                self.advise("Reached start of  List")
            except Exception, e:
                print "Exception in maingui.next_patient", e

    def apply_editpage_changes(self):
        '''
        apply any changes made on the edit patient page
        '''
        if self.pt.serialno == 0 and self.ui.newPatientPushButton.isEnabled():
            ###firstly.. don't apply edit page changes if there
            ####is no patient loaded,
            ###and no new patient to apply
            return

        self.pt.title=str(self.ui.titleEdit.text().toAscii()).upper()
        #--NB - these are QSTRINGs... hence toUpper() not PYTHON equiv upper()
        self.pt.fname=str(self.ui.fnameEdit.text().toAscii()).upper()
        self.pt.sname=str(self.ui.snameEdit.text().toAscii()).upper()
        self.pt.dob=localsettings.formatDate(self.ui.dobEdit.date().toPyDate())
        self.pt.addr1=str(self.ui.addr1Edit.text().toAscii()).upper()
        self.pt.addr2=str(self.ui.addr2Edit.text().toAscii()).upper()
        self.pt.addr3=str(self.ui.addr3Edit.text().toAscii()).upper()
        self.pt.town=str(self.ui.townEdit.text().toAscii()).upper()
        self.pt.county=str(self.ui.countyEdit.text().toAscii()).upper()
        self.pt.sex=str(self.ui.sexEdit.currentText().toAscii()).upper()
        self.pt.pcde=str(self.ui.pcdeEdit.text().toAscii()).upper()
        self.pt.memo=str(self.ui.memoEdit.toPlainText().toAscii())
        self.pt.tel1=str(self.ui.tel1Edit.text().toAscii()).upper()
        self.pt.tel2=str(self.ui.tel2Edit.text().toAscii()).upper()
        self.pt.mobile=str(self.ui.mobileEdit.text().toAscii()).upper()
        self.pt.fax=str(self.ui.faxEdit.text().toAscii()).upper()
        self.pt.email1=str(self.ui.email1Edit.text().toAscii())
        #--leave as user entered case
        self.pt.email2=str(self.ui.email2Edit.text().toAscii())
        self.pt.occup=str(self.ui.occupationEdit.text().toAscii()).upper()

    def accountsTableClicked(self, row, column):
        sno=self.ui.accounts_tableWidget.item(row, 1).text()
        print sno
        self.getrecord(int(sno))

    def getrecord(self, serialno, checkedNeedToLeaveAlready=False):
        '''
        a record has been called byone of several means
        '''
        if self.enteringNewPatient():
            return
        print "get record %d"%serialno
        if not checkedNeedToLeaveAlready and not self.okToLeaveRecord():
            print "not loading"
            self.advise("Not loading patient")
            return
        if serialno != 0:
            self.advise("connecting to database to get patient details..")

            try:
                loadPt=patient_class.patient(serialno)
                #--work on a copy only, so that changes can be tested for later
                #--has to be a deep copy, as opposed to shallow
                #--otherwise changes to attributes which are lists aren't
                #--spotted new "instance" of patient
                self.pt=loadPt
                #-- this next line is to prevent a "not saved warning"
                self.pt_dbstate.fees=self.pt.fees
                try:
                    self.loadpatient()
                except Exception, e:
                    self.advise("Error populating interface\n%s\n%s"%(Exception, e), 2)
                finally:
                    self.pt_dbstate=copy.deepcopy(self.pt)


            except localsettings.PatientNotFoundError:
                print "NOT FOUND ERROR"
                self.advise ("error getting serialno %d"%serialno+
                              "- please check this number is correct?", 1)
                return
                #except Exception, e:
                print "#"*20
                print "SERIOUS ERROR???"
                print str(Exception)
                print e
                print "maingself.ui.getrecord - serialno%d"%serialno
                print "#"*20
                self.advise ("Serious Error - Tell Neil<br />%s"%e, 2)

        else:
            self.advise("get record called with serialno 0")

    def reload_patient(self):
        '''
        reload the current record
        '''
        self.getrecord(self.pt.serialno)

    def updateNotesPage(self):
        if self.ui.notesMaximumVerbosity_radioButton.isChecked():
            self.ui.notesBrowser.setHtml(notes.notes(self.pt.notestuple, 2))
            #--2=verbose
        elif self.ui.notesMediumVerbosity_radioButton.isChecked():
            self.ui.notesBrowser.setHtml(notes.notes(self.pt.notestuple, 1))
        else: #self.ui.notesMinimumVerbosity_radioButton.isChecked():
            self.ui.notesBrowser.setHtml(notes.notes(self.pt.notestuple))
        self.ui.notesBrowser.scrollToAnchor('anchor')

    def loadpatient(self):
        '''
        self.pt is now a patient... time to push to the gui.
        '''
        #-- don't load a patient if you are entering a new one.
        if self.enteringNewPatient():
            return
        print "loading patient"
        self.advise("loading patient")
        self.editPageVisited=False
        self.ui.main_tabWidget.setCurrentIndex(0)
        if localsettings.station == "surgery":
            self.ui.tabWidget.setCurrentIndex(4)
        else:
            self.ui.tabWidget.setCurrentIndex(3)
            self.load_receptionSummaryPage()
        #--populate dnt1 and dnt2 comboboxes
        self.load_dentComboBoxes()
        self.updateDetails()
        self.ui.planSummary_textBrowser.setHtml(plan.summary(self.pt))
        note=notes.notes(self.pt.notestuple)
        #--notes not verbose
        self.ui.notesSummary_textBrowser.setHtml(note)
        self.ui.notesSummary_textBrowser.scrollToAnchor('anchor')
        self.ui.notesBrowser.setHtml("")
        self.ui.notesEnter_textEdit.setText("")
        for chart in (self.ui.staticChartWidget, self.ui.planChartWidget,
        self.ui.completedChartWidget, self.ui.perioChartWidget,
        self.ui.summaryChartWidget):
            chart.clear()
            #--necessary to restore the chart to full dentition
        self.ui.staticChartWidget.setSelected(0, 0)  #select the UR8
        self.chartsTable()
        self.bpe_dates()
        if self.pt.recd:
            self.ui.recall_dateEdit.setDate(
            localsettings.pyDatefromUKDate(self.pt.recd))

        try:
            pos=localsettings.csetypes.index(self.pt.cset)
        except ValueError:
            QtGui.QMessageBox.information(self, "Advisory",
            "Please set a Valid Course Type for this patient")
            pos=-1
        self.ui.cseType_comboBox.setCurrentIndex(pos)
        self.ui.contract_tabWidget.setCurrentIndex(pos)
        #--update bpe
        localsettings.defaultNewPatientDetails=(
        self.pt.sname, self.pt.addr1, self.pt.addr2,
        self.pt.addr3, self.pt.town, self.pt.county, self.pt.pcde, self.pt.tel1)

        if not self.pt.serialno in localsettings.recent_snos:
            #localsettings.recent_snos.remove(self.pt.serialno)
            localsettings.recent_snos.append(self.pt.serialno)
        if self.ui.tabWidget.currentIndex() == 4:  #clinical summary
            self.ui.summaryChartWidget.update()
        self.ui.debugBrowser.setText("")
        self.medalert()
        self.getmemos()

        if localsettings.station == "surgery":
            self.callXrays()
    def getmemos(self):
        urgentMemos = memos.getMemos(self.pt.serialno)
        for umemo in urgentMemos:
            message="<center>Message from %s <br />"%umemo.author
            message+="Dated %s<br /><br />"%localsettings.formatDate(umemo.mdate)
            message+="%s</center>"%umemo.message
            Dialog=QtGui.QDialog(self)
            dl=Ui_showMemo.Ui_Dialog()
            dl.setupUi(Dialog)
            dl.message_label.setText(message)
            if Dialog.exec_():
                if dl.checkBox.checkState():
                    print "deleting Memo %s"%umemo.ix
                    memos.deleteMemo(umemo.ix)

    def newCustomMemo(self):
        Dialog = QtGui.QDialog(self)
        dl = saveMemo.Ui_Dialog(Dialog, self.pt.serialno)
        if not dl.getInput():
            self.advise("memo not saved", 1)

    def medalert(self):
        if self.pt.MEDALERT:
            palette = QtGui.QPalette()
            brush = QtGui.QBrush(colours.med_warning)
            palette.setBrush(QtGui.QPalette.Active,
                             QtGui.QPalette.Button, brush)
            self.ui.medNotes_pushButton.setPalette(palette)
        else:
            self.ui.medNotes_pushButton.setPalette(self.palette())

        if self.pt.MH != None:
            chkdate=self.pt.MH[13]
            if chkdate == None:
                chkdate=""
            else:
                chkdate=" - %s"%chkdate
            self.ui.medNotes_pushButton.setText("MedNotes%s"%chkdate)
        else:
            self.ui.medNotes_pushButton.setText("MedNotes")
        self.enableEdit(True)

    def updateStatus(self):
        '''
        updates the status combobox
        '''
        self.ui.status_comboBox.setCurrentIndex(0)
        for i in range(self.ui.status_comboBox.count()):
            item=self.ui.status_comboBox.itemText(i)
            if str(item).lower() == self.pt.status.lower():
                self.ui.status_comboBox.setCurrentIndex(i)

    def updateDetails(self):
        '''
        sets the patient information into the left column
        '''
        Saved= (self.pt_dbstate.fees == self.pt.fees)
        details=patientDetails.details(self.pt, Saved)
        self.ui.detailsBrowser.setText(details)
        self.ui.detailsBrowser.update()
        curtext="Current Treatment "
        if self.pt.underTreatment:
            self.ui.estimate_groupBox.setTitle(curtext+"- started "+
                                                    str(self.pt.accd))
            self.ui.newCourse_pushButton.setEnabled(False)
            self.ui.closeTx_pushButton.setEnabled(True)
        else:
            self.ui.estimate_groupBox.setTitle(
                                                curtext+"- No Current Course")
            self.ui.newCourse_pushButton.setEnabled(True)
            self.ui.closeTx_pushButton.setEnabled(False)


    def final_choice(self, candidates):
        def DoubleClick():
            '''user double clicked on an item... accept the dialog'''
            Dialog.accept()
        Dialog = QtGui.QDialog(self)
        dl = Ui_select_patient.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.tableWidget.clear()
        dl.tableWidget.setSortingEnabled(False)
        #--good practice to disable this while loading
        dl.tableWidget.setRowCount(len(candidates))
        headers=('Serialno', 'Surname', 'Forename', 'dob', 'Address1',
        'Address2', 'POSTCODE')

        widthFraction=(10, 20, 20, 10, 30, 30, 10)
        dl.tableWidget.setColumnCount(len(headers))
        dl.tableWidget.setHorizontalHeaderLabels(headers)
        dl.tableWidget.verticalHeader().hide()
        row=0
        Dialog.setFixedWidth(self.width()-100)
        for col in range(len(headers)):
            dl.tableWidget.setColumnWidth(col, widthFraction[col]*\
                                          (Dialog.width()-100)/130)
            #grrr - this is a hack. the tablewidget width should be used..
            #but it isn't available yet.
        for candidate in candidates:
            col=0
            for attr in candidate:
                item=QtGui.QTableWidgetItem(str(attr))
                dl.tableWidget.setItem(row, col, item)
                col+=1
            row+=1
        dl.tableWidget.setCurrentCell(0, 1)
        QtCore.QObject.connect(dl.tableWidget, QtCore.SIGNAL(
        "itemDoubleClicked (QTableWidgetItem *)"), DoubleClick)
        #dl.tableWidget.setSortingEnabled(True)
        #allow user to sort pt attributes - buggers things up!!
        if Dialog.exec_():
            row=dl.tableWidget.currentRow()
            result=dl.tableWidget.item(row, 0).text()
            return int(result)

    def find_patient(self):
        if self.enteringNewPatient():
                return
        if not self.okToLeaveRecord():
            print "not loading"
            self.advise("Not loading patient")
            return
        def repeat_last_search():
            dl.dob.setText(localsettings.lastsearch[2])
            dl.addr1.setText(localsettings.lastsearch[4])
            dl.tel.setText(localsettings.lastsearch[3])
            dl.sname.setText(localsettings.lastsearch[0])
            dl.fname.setText(localsettings.lastsearch[1])
            dl.pcde.setText(localsettings.lastsearch[5])
        Dialog = QtGui.QDialog(self)
        dl = Ui_patient_finder.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.dob.setText("00/00/0000")
        dl.dob.setInputMask("00/00/0000")
        QtCore.QObject.connect(dl.repeat_pushButton, QtCore.\
                               SIGNAL("clicked()"), repeat_last_search)
        dl.sname.setFocus()
        if Dialog.exec_():
            dob=str(dl.dob.text())
            addr=str(dl.addr1.text().toAscii())
            tel=str(dl.tel.text().toAscii())
            sname=str(dl.sname.text().toAscii())
            fname=str(dl.fname.text().toAscii())
            pcde=str(dl.pcde.text().toAscii())
            localsettings.lastsearch=(sname, fname, dob, tel, addr, pcde)
            dob=localsettings.uk_to_sqlDate(dl.dob.text())

            try:
                serialno=int(sname)
            except:
                serialno=0
            if serialno>0:
                self.getrecord(serialno, True)
            else:
                candidates=search.getcandidates(dob, addr, tel, sname,
                dl.snameSoundex_checkBox.checkState(), fname,
                dl.fnameSoundex_checkBox.checkState(), pcde)

                if candidates == ():
                    self.advise("no match found", 1)
                else:
                    if len(candidates)>1:
                        sno=self.final_choice(candidates)
                        if sno != None:
                            self.getrecord(int(sno), True)
                    else:
                        self.getrecord(int(candidates[0][0]), True)
        else:
            self.advise("dialog rejected")
    def labels_and_tabs(self):
        self.ui.main_tabWidget.setCurrentIndex(0)
        if localsettings.station == "surgery":
            self.ui.tabWidget.setCurrentIndex(4)
        else:
            self.ui.tabWidget.setCurrentIndex(3)
        self.ui.moneytextBrowser.setHtml(localsettings.message)
        self.ui.notesSummary_textBrowser.setHtml(localsettings.message)

        today=QtCore.QDate().currentDate()
        self.ui.daybookEndDateEdit.setDate(today)
        self.ui.daybookStartDateEdit.setDate(today)
        self.ui.cashbookStartDateEdit.setDate(today)
        self.ui.cashbookEndDateEdit.setDate(today)
        self.ui.recalldateEdit.setDate(today)
        self.ui.stackedWidget.setCurrentIndex(1)
        self.ui.dupReceiptDate_lineEdit.setText(today.toString(
        "dd'/'MM'/'yyyy"))
        brush = QtGui.QBrush(colours.LINEEDIT)
        palette = QtGui.QPalette()
        palette.setBrush(QtGui.QPalette.Base, brush)
        for widg in (self.ui.snameEdit, self.ui.titleEdit, self.ui.fnameEdit,
        self.ui.addr1Edit, self.ui.dobEdit, self.ui.pcdeEdit, self.ui.sexEdit):
            widg.setPalette(palette)
        self.ui.cseType_comboBox.addItems(localsettings.csetypes)
        self.showForumIcon()

    def showForumIcon(self, newItems=True):
        tb=self.ui.main_tabWidget.tabBar()
        if newItems:
            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(":/logo.png"), QtGui.QIcon.Normal,
            QtGui.QIcon.Off)
            tb.setTabIcon(8, icon)
            tb.setTabText(8, "NEW FORUM POSTS")
            tb.setTabTextColor(8, QtGui.QColor("red"))
        else:
            print "removing icon"
            tb.setTabIcon(8, QtGui.QIcon())
            tb.setTabText(8, "FORUM")
            tb.setTabTextColor(8, QtGui.QColor())


    def save_patient_tofile(self):
        '''
        our "patient" is a python object,
        so can be pickled
        save to file is really just a development feature
        '''
        try:
            filepath = QtGui.QFileDialog.getSaveFileName()
            if filepath != '':
                f=open(filepath, "w")
                f.write(pickle.dumps(self.pt))
                f.close()
                self.advise("Patient File Saved", 1)
        except Exception, e:
            self.advise("Patient File not saved - %s"%e, 2)

    def open_patient_fromfile(self):
        '''
        reload a saved (pickled) patient
        only currently works is the OM version is compatible
        '''
        if self.enteringNewPatient():
            return
        if not self.okToLeaveRecord():
            print "not loading"
            self.advise("Not loading patient")
            return
        self.advise("opening patient file")
        filename = QtGui.QFileDialog.getOpenFileName()
        if filename != '':
            self.advise("opening patient file")
            try:
                f=open(filename, "r")
                loadedpt=pickle.loads(f.read())
                if loadedpt.serialno != self.pt.serialno:
                    self.pt_dbstate=patient_class.patient(0)
                    self.pt_dbstate.serialno=loadedpt.serialno
                self.pt=loadedpt
                f.close()
            except Exception, e:
                self.advise("error loading patient file - %s"%e, 2)
        else:
            self.advise("no file chosen", 1)
        self.loadpatient()

    def recallDate(self, arg):
        '''
        receives a signal when the date changes in the recall date edit
        on the correspondence page
        '''
        newdate = localsettings.formatDate(arg.toPyDate())
        if self.pt.recd != newdate:
            self.pt.recd = newdate
            self.updateDetails() 
        

    def exportRecalls(self):
        '''
        gets patients who have the recall date stipulated
        by the ui.recallDateEdit value
        '''
        month=self.ui.recalldateEdit.date().month()
        year=self.ui.recalldateEdit.date().year()
        print "exporting recalls for %s,%s"%(month, year)
        pts=recall.getpatients(month, year)
        dialog=recall_app.Form(pts)
        dialog.exec_()

    def showChartTable(self):
        '''
        flips a stackedwidget to display the table underlying the charts
        '''
        self.ui.stackedWidget.setCurrentIndex(0)

    def showChartCharts(self):
        '''
        flips a stackedwidget to show the charts (default)
        '''
        self.ui.stackedWidget.setCurrentIndex(1)

    def phraseBookDialog(self):
        '''
        show the phraseBook
        '''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        Dialog = QtGui.QDialog(self.ui.notesEnter_textEdit)
        dl = Ui_phraseBook.Ui_Dialog()
        dl.setupUi(Dialog)
        if Dialog.exec_():
            newNotes=""
            for cb in (dl.checkBox, dl.checkBox_2, dl.checkBox_3, dl.checkBox_4,
            dl.checkBox_5, dl.checkBox_6, dl.checkBox_7, dl.checkBox_8):
                if cb.checkState():
                    newNotes+=cb.text()+"\n"
            if newNotes != "":
                self.addNewNote(newNotes)

    def addNewNote(self, arg):
        '''
        used when I programatically add text to the user textEdit
        '''
        self.ui.notesEnter_textEdit.setText(
                self.ui.notesEnter_textEdit.toPlainText()+" "+arg)

    def callXrays(self):
        '''
        this updates a database with the record in use
        '''
        if localsettings.surgeryno == -1:
            Dialog=QtGui.QDialog(self)
            dl=Ui_surgeryNumber.Ui_Dialog()
            dl.setupUi(Dialog)
            if Dialog.exec_():
                localsettings.surgeryno=dl.comboBox.currentIndex()+1
                localsettings.updateLocalSettings(
                "surgeryno", str(localsettings.surgeryno))
            else:
                return
        calldurr.commit(self.pt.serialno, localsettings.surgeryno)

    def showMedNotes(self):
        '''
        user has called for medical notes to be shown
        '''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        Dialog = QtGui.QDialog(self)
        if medNotes.showDialog(Dialog, self.pt):
            self.advise("Updated Medical Notes", 1)
            self.medalert()

    def newBPE_Dialog(self):
        '''
        enter a new BPE
        '''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        Dialog = QtGui.QDialog(self)
        dl = newBPE.Ui_Dialog(Dialog)
        result=dl.getInput()
        if result[0]:
            self.pt.bpe.append((localsettings.ukToday(), result[1]), )
            #--add a bpe
            newnotes=str(self.ui.notesEnter_textEdit.toPlainText().toAscii())
            newnotes+=" bpe of %s recorded \n"%result[1]
            self.ui.notesEnter_textEdit.setText(newnotes)
            self.ui.bpe_textBrowser
        else:
            self.advise("BPE not applied", 2)
        self.bpe_dates()
        self.bpe_table(0)

    def userOptionsDialog(self):
        '''
        not too many user options available yet
        this will change.
        '''
        Dialog = QtGui.QDialog(self)
        dl = Ui_options.Ui_Dialog()
        dl.setupUi(Dialog)
        dl.leftMargin_spinBox.setValue(GP17.offsetLeft)
        dl.topMargin_spinBox.setValue(GP17.offsetTop)

        if Dialog.exec_():
            GP17.offsetLeft=dl.leftMargin_spinBox.value()
            GP17.offsetTop=dl.topMargin_spinBox.value()

    def unsavedChanges(self):
        '''
        important function, checks for changes since the patient was loaded
        '''
        fieldsToExclude=("notestuple", "fees")#, "estimates")
        changes=[]
        if self.pt.serialno == self.pt_dbstate.serialno:
            if len(self.ui.notesEnter_textEdit.toPlainText()) != 0:
                changes.append("New Notes")
            for attr in self.pt.__dict__:
                newval=str(self.pt.__dict__[attr])
                oldval=str(self.pt_dbstate.__dict__[attr])
                if oldval != newval:
                    if attr == "xraycmp":
                        daybook_module.xrayDates(self, newval)
                    elif attr == "periocmp":
                        daybook_module.perioDates(self, newval)
                    elif attr not in fieldsToExclude:
                        if attr != "memo" or oldval.replace(chr(13), "") != newval:
                            #--ok - windows line ends from old DB were
                            #-- creating an issue
                            #-- memo was reporting that update had occurred.
                            changes.append(attr)

            return changes
        else: #this should NEVER happen!!!
            self.advise( "POTENTIALLY SERIOUS CONFUSION PROBLEM"+
                        " WITH PT RECORDS %d and %d"%\
                        (self.pt.serialno, self.pt_dbstate.serialno), 2)
            return changes

    def save_changes(self, leavingRecord=False):
        '''
        updates the database when the save is requested
        '''
        if self.pt.serialno == 0:
            self.advise("no patient selected", 1)
            return
        if self.editPageVisited:
            #-- only make changes if user has visited this tab
            self.apply_editpage_changes()
        if self.pt.HIDDENNOTES != []:
            #-- hidden notes is
            #-- treatment codes... money, printing etc..
            print "saving hiddennotes"
            patient_write_changes.toNotes(self.pt.serialno, self.pt.HIDDENNOTES)
            self.pt.clearHiddenNotes()

        daybook_module.updateDaybook(self)
        uc=self.unsavedChanges()
        if uc != []:
            print "changes made to patient atttributes..... updating database"

            result=patient_write_changes.all_changes(self.pt, uc,
            self.pt_dbstate.estimates)

            if result: #True if sucessful
                if not leavingRecord and "estimates" in uc:
                    #-- necessary to get index numbers for estimate data types
                    self.pt.getEsts()
                    if self.ui.tabWidget.currentIndex() == 7:
                        self.load_newEstPage()
            
                self.pt_dbstate=copy.deepcopy(self.pt)
                message="Sucessfully altered the following items<ul>"
                for item in uc:
                    message+="<li>%s</li>"%str(item)
                self.advise(message+"</ul>", 1)
            else:
                self.advise("Error applying changes... please retry", 2)
                print "error saving changes to record %s"%self.pt.serialno,
                print result, str(uc)

        #--convert to python datatype
        newnote=str(self.ui.notesEnter_textEdit.toPlainText().toAscii())
        if len(newnote)>0:
            newnote=newnote.replace('"', "'")
            #--because " knackers my sql queries!!
            notelines=[]
            #-- silly database stores note lines as strings of max 80chrs
            while len(newnote)>79:
                if "\n" in newnote[:79]:
                    pos=newnote[:79].rindex("\n")
                elif " " in newnote[:79]:
                    pos=newnote[:79].rindex(" ")
                    #--try to split nicely
                else:
                    pos=79
                    #--ok, no option
                notelines.append(newnote[:pos])
                newnote=newnote[pos+1:]
            notelines.append(newnote)
            print "NOTES UPDATE\n%s"%notelines
            result= patient_write_changes.toNotes(self.pt.serialno, notelines)
            #--sucessful write to db?
            if result != -1:
                #--result will be a "line number" or -1 if unsucessful write
                self.ui.notesEnter_textEdit.setText("")
                self.pt.getNotesTuple()
                #--reload the notes
                self.ui.notesSummary_textBrowser.setHtml(notes.notes(
                                                            self.pt.notestuple))
                self.ui.notesSummary_textBrowser.scrollToAnchor("anchor")
                if self.ui.tabWidget.currentIndex() == 5:
                    self.updateNotesPage()
            else:
                #--exception writing to db
                self.advise("error writing notes to database... sorry!", 2)
        self.updateDetails()


    def enableEdit(self, arg=True):
        '''
        disable/enable widgets "en mass" when no patient loaded
        '''
        for widg in (self.ui.printEst_pushButton,
        self.ui.printAccount_pushButton,
        self.ui.relatedpts_pushButton,
        self.ui.saveButton,
        self.ui.phraseBook_pushButton,
        self.ui.exampushButton,
        self.ui.medNotes_pushButton,
        self.ui.charge_pushButton,
        self.ui.printGP17_pushButton,
        self.ui.newBPE_pushButton,
        self.ui.hygWizard_pushButton,
        self.ui.notesEnter_textEdit,
        self.ui.memos_pushButton,
        self.ui.printAppt_pushButton):

            widg.setEnabled(arg)

        for i in (0, 1, 2, 5, 6, 7, 8, 9):
            if self.ui.tabWidget.isTabEnabled(i) != arg:
                self.ui.tabWidget.setTabEnabled(i, arg)
        if arg == True and "N" in self.pt.cset:
            #-- show NHS form printing button
            self.ui.NHSadmin_groupBox.show()
        else:
            self.ui.NHSadmin_groupBox.hide()

    def setValidators(self):
        '''
        add user Input validators to some existing widgets
        '''
        self.ui.dupReceiptDate_lineEdit.setInputMask("00/00/0000")

    def changeDB(self):
        '''
        a dialog to user a different database (or backup server etc...)
        '''
        if not permissions.granted(self):
            return

        def togglePassword(e):
            if not dl.checkBox.checkState():
                dl.password_lineEdit.setEchoMode(QtGui.QLineEdit.Password)
            else:
                dl.password_lineEdit.setEchoMode(QtGui.QLineEdit.Normal)
        Dialog = QtGui.QDialog(self)
        dl = Ui_changeDatabase.Ui_Dialog()
        dl.setupUi(Dialog)
        QtCore.QObject.connect(dl.checkBox, QtCore.SIGNAL("stateChanged(int)"),
                                                                togglePassword)
        if Dialog.exec_():
            from openmolar import connect
            connect.myDb=str(dl.database_lineEdit.text())
            connect.myHost=str(dl.host_lineEdit.text())
            connect.myPassword=str(dl.password_lineEdit.text())
            connect.myUser=str(dl.user_lineEdit.text())
            try:
                connect.mainconnection.close()
                connect.forumconnection.close()
                self.advise("Applying changes", 1)
                localsettings.initiate()
            except Exception, e:
                print "unable to close existing connection!"
                print e


################################ FEES #########################################
    def charge_pushButtonClicked(self):
        '''
        user is raising a charge using the button on the clinical summary page
        '''
        fees_module.raiseACharge(self)
        
    def takePayment_pushButton_clicked(self):
        '''
        user has clicked to take a payment
        '''
        fees_module.takePayment(self)
    
    def feeSearch_lineEdit_edited(self):
        '''
        user has entered a field to search for in the fees table
        '''
        fees_module.newFeeSearch(self)
        
    def feeSearch_pushButton_clicked(self):
        '''
        user is searching fees
        '''
        fees_module.feeSearch(self)

    def nhsRegs_pushButton_clicked(self):
        '''
        user should be offered a PDF of the current regulations
        '''
        fees_module.nhsRegsPDF(self)
        
    def chooseFeescale_comboBox_changed(self, arg):
        '''
        receives signals from the choose feescale combobox
        '''
        fees_module.chooseFeescale(self,arg)

    def feeItems_comboBox_changed(self, arg):
        '''
        receives signals from the choose feescale Items combobox
        '''
        fees_module.chooseFeeItemDisplay(self, arg)
    
    def feeExpand_radiobuttons_clicked(self):
        '''
        the expand or collapse radio buttons on the fees page
        have been clicked.
        '''
        fees_module.expandFees(self)
    
    def feesColumn_comboBox_changed(self, arg):
        '''
        expand columns within the fees table
        '''
        fees_module.expandFeeColumns(self,arg)
    
    def newCourse_pushButton_clicked(self):
        '''
        user has clicked on the new course button
        '''
        course_module.newCourseNeeded(self)
    
    def closeTx_pushButton_clicked(self):
        '''
        user has clicked on close course button
        '''
        course_module.closeCourse(self)

    def estWidget_applyFeeNowCalled(self,amount,coursetype=None):
        '''
        est Widget has emitted a signal to apply a fee.
        '''
        fees_module.applyFeeNow(self,amount,coursetype)

    def showExamDialog(self):
        '''
        call a smart dialog which will perform an exam on the current patient
        '''
        examdialog.perform(self)
    
    def showHygDialog(self):
        '''
        call a smart dialog which will perform hygenist treatment 
        on the current patient
        '''
        perio_tx_dialog.perform(self)

    def addXrayItems(self):
        '''
        add Xray items to the treatment plan
        '''
        add_tx_to_plan.xrayAdd(self)

    def addPerioItems(self):
        '''
        add Perio items to the treatment plan
        '''
        add_tx_to_plan.perioAdd(self)

    def addOtherItems(self):
        '''
        add 'Other' items to the treatment plan
        '''
        add_tx_to_plan.otherAdd(self)
        
    def addCustomItem(self):
        '''
        add custom items to the treatment plan
        '''
        add_tx_to_plan.customAdd(self)

    def offerTreatmentItems(self,arg):
        '''
        offers treatment items passed by argument
        '''
        Dialog = QtGui.QDialog(self)
        dl = addTreat.treatment(Dialog,arg,self.pt)
        result =  dl.getInput()
        return result

    def toothTreatAdd(self, tooth, properties):
        '''
        properties for tooth has changed.
        '''
        add_tx_to_plan.chartAdd(self, tooth, properties)

    def planChartWidget_completed(self,arg):
        '''
        called when double clicking on a tooth in the plan chart
        '''
        complete_tx.chartComplete(self,arg)
        
    def estwidget_completeItem(self, txtype):
        '''
        estwidget has sent a signal that an item is marked as completed.
        '''
        complete_tx.estwidg_complete(self, txtype)
        
    def estwidget_unCompleteItem(self,txtype):
        '''
        estwidget has sent a signal that a previous completed item needs 
        reversing
        '''
        complete_tx.estwidg_unComplete(self, txtype)
        
    def estwidget_deleteTxItem(self,pl_cmp,txtype):
        '''
        estWidget has removed an item from the estimates.
        (user clicked on the delete button)
        '''
        ##TODO - I have removed this functionality due to estimate errors.
        print "DO YOU WANT TO ADD FUNCTIONALITY TO estwidget_deleteTxItem??"
        return
        
    def planItemClicked(self,item,col):
        '''
        user has double clicked on the treatment plan tree
        col is of no importance as I only have 1 column
        '''
        manipulate_tx_plan.itemChosen(self, item, "pl")

    def cmpItemClicked(self,item,col):
        '''
        user has double clicked on the treatment competled tree
        col is of no importance - tree widget has only 1 column.
        '''
        manipulate_tx_plan.itemChosen(self, item, "cmp")

    def makeBadDebt_clicked(self):
        '''
        user has decided to reclassify a patient as a "bad debt" patient
        '''
        fees_module.makeBadDebt(self)
    
    def loadAccountsTable_clicked(self):
        '''
        button has been pressed to load the accounts table
        '''
        fees_module.populateAccountsTable(self)

    def forum_treeWidget_selectionChanged(self):
        '''
        user has selected an item in the forum
        '''
        forum_gui_module.forumItemSelected(self) 
    
    def forumNewTopic_clicked(self):
        '''
        user has called for a new topic in the forum
        '''
        forum_gui_module.forumNewTopic(self)
    
    def forumDeleteItem_clicked(self):
        '''
        user is deleting an item from the forum
        '''
        forum_gui_module.forumDeleteItem(self)
        
    def forumReply_clicked(self):
        '''
        user is replying to an existing topic
        '''
        forum_gui_module.forumReply(self)
    
    def checkForNewForumPosts(self):
        '''
        ran in a thread - checks for messages
        '''
        forum_gui_module.checkForNewForumPosts(self)

    def contractTab_navigated(self,i): 
        '''
        the contract tab is changing
        '''
        contract_gui_module.handle_ContractTab(self)

    def dnt1comboBox_clicked(self, qstring):
        '''
        user is changing dnt1
        '''
        contract_gui_module.changeContractedDentist(self,qstring)

    def dnt2comboBox_clicked(self, qstring):
        '''
        user is changing dnt1
        '''
        contract_gui_module.changeCourseDentist(self,qstring)
    
    def cseType_comboBox_clicked(self, qstring):
        '''
        user is changing the course type
        '''
        contract_gui_module.changeCourseType(self,qstring)

    def editNHS_pushButton_clicked(self):
        '''
        edit the NHS contract
        '''
        contract_gui_module.editNHScontract(self)

    def editPriv_pushButton_clicked(self):
        '''
        edit Private contract
        '''
        contract_gui_module.editPrivateContract(self)

    def nhsclaims_pushButton_clicked(self):
        '''
        edit Private contract
        '''
        self.nhsClaimsShortcut()
    
    def editHDP_pushButton_clicked(self):
        '''
        edit the HDP contract
        '''
        contract_gui_module.editHDPcontract(self)
    
    def editRegDent_pushButton_clicked(self):
        '''
        edit the "other Dentist" contract
        '''
        contract_gui_module.editOtherContract(self)
    
    
###############################################################################
########          ATTENTION NEEDED HERE         ###############################
         
    def recalculateEstimate(self, ALL=True):
        ####################todo - -move this to the estimates module.....
        ####################see NEW function below
        '''
        Adds ALL tooth items to the estimate.
        prompts the user to confirm tooth treatment fees
        '''
        ##TODO - redesign this!!!
        self.ui.planChartWidget.update()

        Dialog = QtGui.QDialog(self)
        dl = addToothTreat.treatment(Dialog,self.pt.cset)
        if ALL == False:
            dl.itemsPerTooth(tooth, item)
        else:
            treatmentDict = estimates.toothTreatDict(self.pt)
            dl.setItems(treatmentDict["pl"],)
            dl.setItems(treatmentDict["cmp"],)

        dl.showItems()

        chosen = dl.getInput()

        if chosen:
            if self.pt.dnt2 != 0:
                dent = self.pt.dnt2
            else:
                dent = self.pt.dnt1

            for treat in chosen:
                #-- treat[0]= the tooth name
                #-- treat[1] = item code
                #-- treat[2]= description
                #-- treat[3]= adjusted fee
                #-- treat[4]=adjusted ptfee

                self.pt.addToEstimate(1, treat[1], treat[2], treat[3],
                treat[4], dent, self.pt.cset, treat[0])

            self.load_newEstPage()
            self.load_treatTrees()

    def NEWrecalculateEstimate(self):
        '''
        Adds ALL tooth items to the estimate.
        prompts the user to confirm tooth treatment fees
        '''
        ##TODO - redesign this!!!
        estimates.abandon_estimate(self.pt)
        if estimates.calculate_estimate(self.pt):
            self.load_newEstPage()
            self.load_treatTrees()

################################################################################



















def main(arg):
    #-- app required for polite shutdown
    if not localsettings.successful_login and not "neil" in os.getcwd():
        print "unable to run... no login"
        sys.exit()

    app = QtGui.QApplication(arg)
    #-- user could easily play with this code and avoid login...
    #--the app would however, not have initialised.
    mainWindow=openmolarGui()
    mainWindow.app=app
    mainWindow.show()

    if __name__ != "__main__":
        #--don't maximise the window for dev purposes - I like to see
        #--all the error messages in a terminal ;).
        mainWindow.setWindowState(QtCore.Qt.WindowMaximized)
    sys.exit(app.exec_())

if __name__ == "__main__":
    print "dev mode"
    localsettings.initiate()

    print "Qt Version: ", QtCore.QT_VERSION_STR
    print "PyQt Version: ", QtCore.PYQT_VERSION_STR
    main(sys.argv)
