import numpy as np
from scipy import signal
import matplotlib.pyplot as plt
from pyscope import *
from measurements import *
from utilities import *
def butter_lowpass_filter(data, freq_cutoff, freq_samp, order=4):
    norm_cutoff = 2 * freq_cutoff / freq_samp
    b, a = signal.butter(order, norm_cutoff, btype='lowpass', analog=False)
    # output      = signal.lfilter(b,a,data)
    output = signal.filtfilt(b, a, data)
    return output


def butter_bandpass_filter(data, freq_cutoff_low, freq_cutoff_high, freq_samp, order=4):
    norm_cutoff_low = 2 * freq_cutoff_low / freq_samp
    norm_cutoff_high = 2 * freq_cutoff_high / freq_samp

    b, a = signal.butter(order, [norm_cutoff_low, norm_cutoff_high], btype='bandpass', analog=False)
    output = signal.lfilter(b, a, data)
    # output              = signal.filtfilt(b,a,data)
    return output


# volt_data: 输入的电压数据。
# time_data: 时间数据。
# fsin: 正弦信号的频率。
# iq_lowFilter: 低通滤波器的截止频率（归一化频率）。
def detect_excitation_distortion(volt_data,
                                 time_data,
                                 fsin,
                                 iq_lowFilter=0.8):
    # 获取数据长度
    record_len = len(volt_data)
    # 计算出采样频率
    Ts = time_data[1] - time_data[0]
    fs = 1 / Ts
    # 生成本地振荡信号
    # lo_i 和 lo_q 分别是正弦和余弦本地振荡信号，它们与时间数据相乘用于后续混频过程。
    lo_i = 2 * np.sin(2 * np.pi * fsin * time_data)
    lo_q = 2 * np.cos(2 * np.pi * fsin * time_data)
    # idx_llim 和 idx_ulim 是用于限制处理数据的索引边界，选择从数据的第 2/10 到第 8/10 的部分。
    idx_llim = int(np.floor(2 * record_len / 10))
    idx_ulim = int(np.floor(8 * record_len / 10))

    # #volt_data_filter    = butter_bandpass_filter(volt_data, pre_bandFilter[0]*fsin, pre_bandFilter[1]*fsin, fs, 3)
    # volt_data_filter    = volt_data

    # butter_lowpass_filter 函数用于对输入的电压数据进行低通滤波。
    # iq_lowFilter = 0.8
    output_I = butter_lowpass_filter(volt_data * lo_i, iq_lowFilter * fsin, fs)[idx_llim: idx_ulim]
    output_Q = butter_lowpass_filter(volt_data * lo_q, iq_lowFilter * fsin, fs)[idx_llim: idx_ulim]

    return output_I, output_Q, time_data[idx_llim: idx_ulim]


if __name__ == '__main__':
    rm = visa.ResourceManager()
    print(rm.list_resources())
    scope_address = 'USB0::0x0699::0x0530::C069124::INSTR'
    scope = TekScopeMainstream(rm, scope_address, 10000)

    channels = ["CH1","CH2"]
    vertScales = [1, 1, 1, 1]
    vertPositions = [0, 0, 0, 0]
    vertOffsets = [0, 0, 0, 0]
    scope.display_analog_channel(channels, [1, 1, 0, 0])
    scope.set_vertical(channels, vertScales, vertOffsets, vertPositions)
    scope.set_horizontal(1.25e6, 50e6)

    fe = 1e3
    afg_set_sine(scope.session,fe,1.5,-1.5)
    record_len = scope.get_record_length()
    scope.acquire_run_single_auto_acq_complete()
    volt_data, time_data = scope.transfer_wfm(channels, 1, record_len)
    y_i, y_q, t_iq = detect_excitation_distortion(volt_data[1], time_data, fe)
    phase = np.arctan2(y_q, y_i)

    plt.subplot(4, 1, 1)
    plt.plot(time_data, volt_data[1])
    plt.grid()
    plt.ylabel("Raw Signal")

    plt.subplot(4, 1, 2)
    plt.plot(t_iq, y_i)
    plt.grid()
    plt.ylabel("I Signal")
    print(y_i)

    plt.subplot(4, 1, 3)
    plt.plot(t_iq, y_q)
    plt.grid()
    plt.ylabel("Q Signal")
    print(y_q)

    plt.subplot(4, 1, 4)
    plt.plot(t_iq, phase)
    plt.grid()
    plt.ylabel("Phase Signal")
    print(phase)

    plt.show()
    rm.close()