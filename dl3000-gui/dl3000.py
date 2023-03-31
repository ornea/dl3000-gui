# Work in progress
# pip install pyvisa-py
import pyvisa as visa
#Insert your serial number here / confirm via Ultra Sigma GUI
# examples "TCPIP0::192.168.1.60::INSTR" 
#          "USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR"

CONNECTSTRING = "TCPIP0::172.16.0.135::INSTR"

class DL3000(object):
    def __init__(self):
        pass

    def conn(self, constr):
        """Attempt to connect to instrument"""
        try:
            rm = visa.ResourceManager()
            self.inst = rm.open_resource(constr)
        except visa.VisaIOError:
            print("\n\n\nFailed to connect to",constr,"\n\n\n")
  
    def dis(self):
        del self.inst
        
    def identify(self):
        """Return identify string which has serial number"""
        resp = self.inst.query("*IDN?").rstrip("\n").split(',')
        dr = {"company":resp[0], "model":resp[1], "serial":resp[2], "ver":resp[3]}
        
        return dr

    def reset(self):
        print("Resetting")
        self.inst.write("*RST")
        
    def setStaticOperationCurr(self):
        """Sets the static operation mode of the electronic load  :[SOURce]:FUNCtion {CURRent|RESistance|VOLTage|POWer}"""
        print("Setting to Current Mode")
        self.inst.write("SOUR:FUNC CURR")
       

    def setSourceFuncMode(self,mode="BATT"):
        """The input regulation mode setting is controlled by the FUNCtion command, the list value, the waveform display command, or the battery discharge command
            :[SOURce]:FUNCtion:MODE {FIXed|LIST|WAVe|BATTery}
            BATTery: indicates that the input regulation mode is determined by the battery discharge command"""
        print("Setting to Current Mode:%s"%mode)
        self.inst.write("SOUR:FUNC:MODE %s"%mode)


    def setSourceFuncBatt(self):
        """The input regulation mode setting is controlled by the FUNCtion command, the list value, the waveform display command, or the battery discharge command
        :[SOURce]:FUNCtion:MODE {FIXed|LIST|WAVe|BATTery}
        BATTery: indicates that the input regulation mode is determined by the battery discharge command"""
        print("Setting to SOUR:FUNC:MODE BATT")
        self.inst.write("SOUR:FUNC:MODE BATT")

    def setSourceFunc(self,func="CURR"):
        """:[SOURce]:FUNCtion {CURRent|RESistance|VOLTage|POWer}
        Sets the static operation mode of the electronic load.
        Queries the static operation mode of the electronic load."""
        self.inst.write("SOUR:FUNC %s"%func)

    #Current Settings

    def setCurrImmediate(self, Current="0"):
        """Sets the load's regulated current in CC mode  :[SOURce]:CURRent[:LEVel][:IMMediate] {<value>|MINimum|MAXimum|DEFault}"""
        print("Setting Current Level: %s"%Current)
        self.inst.write(":SOUR:CURR:LEV:IMM %s"%Current)

    def setCurrRangeLow(self):
        #print("Setting Range Low")
        self.inst.write("SOUR:CURR:RANGE 3")
        
    def setCurrRangeHigh(self):
        print("Setting Range hIGH")
        self.inst.write("SOUR:CURR:RANGE 5")

    #Resistance settings
    def setResistanceLevelImmediate(self,ohms="1000"):
        self.inst.write(":SOUR:RES:LEV:IMM %s"%ohms)
        
    #Voltage settings
    def setVoltageLevelImmediate(self,volts="10"): #set a voltage that the load tries to maintain adjustin its load resistance accordingly
        self.inst.write(":SOUR:VOLT:LEV:IMM %s"%volts)
        

    #Power settings
    def setPowerLevelImmediate(self,power="0.010"):
        self.inst.write(":SOUR:POW:LEV:IMM %s"%power)


    def setState(self,state="OFF"):
        self.inst.write("SOUR:INP:STAT %s"%state)
        



    def temperature(self):
        results = self.inst.query("*TST?").rstrip("\n").split(",")
        resp = "PASS"
        for result in results:
            #print (result.split(":")[1])
            if(result.split(":")[1] != "PASS"):
                resp = "FAIL"
        return resp
        
    def readings(self):
        resp = {"v":self.getVolts(), "i":self.getCurr(), "p":self.getPower(), "w":self.getWatts(), "p":self.getPower(), "c":self.getCapacity(),"t":self.getDischargeTime()}
        return resp
        
    def getVolts(self):
        return(float(self.inst.query("MEAS:VOLT?")))

    def getCurr(self):
        return(float(self.inst.query("MEAS:CURR?")))

    def getWatts(self):
        return(float(self.inst.query("MEAS:WATT?")))

    def getPower(self):
        return(float(self.inst.query("MEAS:POW?")))

    def getCapacity(self):
        return(float(self.inst.query("MEAS:CAP?")))

    def getDischargeTime(self):
        return(self.inst.query("MEAS:DISCT?").rstrip("\n"))

    def getState(self):
        #print ("here in getSTat" + ch)
        if(self.inst.query("SOUR:INP:STAT?").rstrip("\n") == "0"):
            return "OFF" #self.inst.query("SOUR:INP:STAT?").rstrip("\n"))
        else:
            return "ON"

    def getCurrImmediate(self):
        """Gets the load's regulated current in CC mode  :[SOURce]:CURRent[:LEVel][:IMMediate] {<value>|MINimum|MAXimum|DEFault}"""
        return(float(self.inst.query(":SOUR:CURR:LEV:IMM?").rstrip("\n")))
    
if __name__ == '__main__':
    test = DL3000()
    
    test.conn(CONNECTSTRING)#"TCPIP0::192.168.1.60::INSTR")#"USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR")
    test.reset()
    #test.setRegulationMode("FIX")
    test.setSourceFunction()
    test.setCurrRangeLow()
    #test.setCurrRangeHigh()
    print (test.identify())
    print (test.temperature())
    #print (test.getVolts() )
    #print (test.getCurr() )
    #print (test.getWatts() )
    #print (test.getPower() )
    print (test.getCapacity() )
    test.setRegulationModeBatt()
    sleep(4)
    test.setCurrRangeLow()
    test.setCurrRangeLow()
    test.setCurrRangeLow()
#    test.setRegulationModeBatt()
    #print (test.getDischargeTime() )
    