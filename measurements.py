import os
from ctypes import *
from math import *
import statistics as stats
import sys
import numpy as np
from typing import Optional, List, Tuple, Iterable


dllDir = os.path.dirname(sys.argv[0])
dll = CDLL(dllDir +'/calc_crosses.dll')



def bandpass_filter(volt_data, 
                    sample_rate: float, 
                    fc_low: float, 
                    fc_high: float, 
                    numtaps = 101,
                    window_type: str = "blackman") -> np.ndarray:
    
    nyquist         = 0.5 * sample_rate
    fc_norm_low     = fc_low / nyquist
    fc_norm_high    = fc_high / nyquist

    # create the FIR filter
    taps =  np.sinc(2 * fc_norm_high * (np.arange(numtaps) - (numtaps - 1) / 2.)) - np.sinc(2 * fc_norm_low * (np.arange(numtaps) - (numtaps - 1) / 2.))

    if window_type == "rectangular":
        window = np.ones(numtaps)        
    elif window_type == "hanning":
        window = np.hanning(numtaps)
    elif window_type == "hamming":
        window = np.hamming(numtaps)
    elif window_type == "blackman":
        window = np.blackman(numtaps)
    else:
        window = np.blackman(numtaps)

    taps *= window

    # normalize filter coefficients
    taps /= np.sum(taps)

    # apply the filter to the data
    data_filtered = np.convolve(volt_data, taps, mode = "same")

    return data_filtered



def calc_max(volt_data: Iterable):
    return np.max(volt_data)



def calc_min(volt_data: Iterable):
    return np.min(volt_data)    



def calc_base_top(volt_data: Iterable,
                  mode_method: bool = True, 
                  qual_range: Optional[Tuple[float, float]] = None, 
                  dividing_window_ratio: float = 0.45):
    
    base_state_ratio    = dividing_window_ratio
    top_state_ratio     = 1 - dividing_window_ratio
  
    if not qual_range:
        volt_data_min = volt_data.min()
        volt_data_max = volt_data.max()
    else:
        volt_data_min = qual_range[0]
        volt_data_max = qual_range[1]
    
    base_list_limit_upper = volt_data_min +  base_state_ratio*(volt_data_max-volt_data_min)
    top_list_limit_lower  = volt_data_min +  top_state_ratio*(volt_data_max-volt_data_min)  
    
    base_list=[]
    top_list=[]
    
    for magnitude in volt_data:
        if volt_data_min <= magnitude <= base_list_limit_upper:
            base_list.append(magnitude)
        elif top_list_limit_lower <= magnitude <= volt_data_max: 
            top_list.append(magnitude)                    
    
    base_mean = np.mean(base_list)
    base_mode = stats.mode(base_list)    

    top_mean = np.mean(top_list)
    top_mode = stats.mode(top_list) 

    if mode_method:
        return base_mode, top_mode
    else:
        return base_mean, top_mean


# reflevel：参考电压 ，hystersis 是迟滞
# 返回波形数据与指定参考电压的交叉点，必须横穿了迟滞带，
def calc_crosses(time_data: np.ndarray, 
               volt_data: np.ndarray,
               refLevel: float, 
               hystersis: float):
    c_calc_crosses            =   dll.ez_cross_time_2
    c_calc_crosses.argtypes   =   [POINTER(c_double),
                                c_ulonglong, 
                                c_double, 
                                c_double, 
                                POINTER(c_ulonglong), 
                                POINTER(POINTER(c_int)),
                                POINTER(POINTER(c_double))]        
    c_calc_crosses.restype    =   c_int

    ctypes_ncrosses           =   c_ulonglong(0)
    ctypes_pCrossTypes       =   (POINTER(c_int))()
    ctypes_pCrossTimes       =   (POINTER(c_double))() 


    status                  =   c_calc_crosses( volt_data.ctypes.data_as(POINTER(c_double)),
                                                c_ulonglong(volt_data.shape[0]),
                                                c_double(refLevel),
                                                c_double(hystersis),
                                                pointer(ctypes_ncrosses),
                                                pointer(ctypes_pCrossTypes),
                                                pointer(ctypes_pCrossTimes))


    if status < 0:
        crossTypes           = None
        crossTimes           = None
    else:
        ncrosses              = ctypes_ncrosses.value
        crossTypes           = np.zeros(ncrosses)
        crossTimes           = np.zeros(ncrosses)
        for i in range(ncrosses):
            crossTypes[i]    = ctypes_pCrossTypes[i]
            crossTimes[i]    = time_data[0] + (time_data[1]-time_data[0])*ctypes_pCrossTimes[i]

    return  crossTypes, crossTimes        



