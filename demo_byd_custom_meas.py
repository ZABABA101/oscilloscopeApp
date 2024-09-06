import pyvisa as visa
import numpy as np
import matplotlib.pyplot as plt
import logging

from pyscope import *
from measurements import *
from utilities import *

if __name__ == '__main__':
    ############################################################################    
    rm = visa.ResourceManager()
    print(rm.list_resources())

    # scope_ip_address    = '134.64.228.105'      # MDO3-SZ
    #scope_ip_address    = '134.64.228.116'      #DPO70k-SZ
    scope_ip_address    = "134.64.228.77"        #MSO64-SZ
    #scope_ip_address    = "172.25.164.36"       #MSO58-TSC
    scope_address       = f'TCPIP0::{scope_ip_address}::inst0::INSTR'
    # scope_address       = f'USB0::0x0699::0x0530::C032941::INSTR'
    # scope_address       = f'USB0::0x0699::0x0527::C065939::INSTR'

    #scope = TekScopeMDO3(rm, scope_address, 40000)
    scope = TekScopeMainstream(rm, scope_address, 10000)

    scope.device_clear()
    ############################################################################    

    # channels        = ["CH1", "CH2", "CH3", "CH4"]
    channels        = ["CH1"]
    vertScales      = [0.5, 0.2, 0.2, 0.2]
    vertPositions   = [0, 0, 0, 0] 
    vertOffsets     = [0, 0, 0, 0]

    scope.default_setup()
    scope.display_analog_channel(channels, [1, 1, 1, 1])
    scope.set_vertical(channels, vertScales, vertOffsets, vertPositions)
    # scope.set_horizontal(31.25e6, 100e3)
    scope.set_horizontal(1.25e9, 100e3)

    # afg_set_burst_pulse(scope.session)
    # afg_set_sine(scope.session, 100e3, -0.25, 0.25)
    afg_set_square(scope.session, 100e4, 0.3, -1, 1, 100)


    ############################################################################
    record_len              = scope.get_record_length()

    scope.acquire_run_single_auto_acq_complete()
    volt_data, time_data    = scope.transfer_wfm(channels, 1, record_len)
    # volt_data, time_data    = scope.transfer_wfm_se(["CH1", "CH2", "CH3", "CH4"], 1, record_len, digitScales, digitOffsets, digitZeros)
    # volt_data, time_data    = scope.transfer_wfm_se2(["CH1", "CH2", "CH3", "CH4"], 
    #                                                 1, 
    #                                                 record_len,
    #                                                 vertScales,
    #                                                 vertPositions,
    #                                                 vertOffsets,
    #                                                 True)    

    base, top = calc_base_top(volt_data[0])

    logger = logging.getLogger()
    logger.info(f"the base voltage is {base:.5f} V, the top voltage is {top:.5f} V")   

    crossTypes, crossTimes = calc_crosses(time_data, volt_data[0] , 0, 0.05)

    edgeTypes, edgeTimes = calc_transitions(time_data, volt_data[0] , -0.5, +0.5,  0.05)
    # edgeTypes, edgeTimes = calc_transitions(time_data, volt_data[0] , -1.0, +1.0,  0.1)
    
    risetime_mean, risetime_max, risetime_min, risetime_var = calc_rise_time(edgeTypes, edgeTimes)
    logger.info(f"the rise time is {risetime_mean:.5e} @mean, {risetime_max:.5e} @max, {risetime_min:.5e} @min")

    falltime_mean, falltime_max, falltime_min, falltime_var = calc_fall_time(edgeTypes, edgeTimes)
    logger.info(f"the fall time is {falltime_mean:.5e} @mean, {falltime_max:.5e} @max, {falltime_min:.5e} @min")

    period_mean, period_max, period_min, period_var = calc_pulse_period(crossTypes, crossTimes)
    logger.info(f"the pulse period is {period_mean:.5e} @mean, {period_max:.5e} @max, {period_min:.5e} @min")

    freq_mean, freq_max, freq_min, freq_var = calc_pulse_frequency(crossTypes, crossTimes)
    logger.info(f"the pulse frequency is {freq_mean:.5e} @mean, {freq_max:.5e} @max, {freq_min:.5e} @min")

    dc_pos_mean, dc_pos_max, dc_pos_min, dc_pos_var= calc_pulse_duty_cycle_pos(crossTypes, crossTimes)
    logger.info(f"the pulse duty cycle pos is {dc_pos_mean:.5e} @mean, {dc_pos_max:.5e} @max, {dc_pos_min:.5e} @min")

    dc_neg_mean, dc_neg_max, dc_neg_min, dc_neg_var= calc_pulse_duty_cycle_neg(crossTypes, crossTimes)
    logger.info(f"the pulse duty cycle neg is {dc_neg_mean:.5e} @mean, {dc_neg_max:.5e} @max, {dc_neg_min:.5e} @min")

    rm.close()

    # plt.plot(time_data, volt_data[0])
    # plt.plot(time_data, volt_data[1])  
    # plt.plot(time_data, volt_data[2])
    # plt.plot(time_data, volt_data[3])
    # plt.grid()
    # plt.show() 

    # time_now = datetime.now()
    # fileDir = r"C:\Temp"
    # fileName = (str(time_now.year) +  
    #             str(time_now.month) +  
    #             str(time_now.day) + 
    #             "_" + 
    #             str(time_now.hour) + 
    #             "_" + 
    #             str(time_now.minute) + 
    #             "_" + \
    #             str(time_now.second) +
    #             "_" + 
    #             str(time_now.microsecond) +
    #             ".png")
    # logger.info("the image filename is %s"%fileName)
    # scope.transfer_screenshot(fileDir, fileName)
    # scope.event_check()  