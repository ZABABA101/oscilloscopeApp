import pyvisa as visa
from typing import Optional, List, Tuple, Iterable



def afg_set_burst_pulse(session):
    cmdStr = (":AFG:OUTPut:MODe BURSt;" +
                ":AFG:FUNCtion PULSe;" +
                ":AFG:BURSt:CCOUnt 2;" +
                ":AFG:FREQuency 1e6;" +
                ":AFG:PULse:WIDth 500e-9;" +
                ":AFG:HIGHLevel 0.05;" +
                ":AFG:LOWLevel -0.05;")
    session.write(cmdStr)



def afg_pulse_emit(session):
    session.write("AFG:BURSt:TRIGger")



def afg_set_sine(session, frequency, levelHigh, levelLow):
    cmdStr = (":AFG:OUTPut:MODe CONTinuous;" +
                ":AFG:FUNCtion SINE;" +
                ":AFG:FREQuency %s;"%frequency +
                ":AFG:HIGHLevel %s;"%levelHigh +
                ":AFG:LOWLevel %s;"%levelLow +
                "AFG:OUTPut:STATE ON")
    session.write(cmdStr)    



def afg_set_square(session, frequency, dutyCycle, levelHigh, levelLow):
    cmdStr = (":AFG:OUTPut:MODe CONTinuous;" +
                ":AFG:FUNCtion SQUare;" +
                ":AFG:SQUare:DUty %s;"%(dutyCycle*100) +
                ":AFG:FREQuency %s;"%frequency +
                ":AFG:HIGHLevel %s;"%levelHigh +
                ":AFG:LOWLevel %s;"%levelLow +
                "AFG:OUTPut:STATE ON")
    session.write(cmdStr)  