def calc_transitions(time_data: np.ndarray, 
                    volt_data: np.ndarray,
                    refLevelLow: float,  
                    refLevelHigh: float,
                    hystersis: float):
    
    crossTypes_low, crossTimes_low      = calc_crosses(time_data, volt_data, refLevelLow, hystersis)    
    crossTypes_high, crossTimes_high    = calc_crosses(time_data, volt_data, refLevelHigh, hystersis)


    ncrosses_low    = len(crossTimes_low)
    ncrosses_high   = len(crossTimes_high)
    nedges_esti     = min(ncrosses_low, ncrosses_high)

    edgeTypes = np.zeros( (nedges_esti, 1) )
    edgeTimes = np.zeros( (nedges_esti, 2) )

    idx_high = 0
    idx_low = 0
    nedges = 0

    while idx_low < ncrosses_low and idx_high < ncrosses_high:
        if crossTypes_low[idx_low] >0 and crossTypes_high[idx_high]>0:
            if crossTimes_high[idx_high] > crossTimes_low[idx_low] and idx_low == ncrosses_low - 1:
                edgeTypes[nedges] = 1
                edgeTimes[nedges, 0] = crossTimes_low[idx_low]
                edgeTimes[nedges, 1] = crossTimes_high[idx_high]
                nedges += 1
                break
            elif crossTimes_low[idx_low] < crossTimes_high[idx_high] < crossTimes_low[idx_low+1]:
                edgeTypes[nedges] = 1
                edgeTimes[nedges, 0] = crossTimes_low[idx_low]
                edgeTimes[nedges, 1] = crossTimes_high[idx_high]                             
                nedges += 1
                idx_low += 1
                idx_high += 1
            else:
                idx_low += 2 
        elif crossTypes_low[idx_low] <0 and crossTypes_high[idx_high]<0:
            if  crossTimes_low[idx_low] > crossTimes_high[idx_high] and idx_high == ncrosses_high - 1:
                edgeTypes[nedges] = -1
                edgeTimes[nedges, 0] = crossTimes_low[idx_low]
                edgeTimes[nedges, 1] = crossTimes_high[idx_high]
                nedges += 1
                break
            elif crossTimes_high[idx_high] < crossTimes_low[idx_low] < crossTimes_high[idx_high+1]:
                edgeTypes[nedges] = -1
                edgeTimes[nedges, 0] = crossTimes_low[idx_low]
                edgeTimes[nedges, 1] = crossTimes_high[idx_high]                            
                nedges += 1
                idx_low += 1
                idx_high += 1
            else:
                idx_high += 2 
        elif crossTypes_low[idx_low] <0 and crossTypes_high[idx_high]>0:
            if crossTimes_low[idx_low] < crossTimes_high[idx_high]:
                idx_low += 1
            else:
                idx_high += 1
        else:
            pass          
    

    edgeTypes = edgeTypes[0:nedges-1]
    edgeTimes = edgeTimes[0:nedges-1]

    return edgeTypes, edgeTimes



def calc_rise_time(edgeTypes, edgeTimes):
    nedges = len(edgeTypes)

    idx_start = 0
    idx_end = nedges-1

    if edgeTypes[0]<0:
        idx_start=1

    if edgeTypes[-1] <0:
        idx_end = nedges-2

    nedges_rise = int((idx_end-idx_start)/2)+1

    riseTimes = np.zeros((nedges_rise, 1))
    for i in range(nedges_rise):
        riseTimes[i] = edgeTimes[2*i+idx_start][1] - edgeTimes[2*i+idx_start][0]
    
    meas_mean = np.mean(riseTimes)
    meas_max  = np.max(riseTimes)
    meas_min  = np.min(riseTimes)
    meas_var  = np.var(riseTimes)   

    return  meas_mean, meas_max, meas_min, meas_var    



