# Date 2022/02/26 
# Ultra Crappy DL3000 GUI based on DL3000 GUI based on Colin O'Flynn's and kudl4t4's github repository by Justin Richards
# Colin O'Flynn's - https://github.com/colinoflynn/DL3000-gui  https://www.youtube.com/watch?v=Mwu7hfbYQjk
# kudl4t4 - https://github.com/kudl4t4/RIGOL-DL3000-GUI
#
# Python 3.10.0
# pip install pyside6
# pip install PyQt5 
# pip install pyqtgraph
# pip install pyvisa-py
# pip install matplotlib

#"TCPIP0::192.168.1.60::INSTR"  <- If using TCPIP then point browser to your IP address and it will reveal the "VISA TCP/IP String"
#"USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR"
# ToDo

CONNECTSTRING = "TCPIP0::172.16.0.135::INSTR"

import os
import sys
import time

import math
import matplotlib.pyplot as plt

import numpy as np

from PySide6.QtCore import *
from PySide6.QtGui import *

from PyQt5.QtWidgets import * #QApplication, QWidget, QMainWindow, QPushButton, QMessageBox, QBoxLayout
from PyQt5 import QtCore, QtGui

try:
    import pyqtgraph as pg
    import pyqtgraph.parametertree.parameterTypes as pTypes
    from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem, registerParameterType
except ImportError:
    print ("Install pyqtgraph from http://www.pyqtgraph.org")
    raise

from dl3000 import DL3000

class GraphWidget(QWidget):
    """
    This GraphWidget holds a pyqtgraph PlotWidget, and adds a toolbar for the user to control it.
    """

    def __init__(self):
        #pg.setConfigOption('background', 'w')
        #pg.setConfigOption('foreground', 'k')

        QWidget.__init__(self)
        layout = QVBoxLayout()

        self.pw = pg.PlotWidget(name="Power Trace View")
        self.pw.setLabel('top', 'Power Trace View')
        self.pw.setLabel('bottom', 'Samples')
        self.pw.setLabel('left', 'Data')
        vb = self.pw.getPlotItem().getViewBox()
        vb.setMouseMode(vb.RectMode)

        layout.addWidget(self.pw)

        self.setLayout(layout)

        self.setDefaults()

    def setDefaults(self):
        self.defaultYRange = None

    def VBStateChanged(self, obj):
        """Called when ViewBox state changes, used to sync X/Y AutoScale buttons"""
        arStatus = self.pw.getPlotItem().getViewBox().autoRangeEnabled()

        #X Axis
        if arStatus[0]:
            self.XLockedAction.setChecked(False)
        else:
            self.XLockedAction.setChecked(True)

        #Y Axis
        if arStatus[1]:
            self.YLockedAction.setChecked(False)
        else:
            self.YLockedAction.setChecked(True)

    def VBXRangeChanged(self, vb, range):
        """Called when X-Range changed"""
        self.xRangeChanged.emit(range[0], range[1])

    def xRange(self):
        """Returns the X-Range"""
        return self.pw.getPlotItem().getViewBox().viewRange()[0]

    def YDefault(self, extraarg=None):
        """Copy default Y range axis to active view"""
        if self.defaultYRange is not None:
            self.setYRange(self.defaultYRange[0], self.defaultYRange[1])

    def setDefaultYRange(self, lower, upper):
        """Set default Y-Axis range, for when user clicks default button"""
        self.defaultYRange = [lower, upper]

    def setXRange(self, lower, upper):
        """Set the X Axis to extend from lower to upper"""
        self.pw.getPlotItem().getViewBox().setXRange(lower, upper)

    def setYRange(self, lower, upper):
        """Set the Y Axis to extend from lower to upper"""
        self.pw.getPlotItem().getViewBox().setYRange(lower, upper)

    def xAutoScale(self, enabled):
        """Auto-fit X axis to data"""
        vb = self.pw.getPlotItem().getViewBox()
        bounds = vb.childrenBoundingRect(None)
        vb.setXRange(bounds.left(), bounds.right())

    def yAutoScale(self, enabled):
        """Auto-fit Y axis to data"""
        vb = self.pw.getPlotItem().getViewBox()
        bounds = vb.childrenBoundingRect(None)
        vb.setYRange(bounds.top(), bounds.bottom())

    def xLocked(self, enabled):
        """Lock X axis, such it doesn't change with new data"""
        self.pw.getPlotItem().getViewBox().enableAutoRange(pg.ViewBox.XAxis, ~enabled)

    def yLocked(self, enabled):
        """Lock Y axis, such it doesn't change with new data"""
        self.pw.getPlotItem().getViewBox().enableAutoRange(pg.ViewBox.YAxis, ~enabled)

    def passTrace(self, trace, startoffset=0, pen='b', clear=True):
        if clear:
            self.pw.clear()
        xaxis = range(startoffset, len(trace)+startoffset)
        self.pw.plot(xaxis, trace, pen=pen)