def calc_fall_time(edgeTypes, edgeTimes):
    nedges = len(edgeTypes)

    idx_start = 0
    idx_end = nedges-1

    if edgeTypes[0] > 0:
        idx_start=1

    if edgeTypes[-1] > 0:
        idx_end = nedges-2

    nedges_fall = int((idx_end-idx_start)/2) + 1

    fallTimes = np.zeros((nedges_fall, 1))
    for i in range(nedges_fall):
        fallTimes[i] = edgeTimes[2*i+idx_start][0] - edgeTimes[2*i+idx_start][1]
    
    meas_mean = np.mean(fallTimes)
    meas_max  = np.max(fallTimes)
    meas_min  = np.min(fallTimes)
    meas_var  = np.var(fallTimes)   

    return  meas_mean, meas_max, meas_min, meas_var    



def calc_pulse_period(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    periods = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        periods[i] =  edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i]

    meas_mean = np.mean(periods)
    meas_max  = np.max(periods)
    meas_min  = np.min(periods)
    meas_var  = np.var(periods)   

    return  meas_mean, meas_max, meas_min, meas_var
 


def calc_pulse_frequency(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    frequencies = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        frequencies[i] =  1/(edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i])

    meas_mean = np.mean(frequencies)
    meas_max  = np.max(frequencies)
    meas_min  = np.min(frequencies)
    meas_var  = np.var(frequencies)   

    return  meas_mean, meas_max, meas_min, meas_var      



def calc_pulse_width_pos(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    width_pos = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        width_pos[i] =  edgeTimes[idx_start + 2*i + 1]  - edgeTimes[idx_start + 2*i]

    meas_mean = np.mean(width_pos)
    meas_max  = np.max(width_pos)
    meas_min  = np.min(width_pos)
    meas_var  = np.var(width_pos)   

    return  meas_mean, meas_max, meas_min, meas_var



def calc_pulse_width_neg(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    width_neg = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        width_neg[i] =  edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i + 1]

    meas_mean = np.mean(width_neg)
    meas_max  = np.max(width_neg)
    meas_min  = np.min(width_neg)
    meas_var  = np.var(width_neg)   

    return  meas_mean, meas_max, meas_min, meas_var



def calc_pulse_duty_cycle_pos(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    duty_cycle = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        width_pos       =  edgeTimes[idx_start + 2*i + 1]  - edgeTimes[idx_start + 2*i]
        period          =  edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i]
        duty_cycle[i]   = width_pos/period

    meas_mean = np.mean(duty_cycle)
    meas_max  = np.max(duty_cycle)
    meas_min  = np.min(duty_cycle)
    meas_var  = np.var(duty_cycle)   

    return  meas_mean, meas_max, meas_min, meas_var



def calc_pulse_duty_cycle_neg(edgeTypes, edgeTimes):
    nedges      = len(edgeTypes)
    idx_start   = 0
    idx_end     = nedges - 1
    if edgeTypes[0] > 0:
        idx_start   = 0
    else:
        idx_start   = 1       

    if edgeTypes[-1] > 0:
        idx_end     = nedges - 1
    else:
        idx_end     = nedges - 2

    nperiods = int((idx_end - idx_start)/2)

    duty_cycle = np.zeros((nperiods, 1))
    for  i in range(nperiods):
        width_neg       = edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i + 1]
        period          = edgeTimes[idx_start + 2*i + 2]  - edgeTimes[idx_start + 2*i]
        duty_cycle[i]   = width_neg/period

    meas_mean = np.mean(duty_cycle)
    meas_max  = np.max(duty_cycle)
    meas_min  = np.min(duty_cycle)
    meas_var  = np.var(duty_cycle)   

    return  meas_mean, meas_max, meas_min, meas_var