class DL3000GUI(QMainWindow):

    def __init__(self):
        super(DL3000GUI, self).__init__()
        self.setWindowIcon(QtGui.QIcon('frog1.bmp'))
        wid = QWidget()
        layout = QVBoxLayout()
        self.drawDone = False

        settings = QSettings()

        constr = settings.value('constring')
        if constr is None: constr = CONNECTSTRING

        self.constr = QLineEdit(constr)
        self.conpb = QPushButton("Connect")
        self.conpb.clicked.connect(self.tryConnect)

        self.dispb = QPushButton("Disconnect")
        self.dispb.clicked.connect(self.dis)

        self.loggingPushButton = QPushButton("Log On/Off")
        self.loggingPushButton.setCheckable(True)
        #self.loggingPushButton.clicked.connect(self.setLogging)

        self.cbNumDisplays = QSpinBox()
        self.cbNumDisplays.setMinimum(1)
        self.cbNumDisplays.setMaximum(3)
        self.cbNumDisplays.setValue(3)

        self.sbReadingsInterval = QSpinBox()
        self.sbReadingsInterval.setAccelerated(True)
        self.sbReadingsInterval.setMinimum(1)
        self.sbReadingsInterval.setMaximum(600000)         #600 sec 10mins
        self.sbReadingsInterval.setValue(10000)
        self.sbReadingsInterval.setSuffix(" mS")
        self.sbReadingsInterval.setPrefix("Update ")
        self.sbReadingsInterval.valueChanged.connect(lambda x: self.setInterval( x))
        
        self.pbPauseTimer = QPushButton("Pause Timer")
        self.pbPauseTimer.setCheckable(True)
        self.pbPauseTimer.clicked.connect(self.tryPauseTimer)

        self.leTemp = QLineEdit("---")
        self.leTemp.setObjectName("leTemp")
        
        self.leModel = QLineEdit("---")
        self.leModel.setObjectName("leModel")
     
        self.layoutcon = QHBoxLayout()
        self.layoutcon.addWidget(QLabel("Connect String:"))
        self.layoutcon.addWidget(self.constr)
        self.layoutcon.addWidget(self.conpb)
        self.layoutcon.addWidget(self.dispb)
        self.layoutcon.addWidget(self.cbNumDisplays)
        self.setGeometry(30, 60, 500, 100)

        layout.addLayout(self.layoutcon)

        self.layoutcon2 = QHBoxLayout()
        #self.layoutcon2.addWidget(QLabel("Connect String:"))
        layout.addLayout(self.layoutcon2)


        self.graphlist = []
        self.graphsettings = []
        self.chLineEdits = []
        self.chConfig = []
        
        self.vdata = [[],[],[]]
        self.idata = [[],[],[]]
        self.pdata = [[],[],[]]
        self.edata = [[],[],[]]
        
        self.filename = ""
        self.startLogTime = time.time() 

        self.degree = 0
        self.temperatureWarningToggle = False
        
        # suspect it is 60mS is the fastest it can up date
        #pos slope 0 - 30V ~ 105mS
        #neg slope 30 - 0V ~ 355mS
        
        wid.setLayout(layout)

        self.setCentralWidget(wid)
        self.setWindowTitle("DL3000 GUI")

    def addGraphs(self, graphnum):
        layout = self.centralWidget().layout()
        gb = QGroupBox()

        self.gridLayoutChannel = QGridLayout()

        self.lblPoint = QLabel()
        self.lblPoint.setObjectName("lblPoint")
        self.gridLayoutChannel.addWidget(self.lblPoint, 0, 2, 1, 1)

        self.graphsettings.append({"channel":"CH%d"%(graphnum+1), "points":4096})

        self.vdata.append([-1])
        self.idata.append([-1])
        self.pdata.append([-1])
        self.edata.append([-1])

        self.sbPoints = QSpinBox()
        self.sbPoints.setMinimum(10)
        self.sbPoints.setMaximum(30000)
        self.sbPoints.setObjectName("sbPoints")
        self.sbPoints.setValue(self.graphsettings[-1]["points"])
        self.sbPoints.valueChanged.connect(lambda x: self.setPoints(graphnum, x))
        self.gridLayoutChannel.addWidget(self.sbPoints, 0, 3, 1, 1)

        self.pbPlotV = QPushButton()
        self.pbPlotV.setObjectName("pbPlotV")
        self.pbPlotV.setCheckable(True)
        self.pbPlotV.setChecked(True)
        self.gridLayoutChannel.addWidget(self.pbPlotV, 1, 1, 1, 1)

        self.pbPlotI = QPushButton()
        self.pbPlotI.setObjectName("pbPlotI")
        self.pbPlotI.setCheckable(True)
        self.gridLayoutChannel.addWidget(self.pbPlotI, 1, 2, 1, 1)

        self.pbPlotE = QPushButton()
        self.pbPlotE.setObjectName("pbPlotE")
        self.pbPlotE.setCheckable(True)
        self.gridLayoutChannel.addWidget(self.pbPlotE, 1, 0, 1, 1)

 
        self.pbPlotP = QPushButton()
        self.pbPlotP.setObjectName("pbPlotP")
        self.pbPlotP.setCheckable(True)
        self.gridLayoutChannel.addWidget(self.pbPlotP, 1, 3, 1, 1)

        self.graphsettings[-1]["venabled"] = self.pbPlotV
        self.graphsettings[-1]["ienabled"] = self.pbPlotI
        self.graphsettings[-1]["penabled"] = self.pbPlotP
        self.graphsettings[-1]["eenabled"] = self.pbPlotE

        self.pbEStop = QPushButton()
        self.pbEStop.setObjectName("pbEStop")
        self.pbEStop.clicked.connect(lambda : self.eStop(graphnum))
        self.gridLayoutChannel.addWidget(self.pbEStop, 0, 0, 1, 1)
        
        self.pbPause = QPushButton()
        self.pbPause.setObjectName("pbPause")
        self.pbPause.setCheckable(True)
        self.pbPause.clicked.connect(lambda : self.tryPausePlot(graphnum))
        self.gridLayoutChannel.addWidget(self.pbPause, 2, 0, 1, 1)
        self.graphsettings[-1]["pauseenabled"] = self.pbPause
        
        self.pbClearPlot = QPushButton()
        self.pbClearPlot.setObjectName("pbClearPlot")        
        self.pbClearPlot.clicked.connect(lambda : self.clearPlot(graphnum))
        self.gridLayoutChannel.addWidget(self.pbClearPlot, 2, 1, 1, 1)
        
        if(graphnum == 0):
            self.lblState = QLabel()
            self.lblState.setObjectName("lblState")
            self.gridLayoutChannel.addWidget(self.lblState, 3, 0, 1, 1)
            
            self.cbState = QComboBox()
            self.cbState.setObjectName("cbState")
            self.cbState.addItem("ON")
            self.cbState.addItem("OFF")
            self.cbState.setCurrentText(self.inst.getState())

            self.sbVolts = QDoubleSpinBox()
            self.sbVolts.setAccelerated(True)
            self.sbVolts.setSuffix(" [V]")
            self.sbVolts.setDecimals(3)

            self.sbVolts.setMaximum(40)
            self.sbVolts.setSingleStep(0.01)
            self.sbVolts.setObjectName("sbVolts")
            self.sbVolts.setValue(float(eval(self.cbBattery.currentText())["VoltsCut"])) ###("CH%d"% (graphnum+1)))

            self.sbCurrent = QDoubleSpinBox()
            self.sbCurrent.setAccelerated(True)
            self.sbCurrent.setSuffix(" [A]")
            self.sbCurrent.setDecimals(3)
            self.sbCurrent.setMaximum(40)
            self.sbCurrent.setSingleStep(0.01)
            self.sbCurrent.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
            self.sbCurrent.setObjectName("sbCurrent")
            self.sbCurrent.setValue(self.inst.getCurrImmediate())#self.inst.getCurr()) ###"CH%d"% (graphnum+1)))
            #self.sbCurrent.setValue(float(eval(self.cbBattery.currentText())["CurrLoad"]))
            #self.sbCurrent.valueChanged.connect(lambda x: self.setCurr(graphnum, x))

            self.lblVoltage = QLabel()
            self.lblVoltage.setObjectName("lblVoltage")
            self.gridLayoutChannel.addWidget(self.lblVoltage, 4, 0, 1, 1)

            self.leState = QLineEdit()
            self.leState.setObjectName("leState")

            self.leVolts = QLineEdit()
            self.leVolts.setObjectName("leVolts")

            self.leCurrent = QLineEdit()
            self.leCurrent.setObjectName("leCurrent")

            self.lePower = QLineEdit()
            self.lePower.setObjectName("lePower")
            
            self.leEnergy = QLineEdit()
            self.leEnergy.setObjectName("leEnergy")
            
            self.leCapacity = QLineEdit()
            self.leCapacity.setObjectName("leCapacity")

            self.leDischargeTime = QLineEdit()
            self.leDischargeTime.setObjectName("leDischargeTime")
            
            self.chLineEdits.append({"state":self.leState,"volts":self.leVolts,"current":self.leCurrent,"power":self.lePower,"energy":self.leEnergy,"capacity":self.leCapacity, "dischargetime":self.leDischargeTime})
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["state"], 3, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["volts"], 4, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["current"], 5, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["power"], 6, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["energy"], 7, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["capacity"], 8, 1, 1, 1)
            self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["dischargetime"], 9, 1, 1, 1)
            
            self.lblCurr = QLabel()
            self.lblCurr.setObjectName("lblCurr")
            self.gridLayoutChannel.addWidget(self.lblCurr, 5, 0, 1, 1)

            self.pbSet = QPushButton()
            self.pbSet.setObjectName("pbSet")
            self.gridLayoutChannel.addWidget(self.pbSet, 2, 2, 1, 2)
            self.pbSet.clicked.connect(lambda : self.setupChannel(graphnum))

            self.lblPower = QLabel()
            self.lblPower.setObjectName("lblPower")
            self.gridLayoutChannel.addWidget(self.lblPower, 6, 0, 1, 1)

            self.lblEnergy = QLabel()
            self.lblEnergy.setObjectName("lblEnergy")
            self.gridLayoutChannel.addWidget(self.lblEnergy, 7, 0, 1, 1)

            self.lblCapacity = QLabel()
            self.lblCapacity.setObjectName("lblCapacity")
            self.gridLayoutChannel.addWidget(self.lblCapacity, 8, 0, 1, 1)

            self.lblDischargeTime = QLabel()
            self.lblDischargeTime.setObjectName("lblDischargeTime")
            self.gridLayoutChannel.addWidget(self.lblDischargeTime, 9, 0, 1, 1)


            self.ckState = QCheckBox()
            self.ckState.setObjectName("ckState")
            self.lblVoltCut = QLabel()
            self.lblVoltCut.setObjectName("lblVoltCut")
            self.gridLayoutChannel.addWidget(self.lblVoltCut, 6, 2, 1, 1)

            self.ckCurrent = QCheckBox()
            self.ckCurrent.setObjectName("ckCurrent")
            self.ckRun = QCheckBox()
            self.ckRun.setObjectName("ckRun")

            self.chConfig.append({"ckState":self.ckState,"ckCurrent":self.ckCurrent,"ckRun":self.ckRun, \
            "cbState":self.cbState,"sbVolts":self.sbVolts,"sbCurrent":self.sbCurrent,"pbPause":self.pbPause,"pbClearPlot":self.pbClearPlot})
            
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["pbPause"], 2, 0, 1, 1)
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["pbClearPlot"], 2, 1, 1, 1)
            
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckState"], 3, 2, 1, 1)
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckCurrent"], 4, 2, 1, 1)
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckRun"], 7, 2, 1, 1)
            
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["cbState"], 3, 3, 1, 1)        
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["sbVolts"], 6, 3, 1, 1)        
            self.gridLayoutChannel.addWidget(self.chConfig[-1]["sbCurrent"], 4, 3, 1, 1)


        gb.setLayout(self.gridLayoutChannel)
        self.gridLayoutChannel.setColumnStretch(0, 1)
        self.gridLayoutChannel.setColumnStretch(1, 1)
        self.gridLayoutChannel.setColumnStretch(2, 1)
        self.gridLayoutChannel.setColumnStretch(3, 1)
        self.gridLayoutChannel.setColumnStretch(4, 10)
        layout.addWidget(gb)

        self.retranslateUi(QMainWindow)

        self.graphlist.append(GraphWidget())
        self.gridLayoutChannel.addWidget(self.graphlist[-1], 0, 4,9,1)
        

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        self.cbState.setItemText(0, _translate("MainWindow", "ON"))
        self.cbState.setItemText(1, _translate("MainWindow", "OFF"))
        self.lblState.setText(_translate("MainWindow", "State:"))
        self.leVolts.setText(_translate("MainWindow", "---"))
        self.ckState.setText(_translate("MainWindow", "State: "))
        self.pbEStop.setText(_translate("MainWindow", "E STOP"))
        self.lePower.setText(_translate("MainWindow", "---"))
        self.leCurrent.setText(_translate("MainWindow", "---"))
        self.lblCurr.setText(_translate("MainWindow", "Current [A]:"))
        self.lblVoltage.setText(_translate("MainWindow", "Voltage [V]:"))
        self.pbSet.setText(_translate("MainWindow", "SET"))
        self.pbPlotE.setText(_translate("MainWindow", "Plot E"))
        self.pbPlotI.setText(_translate("MainWindow", "Plot I"))
        self.leState.setText(_translate("MainWindow", "---"))
        self.lblPoint.setText(_translate("MainWindow", "Points"))
        self.lblPower.setText(_translate("MainWindow", "Power [W]:"))
        self.lblEnergy.setText(_translate("MainWindow", "Energy [Wh]:"))
        self.lblCapacity.setText(_translate("MainWindow", "Capacity [mAh]:"))
        self.lblDischargeTime.setText(_translate("MainWindow", "Dis Time [HMS]:"))
        
        
        self.pbPlotV.setText(_translate("MainWindow", "Plot V"))
        self.pbPause.setText(_translate("MainWindow", "PAUSE PLOT"))
        self.pbClearPlot.setText(_translate("MainWindow", "CLEAR PLOT"))
        self.pbPlotP.setText(_translate("MainWindow", "Plot P"))
        self.lblVoltCut.setText(_translate("MainWindow", "Volt Cutoff [V]:"))
        self.ckCurrent.setText(_translate("MainWindow", "Current [I]:"))
        self.ckRun.setText(_translate("MainWindow", "Run"))
        

    def clearPlot(self,graphnum):
        self.vdata[graphnum] = []
        self.idata[graphnum] = []
        self.pdata[graphnum] = []
        self.edata[graphnum] = []
        
    def tryPauseTimer(self):
        if(self.pbPauseTimer.isChecked()):
            self.readtimer.stop()
        else:
            self.readtimer.start()

    def dis(self): #disconnect
        self.readtimer.stop()
        self.inst.dis()

    def tryConnect(self):
        constr = self.constr.text()
        QSettings().setValue('constring', constr)

        self.inst = DL3000()
        self.inst.conn(constr)
        self.leModel.setText(self.inst.identify()["model"])
        
        self.inst.reset()
        
        self.cbBattery = QComboBox()
        self.cbBattery.setObjectName("cbBattery")
        self.cbBattery.addItem('{"Type":"12v 7Ah Pb","VoltsCut":11.8,"CurrLoad":3.5}')
        self.cbBattery.addItem('{"Type":"Motorola 7.4v 1.7Ah 12.6Wh Li-Ion","VoltsCut":7,"CurrLoad":0.850}')
        self.cbBattery.addItem('{"Type":"12v 24Ah Pb","VoltsCut":11.8,"CurrLoad":12}')
        self.cbBattery.activated.connect(lambda x: self.setBattery(x))

        self.cbSourceFunction = QComboBox()
        self.cbSourceFunction.setObjectName("cbSourceFunction")
        self.cbSourceFunction.addItem("CURRENT")
        self.cbSourceFunction.addItem("RESISTANCE")
        self.cbSourceFunction.addItem("VOLTAGE")
        self.cbSourceFunction.addItem("POWER")
        self.cbSourceFunction.activated.connect(lambda x: self.setSourceFunction(x))

        self.cbSourceFunctionMode = QComboBox()
        self.cbSourceFunctionMode.setObjectName("cbSourceFunctionMode")
        self.cbSourceFunctionMode.addItem("BATTERY")
        self.cbSourceFunctionMode.addItem("FIXED")
        self.cbSourceFunctionMode.addItem("LIST")
        self.cbSourceFunctionMode.addItem("WAVE")
        self.cbSourceFunctionMode.activated.connect(lambda x: self.setSourceFunctionMode(x))

        
        self.layoutcon.addWidget(self.loggingPushButton)
        self.layoutcon.addWidget(self.sbReadingsInterval)
        self.layoutcon.addWidget(self.pbPauseTimer)
        self.layoutcon.addWidget(QLabel("Temperature:"))
        self.layoutcon.addWidget(self.leTemp)
        self.layoutcon.addWidget(QLabel("Model:"))
        self.layoutcon.addWidget(self.leModel)
        
        self.layoutcon2.addWidget(QLabel("Battery:"))
        self.layoutcon2.addWidget(self.cbBattery)

        self.layoutcon2.addWidget(QLabel("Battery Ref:"))
        self.leBattRef = QLineEdit("---")
        self.layoutcon2.addWidget(self.leBattRef)

        self.layoutcon2.addWidget(QLabel("Source Function:"))
        self.layoutcon2.addWidget(self.cbSourceFunction)

        self.layoutcon2.addWidget(QLabel("Source Function Mode:"))
        self.layoutcon2.addWidget(self.cbSourceFunctionMode)
        
        
        
        #self.inst.setCurrRangeLow()
 
 
 
        if self.drawDone == False:
            #self.addGraphs(self.cbNumDisplays.value()) # <- it can not be done this way.  It results in all functions refering to CH3 only
            for i in range (0,self.cbNumDisplays.value()):
                self.addGraphs(i)
            self.cbNumDisplays.setEnabled(False)
            self.resize(1200,900)
            self.drawDone = True

        self.readtimer = QtCore.QTimer()
        self.readtimer.setInterval(self.sbReadingsInterval.value())

        self.readtimer.timeout.connect(self.updateReadings)
        self.readtimer.start()

        self.readDegCtimer = QtCore.QTimer()
        self.readDegCtimer.setInterval(1000)

        self.readDegCtimer.timeout.connect(self.updateSystTemperature)
        self.readDegCtimer.start()

    def setInterval(self, interval):
        self.readtimer.setInterval(self.sbReadingsInterval.value())

    def eStop(self, graphnum):
        self.inst.setState("OFF")

    def setBattery(self,x):#triggered with drop down box selection
        self.sbVolts.setValue(float(eval(self.cbBattery.currentText())["VoltsCut"]))
        self.sbCurrent.setValue(float(eval(self.cbBattery.currentText())["CurrLoad"]))
        
    def setSourceFunction(self,x):#triggered with drop down box selection
        self.inst.setState("OFF") #if user makes any changes to function, best to turn off the load
        self.inst.setSourceFunc(self.cbSourceFunction.currentText())
    
        if (self.cbSourceFunction.currentText() == "CURRENT"):
            self.inst.setCurrLevelImmediate("0.01")
        
        if (self.cbSourceFunction.currentText() == "RESISTANCE"):
            self.inst.setResistanceLevelImmediate("1000")
            
        if (self.cbSourceFunction.currentText() == "VOLTAGE"):
            self.inst.setVoltageLevelImmediate("22")
        
        if (self.cbSourceFunction.currentText() == "POWER"):
            self.inst.setPowerLevelImmediate("0.01")

   

    def setSourceFunctionMode(self,x):#triggered with drop down box selection
        self.inst.setSourceFuncMode(self.cbSourceFunctionMode.currentText())


    def setupChannel(self, graphnum):
        if(self.ckCurrent.isChecked()):
            self.inst.setCurrImmediate( self.sbCurrent.value())  #pass the chan number not the chan str. i.e send 2 not CH2

        if(self.chConfig[graphnum]["ckState"].isChecked()):
            self.inst.setState(self.cbState.currentText())

    def setPoints(self, graphnum, points):
        self.graphsettings[graphnum]["points"] = points


    def logData(self):
        path_to_log = "captures\\"
        file_format = "csv"
        try:
            os.makedirs(path_to_log)
        except FileExistsError:
            pass

        if (self.loggingPushButton.isChecked()):
            if(self.filename ==""):
                self.startLogTime = time.time() 
                
                #print(self.leBattRef.text())
                
                # Prepare filename as C:\MODEL_SERIAL_YYYY-MM-DD_HH.MM.SS
                timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                self.filename = path_to_log + self.inst.identify()["model"] + "_" +  self.inst.identify()["serial"] + "_"  +self.leBattRef.text() + "_" + timestamp
                header = b"Timestamp,Volts,Curr,Power,Energy,Capacity,DischargeTime\n"
                file = open(self.filename + "." + file_format, "ab")
                file.write(header) 
                file.close

            readings = self.inst.readings()
            file = open(self.filename + "." + file_format, "ab")
            file.write(("%f,%f,%f,%f,%f,%f,%s\n" % (time.time() - self.startLogTime,readings["v"], readings["i"], readings["p"], readings["w"],readings["c"],readings["t"])).encode("utf-8"))
            file.close
        else:
            self.filename = ""

    def updateSystTemperature(self):
        selfTest = self.inst.temperature()
        if(selfTest != "PASS"):
            if(self.temperatureWarningToggle):
                self.temperatureWarningToggle = False
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : pink;"
                                "}")
            else:
                self.temperatureWarningToggle = True
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : white;"
                                "}")
        else:
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : lightgreen;"
                                "}")        
            
        self.leTemp.setText(selfTest)
    
    def updateReadings(self):
        self.logData()
        readings = self.inst.readings()

        self.leState.setText(self.inst.getState())
        self.chLineEdits[0]["volts"].setText(str(readings["v"]))
        if(self.ckRun.isChecked()):
            if(readings["v"] < self.sbVolts.value()):
                self.ckRun.setChecked(False)
                self.inst.setState("OFF")
                
        self.chLineEdits[0]["current"].setText(str(readings["i"]))
        self.chLineEdits[0]["power"].setText(str(readings["p"]))
        self.chLineEdits[0]["energy"].setText(str(readings["w"]))
        self.chLineEdits[0]["capacity"].setText(str(readings["c"]))
        self.chLineEdits[0]["dischargetime"].setText(str(readings["t"]))

        for i, gs in enumerate(self.graphsettings):
            self.vdata[i].append(readings["v"])
            self.idata[i].append(readings["i"])
            self.pdata[i].append(readings["p"])
            self.edata[i].append(readings["w"])
        

            while len(self.vdata[i]) > gs["points"]:
                self.vdata[i].pop(0)

            while len(self.idata[i]) > gs["points"]:
                self.idata[i].pop(0)

            while len(self.pdata[i]) > gs["points"]:
                self.pdata[i].pop(0)

            while len(self.edata[i]) > gs["points"]:
                self.edata[i].pop(0)
  
 
        self.redrawGraphs()

    def redrawGraphs(self):
        for i,g in enumerate(self.graphlist):
               # self.graphsettings[-1]["pauseenabled"] = self.pbPause
            #if not (self.chConfig[i]["pbPause"].isChecked()):
            if not (self.graphsettings[i]["pauseenabled"].isChecked()):
                clear = True
                
                if self.graphsettings[i]["venabled"].isChecked():
                    g.passTrace(self.vdata[i], pen='b')
                    clear = False

                if self.graphsettings[i]["ienabled"].isChecked():
                    g.passTrace(self.idata[i], pen='r', clear=clear)

                if self.graphsettings[i]["penabled"].isChecked():
                    g.passTrace(self.pdata[i], pen='g', clear=clear)

                if self.graphsettings[i]["eenabled"].isChecked():
                    g.passTrace(self.edata[i], pen='y', clear=clear)


def makeApplication():
    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setOrganizationName("Kissing Frogs")
    app.setApplicationName("DL3000 GUI")
    return app

if __name__ == '__main__':
    app = makeApplication()

    # Create and show the form
    window = DL3000GUI()
    window.show()

    # Run the main Qt loop
    sys.exit(app.exec_())
