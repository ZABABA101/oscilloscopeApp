import pyvisa as visa
import time
import os
import numpy as np
import re
from typing import Optional, List, Tuple, Iterable
from logger import *



class TekScopeBase(object):
    def __init__(self, rm, rsrc_name: str, timeout: Optional[float] = None ):
        self.__session          = rm.open_resource(rsrc_name)
        self.__session.timeout  = 4000 if timeout == None else timeout
        self.time_consumed      = 0



    def __del__(self):
        self.__session.close()



    @property
    def session(self):
        return self.__session
    


    def device_clear(self):
        self.__session.clear()



    def acquire_stop(self, at_least_acq_once: bool = False, num_magic: int = 40) -> None:
        logger.info("the program will stop the acqusition")
        if at_least_acq_once: ## means must acq at least one waveform
            logger.debug("waiting to acquire at least one waveform")
            while True:
                num_acq = self.get_acquire_num()
                if num_acq >= 1:
                    break

        cmdStr =    ':ACQuire:STATE STOP;'
        self.__session.write(cmdStr)

        start = time.perf_counter()
        loop_num = 1
        while True:
            trigger_state   = self.get_trigger_state()      
            busy_flag       = int(self.__session.query("BUSY?").rstrip('\n'))
            if trigger_state != "SAVE":
                num_magic = 0
            elif loop_num > num_magic and trigger_state == "SAVE" and busy_flag == 0:
                break

            loop_num = loop_num + 1
        end = time.perf_counter()
        self.time_consumed = end - start      



    def acquire_run_continuous(self, autoMode: bool = True, prevStopFlag: bool = True) -> None:
        logger.info("the program will start continuous acqusition")
        if not prevStopFlag: ## for speed up, should stop the acq first
            self.acquire_stop()

        if autoMode:
            cmdStr =   (':TRIGger:A:MODe AUTO;' +
                        ':ACQuire:STOPAfter RUNSTop;' +
                        ':ACQuire:STATE RUN;'
                        )        
        else:  
            cmdStr =   (':TRIGger:A:MODe NORMal;' +
                        ':ACQuire:STOPAfter RUNSTop;' +
                        ':ACQuire:STATE RUN;'
                        )        
        self.__session.write(cmdStr)

        # time.sleep(TekScopeBase.time_gap_for_continuous_run)

        start = time.perf_counter()
        ## wait the acq system to be running
        while True:
            trigger_state = self.get_trigger_state()
            if  trigger_state != "SAVE":
                break

        end = time.perf_counter()
        self.time_consumed = end - start 



    def acquire_run_single_to_trigger_ready(self, numseq: Optional[int] = None, prevStopFlag: bool = True) -> None:
        ### wait the scope trigger system to be ready.
        ### after that, the user can assert a one-time trigger condition. 
        ### before that, the user must de-assert the one-time trigger condition, otherwise the scope will miss the one-time trigger condition
        ### after assertin a triggered condtion, the scope will be triggered and capture a waveform
        ### typical usage for this funciton:
        ###     acquire_run_single_to_trigger_ready()
        ###     assert a trigger condition
        ###     acquire_run_single_wait_acq_complete()
        logger.info("the program will start a single acqusition")
        start = time.perf_counter()
        if not prevStopFlag: ## for speed up
            self.acquire_stop()

        seq_num = 1 if numseq == None else numseq 
        cmdStr =   (':ACQuire:SEQuence:NUMSEQuence %s;'%seq_num +
                    ':ACQuire:STOPAfter SEQuence;' +
                    ':ACQuire:STATE RUN;'
                    )
        self.__session.write(cmdStr)

        ## waiting for trigger system to be ready
        while True:
            trigger_state   = self.get_trigger_state()       
            busy_flag       = int(self.__session.query("BUSY?").rstrip('\n'))
            if trigger_state == "READY" and busy_flag == 1:
                break
        end = time.perf_counter()
        logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds");



    def acquire_run_single_wait_acq_complete(self, timeout: Optional[float] = None) -> None:
        ### this function is waiting the scope to finish the acquisition, after the value specified
        ### in the 'timeout' variables, if still not finished the acquisition, return False; 
        ### else return True
        ### typical usage for this funciton:
        ###     acquire_run_single_to_trigger_ready()
        ###     assert a one-time trigger condition
        ###     acquire_run_single_wait_acq_complete()
        logger.info("the program will wait the single acqusition to be fininshed")
        start = time.perf_counter()
        if timeout == None:
            while True:
                numacq          = self.get_acquire_num()
                trigger_state   = self.get_trigger_state()
                busy_flag       = int(self.__session.query("BUSY?").rstrip('\n'))
                if numacq >= 1 and trigger_state == "SAVE" and busy_flag == 0:
                    end = time.perf_counter()
                    logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds");  
                    return True        
        else:
            start_local = time.perf_counter()
            while True:
                end_local       = time.perf_counter()
                numacq          = self.get_acquire_num()
                trigger_state   = self.get_trigger_state()
                busy_flag       = int(self.__session.query("BUSY?").rstrip('\n'))
                if numacq >= 1 and trigger_state == "SAVE" and busy_flag == 0 and end_local - start_local <= timeout:
                    end = time.perf_counter()
                    logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds");                      
                    return True
                elif  end_local - start_local > timeout:
                    end = time.perf_counter()
                    logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds");                      
                    return False 
          


    def acquire_run_single_auto_acq_complete(self, numseq: Optional[int] = None, prevStopFlag: bool = True, timeout: Optional[float] = None) -> None:
        ## if the trigger condition is repeated continuously, and user want to single capture one waveform, then use this function.
        ## if the trigger condition is one-time occuring, then use acquire_run_single_to_trigger_ready() and acquire_run_single_to_trigger_ready()
        logger.info("the program will start a single acqusition and waiting to be auto fininshed")
        start = time.perf_counter()
        
        if not prevStopFlag: ## for speed up
            cmdStr =    ':ACQuire:STATE STOP;'
            self.__session.write(cmdStr)
            self.acquire_stop()

        seq_num = 1 if numseq == None else numseq 
        cmdStr =   (':TRIGger:A:MODe NORMal;' +
                    ':ACQuire:SEQuence:NUMSEQuence %s;'%seq_num +
                    ':ACQuire:STOPAfter SEQuence;' +
                    ':ACQuire:STATE RUN;'
                    )
        self.__session.write(cmdStr)

        completeStatus = self.acquire_run_single_wait_acq_complete(timeout)
        end = time.perf_counter()
        logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds");  
        return completeStatus


    def force_trigger(self):
        logger.info("this function will execute a force trigger once")
        cmdStr =   (':TRIGger:A:MODe NORMal;' +
                    ':ACQuire:SEQuence:NUMSEQuence 1;' +
                    ':ACQuire:STOPAfter SEQuence;' +
                    ':ACQuire:STATE RUN;'
                    )
        self.__session.write(cmdStr)

        start_local         = time.perf_counter()
        force_trigger_flag  = False
        while True:
            end_local       = time.perf_counter()
            numacq          = self.get_acquire_num()
            trigger_state   = self.get_trigger_state()
            busy_flag       = int(self.__session.query("BUSY?").rstrip('\n'))
            if numacq >= 1 and trigger_state == "SAVE" and busy_flag == 0:
                break
            elif  end_local - start_local > 1 and not force_trigger_flag:
                self.__session.write("TRIGger FORCe")
                force_trigger_flag = True



    def get_acquire_num(self) -> int:
        logger.info("execute ACQuire:NUMACq?")
        self.__session.write("ACQuire:NUMACq?")
        self.query_data_ready()
        num_acq = int(self.__session.read().rstrip("\n"))
        logger.debug(f"the response of ACQuire:NUMACq? is {num_acq}")
        return num_acq



    def get_trigger_state(self) -> str:
        logger.info("execute TRIGger:STATE?")   
        self.__session.write('TRIGger:STATE?')
        self.query_data_ready()
        trigger_state = self.__session.read()
        
        if "SAV" in trigger_state:
            trigger_state = "SAVE"
        elif "REA" in trigger_state:
            trigger_state = "READY"
        elif "ARM" in trigger_state:
            trigger_state = "ARMED"
        elif "TRI" in trigger_state:
            trigger_state = "TRIGGER"
        else: # "AUT" in trigger_state:
            trigger_state = "AUTO"

        logger.debug(f"the response of TRIGger:STATE? is {trigger_state}")
        return trigger_state


    def get_sample_rate(self):
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use this method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:SAMPLERate"        
        logger.info("execute HORizontal:MODe:SAMPLERate")
        sample_rate = int(self.session.query("HORizontal:MODe:SAMPLERate").rstrip('\n'))        
        logger.debug(f"the response of HORizontal:MODe:SAMPLERate is {sample_rate}")
        return sample_rate       



    def get_record_length(self) -> int:
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use this method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:RECOrdlength"        
        logger.info("execute HORizontal:MODe:RECOrdlength?")
        record_len = int(self.session.query("HORizontal:MODe:RECOrdlength?").rstrip('\n'))        
        logger.debug("the response of HORizontal:RECOrdlength? is %d"%record_len)
        return record_len



    def get_horizontal_scale(self):
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use this method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:SCAle" 
        logger.info("execute HORizontal:MODe:SCAle?")
        horizontal_scale = float(self.session.query("HORizontal:MODe:SCAle?").rstrip('\n'))
        logger.debug(f"the response of HORizontal:MODe:SCAle? is {horizontal_scale}")
        return float(self.session.query("HORizontal:MODe:SCAle?").rstrip('\n'))
    


    def set_vertical(self, channels: List[str], scales, offsets = None, positions = None, extAttens = None):
        cmdStr = ''
        for i,channel in enumerate(channels):
            cmdStr += ':%s:SCAle %s;'%(channel, scales[i])        
            if offsets != None:
                cmdStr += ':%s:OFFSet %s;'%(channel, offsets[i])

            if positions != None:
                cmdStr += ':%s:POSition %s;'%(channel, positions[i])

            if extAttens != None:
                cmdStr += ':%s:PROBEFunc:EXTAtten %s;'%(channel, extAttens[i])
        self.__session.write(cmdStr)



    def query_data_ready(self) -> None:
        pass



    def event_check(self) -> None:
        start = time.perf_counter()
        esr_value = int(self.__session.query("*ESR?").rstrip('\n'))
        if esr_value > 0:
            logger.warning("the value of *ESR? is %d"%esr_value)
            event_infos = self.__session.query("ALLEV?").rstrip('\n')
            logger.warning("the value of ALLEV? is %s"%event_infos)
        else:
            logger.debug("the value of *ESR? is %d"%esr_value)
        end = time.perf_counter()
        logger.info(f"the time consumed by executing this function is {end-start:.5f} seconds")            



    def transfer_file(self, 
                      src_file_dir: str, 
                      src_file_name: str, 
                      dest_file_dir: str, 
                      dest_file_name: Optional[str] = None) -> None:
        logger.info("the program will transfer the file to the remote controller")
        start = time.perf_counter()
        
        src_file_dir    = src_file_dir.replace("\\", "/")      
        dest_file_dir   = dest_file_dir.replace("\\", "/")

        if src_file_dir[-1] != "/": # change the dir form into "C:/temp/"-like form
            src_file_dir = src_file_dir +'/'       

        if dest_file_dir[-1] != "/": # change the dir form into "C:/temp/"-like form
            dest_file_dir = dest_file_dir +'/'  

        src_file_path   = src_file_dir + src_file_name
        ## add the logic to judge if there is a such file
        self.session.write('FILESystem:READFile "%s"'%src_file_path)
        self.query_data_ready() 
        file_data = self.__session.read_raw()
        ############################################################################

        ############################################################################
        dest_filename   = src_file_name if dest_file_name == None else dest_file_name
        dest_file_path  = dest_file_dir + dest_filename
        if os.path.isdir(dest_file_dir):
            pass
        else:
            os.makedirs(dest_file_dir)

        fid = open(dest_file_path, 'wb')
        fid.write(file_data)
        fid.close()
        ############################################################################       
        end = time.perf_counter()
        logger.info(f"the time consumed by transfer file is {end-start:.5f} seconds")



    def default_setup(self):
        self.__session.write("*RST")
        self.__session.query("*OPC?")
        self.__session.write("HEADer OFF")
        logger.info("the scope has been default setup")
        



class TekScopeMDO3(TekScopeBase):
    stb_query_sleep             = 0.005 # for scope, when fetch data, use stb to check 
                                        # if the data fetched have been ready, this variable is the gap
    unresp_timeout              = 8     # global variable for scope
    # time_gap_for_continuous_run = 0.1


    def acquire_stop(self, at_least_acq_once: bool = False, num_magic: int = 40) -> None:
        ## MDO3 responds slowly, and sometimes stucks and no response. override this function
        ## to check if there is a stuck
        super().acquire_stop(at_least_acq_once, num_magic)

        if self.time_consumed > TekScopeMDO3.unresp_timeout:
            logger.warning(f"the time consumed by acquire stop is {self.time_consumed:.5f} seconds")
        else:
            logger.info(f"the time consumed by acquire stop is {self.time_consumed:.5f} seconds")        



    def acquire_run_continuous(self, autoMode: bool = True, prevStopFlag: bool = True) -> None:
        ## MDO3 responds slowly, and sometimes stucks and no response. override this function
        ## to check if there is a stuck
        super().acquire_run_continuous(autoMode, prevStopFlag)

        if self.time_consumed > TekScopeMDO3.unresp_timeout:
            logger.warning(f"the time consumed by continuous run ready is {self.time_consumed:.5f} seconds")
        else:
            logger.info(f"the time consumed by continuous run ready is {self.time_consumed:.5f} seconds")   


    def query_data_ready(self) -> None:
        ## override the method of base class 
        logger.info("the program will wait the query data to be ready")
        while True: ## waiting for the image data into the output queue
            status = self.session.read_stb()
            logger.debug("the response of read_stb() is %d"%status)
            if status & 0x10:
                break
            if TekScopeMDO3.stb_query_sleep > 0.0:
                time.sleep(TekScopeMDO3.stb_query_sleep)



    def transfer_screenshot(self, fileDir: str, fileName: str) -> None:
        logger.info("the program will transfer the screenshot to the remote controller")
        ############################################################################
        ## check the file format
        fileName, fileExt = os.path.splitext(fileName)
        if fileExt == '':
            fileExt = '.bmp'
            #fileName = fileName + fileExt
        elif fileExt != '.bmp' or fileExt != '.BMP' or fileExt != '.tiff' or fileExt != '.TIFF' or fileExt != '.png' or fileExt != '.PNG':        
            pass
        ############################################################################

        fileName_suffix = ''
        num_try = 1
        while True:
            self.session.clear()
            self.session.write("SAVe:IMAGe:INKSaver ON")
            self.session.write("SAVe:IMAGe:FILEFormat %s"%fileExt[1:])
            if num_try == 1:
                self.session.write("HARDCopy STARt")        
            else:
                self.session.write(":CLEARMenu;:CLEARMenu;:HARDCopy STARt")
            
            start = time.perf_counter()
            self.query_data_ready()
            end = time.perf_counter()
            time_consumed = end - start

            if time_consumed > TekScopeMDO3.unresp_timeout:
                logger.warning(f"the time consumed by image data ready is {time_consumed:.5f} seconds")
                #continue
            else:
                logger.info(f"the time consumed by image data ready is {time_consumed:.5f} seconds") 

            img_data = self.session.read_raw()

            ############################################################################
            fileDir = fileDir.replace("\\", "/")
            if fileDir[-1] != "/": # change the dir form into "C:/temp/"-like form
                fileDir = fileDir +'/'        
            
            filePath = fileDir + fileName + fileName_suffix + fileExt
            if os.path.isdir(fileDir):
                pass
            else:
                os.makedirs(fileDir)

            fid = open(filePath, 'wb')
            fid.write(img_data)
            fid.close()
            ############################################################################
            
            if time_consumed > TekScopeMDO3.unresp_timeout:
                fileName_suffix = "_try" + str(num_try)
                num_try = num_try + 1
                logger.warning(" try again with CLEARMenu command!")
            else:
                break
                


    def transfer_wfm_single_channel(self,
                                    channel: List[str], 
                                    dataStart: int, 
                                    dataStop: int, 
                                    horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        logger.info("the program will transfer the waveform data to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## specify channel sources of the transferred waveforms       
        self.session.write('DATa:SOUrce %s'%channel)
        #self.session.query('DATa:SOUrce?')
        ############################################################################

        ############################################################################
        self.session.write('DATa:ENCdg RIBinary')
        #self.session.query('DATa:ENCdg?')
        
        self.session.write('WFMOutpre:BYT_Nr 2')
        #self.session.query('WFMOutpre:BYT_Nr?')
                
        self.session.write('DATa:STARt %s'% dataStart)   
        self.session.write('DATa:STOP %s'% dataStop)
        #self.session.query('DATa:STARt?')   
        #self.session.query('DATa:STOP?')

        data_len = int(dataStop - dataStart + 1)
        ############################################################################
    
        ############################################################################ 
        ## get the waveform infos(WFMOutpre?)
        cmd_str =  (":WFMOutpre:BN_Fmt?;" +
                    ":WFMOutpre:BYT_Nr?;" +
                    ":WFMOutpre:XINcr?;" +
                    ":WFMOutpre:PT_Off?;" +
                    ":WFMOutpre:XZEro?;" +
                    ":WFMOutpre:YMUlt?;" +
                    ":WFMOutpre:YOFf?;" +
                    ":WFMOutpre:YZEro?")
        self.session.write(cmd_str)

        resp_str            = self.session.read().rstrip('\n')
        resp_str_list       = resp_str.split(";")

        data_format         = resp_str_list[0]
        nbytes_per_point    = int(resp_str_list[1])

        horiz_xincr         = float(resp_str_list[2])
        horiz_pt_offset     = int(resp_str_list[3])  
        horiz_xzero         = float(resp_str_list[4])
            
        digitScale          =  float(resp_str_list[5])
        digitOffset         = float(resp_str_list[6])
        digitZero           = float(resp_str_list[7])    
        ############################################################################

        ############################################################################
        ## get the waveform data
        chunk_size = int(nbytes_per_point*data_len + 100)
        self.session.write('CURVE?')
        raw_data    = self.session.read_raw(chunk_size)
        ############################################################################

        ############################################################################
        ## calculate the time axis  
        if horizontal_flg:          
            time_data   = horiz_xzero + (np.arange(data_len) - horiz_pt_offset) * horiz_xincr
        
        ## calculate the voltage axis        
        if 'RI' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>b'
            elif nbytes_per_point == 2:
                unpack_fmt = '>h'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>l'  
                                
            offset, _   = visa.util.parse_ieee_block_header(raw_data)
            digit       = np.frombuffer(raw_data, unpack_fmt, data_len, offset)
            volt_data   = digitZero + digitScale*(np.array(digit) -digitOffset)
        ############################################################################ 

        end = time.perf_counter()
        logger.info(f"the time consumed by wfm transfer is {end-start:.5f} seconds")
            
        if horizontal_flg:        
            return volt_data, time_data
        else:
            return volt_data, None



    def transfer_wfm(self, 
                     channels: List[str], 
                     dataStart: int, 
                     dataStop: int, 
                     horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        channels_len    = len(channels)
        data_len        = dataStop - dataStart + 1    
        volt_data       = np.zeros((channels_len, data_len))

        for idx, channel in enumerate(channels):
            if idx == 0:
                volt_data[idx], time_data   = self.transfer_wfm_single_channel(channel, dataStart, dataStop, horizontal_flg)
            else:
                volt_data[idx], _           = self.transfer_wfm_single_channel(channel, dataStart, dataStop, False)

        return volt_data, time_data              



    def display_analog_channel(self, channels: List[str], disp_flgs: List[int]):
        cmdStr = ''
        for i,channel in enumerate(channels):
            cmdStr += ':SELect:%s %d;'%(channel, disp_flgs[i])        
        self.session.write(cmdStr)  



    def get_sample_rate(self) -> int:
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use the base method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:SAMPLERate"  
        logger.info("execute HORizontal:SAMPLERate?")
        self.session.write("HORizontal:SAMPLERate?")
        self.query_data_ready()
        sample_rate = int(float(self.session.read().rstrip('\n')))
        logger.debug("the response of HORizontal:SAMPLERate? is %d"%sample_rate)
        return sample_rate
    


    def get_record_length(self) -> int:
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use the base method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:RECOrdlength"      
        logger.info("execute HORizontal:RECOrdlength?")   
        self.session.write('HORizontal:RECOrdlength?')
        self.query_data_ready()
        record_len = int(self.session.read().rstrip('\n'))        
        logger.debug("the response of HORizontal:RECOrdlength? is %d"%record_len)
        return record_len



    def get_horizontal_scale(self) -> int:
        ## comments:MSO4/5/6, DPO7k/DPO70k can directly use the base method, but MDO3 must override this function
        ## due to the different scpi command "HORizontal:SCAle"      
        logger.info("execute HORizontal:SCAle?")   
        self.session.write('HORizontal:SCAle?')
        self.query_data_ready()
        horizontal_scale = float(self.session.read().rstrip('\n'))        
        logger.debug(f"the response of HORizontal:SCAle? is {horizontal_scale}")
        return horizontal_scale
    


        
class TekScopeMainstream(TekScopeBase):
    def transfer_screenshot(self, fileDir: str, fileName: str) -> None:
        logger.info("the program will transfer the screenshot to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## check the file format
        fileExt = os.path.splitext(fileName)[1]
        if fileExt == '':
            fileExt = '.jpg'
            fileName = fileName + fileExt
        elif fileExt != '.bmp' or fileExt != '.BMP' or fileExt != '.jpg' or fileExt != '.JPG' or fileExt != '.png' or fileExt != '.PNG':        
            pass
        ############################################################################

        ############################################################################ 
        scopeDir = "C:/temp"
        self.session.write('FILESystem:CWD "C:/"')

        dir_contents_str = self.session.query('FILESystem:LDIR?')
        m = re.search('"[Tt][Ee][Mm][Pp];DIR;', dir_contents_str)
        if m is None:   
            self.session.write('FILESystem:MKDir "temp"')

        self.session.write('SAVe:IMAGe "%s"'%(scopeDir + '/' + fileName))
        self.session.query('*OPC?')   
        self.session.write('FILESystem:READFile "%s"'%(scopeDir + '/' + fileName)) 
        img_data = self.session.read_raw()
        ############################################################################

        ############################################################################
        fileDir     = fileDir.replace("\\", "/") 
        if fileDir[-1] != "/": # change the dir form into "C:/temp/"-like form
            fileDir = fileDir +'/'  

        filePath    = fileDir + '/' + fileName
        if os.path.isdir(fileDir):
            pass
        else:
            os.makedirs(fileDir)

        fid = open(filePath, 'wb')
        fid.write(img_data)
        fid.close()
        ############################################################################       
        end = time.perf_counter()
        logger.info(f"the time consumed by screenshot transfer is {end-start:.5f} seconds")



    def transfer_wfm(self, 
                     channels: List[str], 
                     dataStart: int, 
                     dataStop: int, 
                     horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        logger.info("the program will transfer the waveform data to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## specify channel sources of the transferred waveforms    
        channels_str    = ''
        channels_len    = len(channels)

        data_len = dataStop - dataStart + 1

        for channel in channels:
            channels_str = channels_str + channel + ', '
        channels_str = channels_str[0:-2]    
        self.session.write('DATa:SOUrce %s'%channels_str)
        #self.session.query('DATa:SOUrce?')
        ############################################################################

        ############################################################################
        self.session.write('DATa:ENCdg RIBinary')
        #self.session.query('DATa:ENCdg?')

        #self.session.write('WFMOutpre:ENCdg BIN')
        #self.session.write('WFMOutpre:BN_Fmt RI')
        #self.session.write('WFMOutpre:BYT_Or MSB')

        self.session.write('WFMOutpre:BYT_Nr 2')
        #self.session.query('WFMOutpre:BYT_Nr?')
                
        self.session.write('DATa:STARt %s'% dataStart)   
        self.session.write('DATa:STOP %s'% dataStop)
        #self.session.query('DATa:STARt?')   
        #self.session.query('DATa:STOP?')
        ############################################################################
    
        ############################################################################ 
        ## get the waveform infos(WFMOutpre?)
        digitScales    = [0]*channels_len
        digitZeros     = [0]*channels_len
        digitOffsets   = [0]*channels_len

        start_local = time.perf_counter()
        # method 1: during actual testing , this method is faster
        for idx, channel in enumerate(channels):
            self.session.write('DATa:SOUrce %s'%channel)
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')
            if idx == 0:    
                data_format         = WFMOut_bytes_list[3].decode('ascii')
                nbytes_per_point    = int(WFMOut_bytes_list[0].decode('ascii'))

                horiz_xincr         = float(WFMOut_bytes_list[11].decode('ascii'))
                horiz_xzero         = float(WFMOut_bytes_list[12].decode('ascii'))
                horiz_pt_offset     = int(WFMOut_bytes_list[13].decode('ascii'))            

            digitScales[idx]   =  float(WFMOut_bytes_list[15].decode('ascii'))
            digitOffsets[idx]  = float(WFMOut_bytes_list[16].decode('ascii'))
            digitZeros[idx]    = float(WFMOut_bytes_list[17].decode('ascii'))
        end_local = time.perf_counter()
        logger.info(f"the time consumed by wfm info query 1 is {end_local-start_local:.5f} seconds")

        # start_local = time.perf_counter()
        ## method 2: during actual testing , this method is slower
        # cmd_str =  (":WFMOutpre:BN_Fmt?;" +
        #             ":WFMOutpre:BYT_Nr?;" +
        #             ":WFMOutpre:XINcr?;" +
        #             ":WFMOutpre:PT_Off?;" +
        #             ":WFMOutpre:XZEro?")        

        # for idx, channel in enumerate(channels):
        #     cmd_str = cmd_str + ';:DATa:SOUrce %s'%channel
        #     cmd_str = cmd_str + (";:WFMOutpre:YMUlt?;" +
        #                         ":WFMOutpre:YOFf?;" +
        #                         ":WFMOutpre:YZEro?")
        # resp_str            = self.session.query(cmd_str).rstrip("\n")
        # resp_str_list       = resp_str.split(";")
        # data_format         = resp_str_list[0]
        # nbytes_per_point    = int(resp_str_list[1])

        # horiz_xincr         = float(resp_str_list[2])
        # horiz_pt_offset     = int(resp_str_list[3])  
        # horiz_xzero         = float(resp_str_list[4])

        # for idx, channel in enumerate(channels):            
        #     digitScales[idx]   = float(resp_str_list[5+ 3*idx])
        #     digitOffsets[idx]  = float(resp_str_list[6+ 3*idx])
        #     digitZeros[idx]    = float(resp_str_list[7+ 3*idx])
        # end_local = time.perf_counter()
        # logger.info("the time consumed by wfm info query 2 is %f"%(end_local-start_local))    
        ############################################################################

        ############################################################################
        ## get the waveform data
        chunk_size = nbytes_per_point*data_len*channels_len
        self.session.write('DATa:SOUrce %s'%channels_str)

        start_local = time.perf_counter()   
        self.session.write('CURVE?')
        raw_data    = self.session.read_raw(chunk_size)
        end_local = time.perf_counter()
        logger.info(f"the time consumed by CURVE? is {end_local-start_local:.5f} seconds") 
        ############################################################################

        ############################################################################    
        raw_data_channel_len    = int(len(raw_data)/channels_len)
        raw_data_list           = [bytearray()]*channels_len
        for idx in range(0, channels_len):
            raw_data_list[idx]  = raw_data[idx*raw_data_channel_len: (idx+1)*raw_data_channel_len]

        ## calculate the time axis
        start_local = time.perf_counter() 
        if horizontal_flg:          
            time_data           = horiz_xzero + (np.arange(data_len) - horiz_pt_offset) * horiz_xincr
        end_local = time.perf_counter()
        logger.info(f"the time consumed by time_data is {end_local-start_local:.5f} seconds") 

        ## calculate the voltage axis
        start_local = time.perf_counter()         
        if 'RI' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>b'
            elif nbytes_per_point == 2:
                unpack_fmt = '>h'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>l'  
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])
        elif 'RP' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>B'
            elif nbytes_per_point == 2:
                unpack_fmt = '>H'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>L'  
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])            
        else:
            if nbytes_per_point == 4:        
                unpack_fmt = '>f'
            elif nbytes_per_point == 8:
                unpack_fmt = '>d'         
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])            
        end_local = time.perf_counter()
        logger.info(f"the time consumed by volt_data is {end_local-start_local:.5f} seconds") 
        ############################################################################ 

        end = time.perf_counter()
        logger.info(f"the time consumed by wfm transfer is {end-start:.5f} seconds")

        if horizontal_flg:        
            return volt_data, time_data
        else:
            return volt_data, None



    def parse_wfmoutpre_vertical(self, channels) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        self.session.write('DATa:ENCdg RIBinary')
        self.session.write('WFMOutpre:BYT_Nr 2')

        channels_len    = len(channels)
        digitScales     = [0]*channels_len
        digitZeros      = [0]*channels_len
        digitOffsets    = [0]*channels_len        
        for idx, channel in enumerate(channels):
            self.session.write('DATa:SOUrce %s'%channel)
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')
         
            digitScales[idx]   =  float(WFMOut_bytes_list[15].decode('ascii'))
            digitOffsets[idx]  = float(WFMOut_bytes_list[16].decode('ascii'))
            digitZeros[idx]    = float(WFMOut_bytes_list[17].decode('ascii'))        

        return digitScales, digitOffsets, digitZeros



    def transfer_wfm_se(self, 
                        channels: List[str], 
                        dataStart: int, 
                        dataStop: int, 
                        digitScales: np.ndarray, 
                        digitOffsets: np.ndarray, 
                        digitZeros: np.ndarray, 
                        horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        logger.info("the program will transfer the waveform data to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## specify channel sources of the transferred waveforms
        channels_str        = ''
        channels_len        = len(channels)
        for channel in channels:
            channels_str    = channels_str + channel + ', '
        channels_str        = channels_str[0:-2]
        self.session.write('DATa:SOUrce %s'%channels_str)
        #self.session.query('DATa:SOUrce?')
        ############################################################################

        ############################################################################
        self.session.write('DATa:ENCdg RIBinary')
        #self.session.query('DATa:ENCdg?')

        # self.session.write('WFMOutpre:ENCdg BIN')
        # self.session.write('WFMOutpre:BN_Fmt RI')
        #self.session.write('WFMOutpre:BYT_Or MSB')

        self.session.write('WFMOutpre:BYT_Nr 2')
        #self.session.query('WFMOutpre:BYT_Nr?')

        self.session.write('DATa:STARt %s'% dataStart)   
        self.session.write('DATa:STOP %s'% dataStop)
        #self.session.query('DATa:STARt?')
        #self.session.query('DATa:STOP?')

        ## get the waveform infos(WFMOutpre?)
        data_len                = dataStop - dataStart + 1
        if horizontal_flg:
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')

            data_format         = WFMOut_bytes_list[3].decode('ascii')
            nbytes_per_point    = int(WFMOut_bytes_list[0].decode('ascii'))

            horiz_xincr         = float(WFMOut_bytes_list[11].decode('ascii'))
            horiz_xzero         = float(WFMOut_bytes_list[12].decode('ascii'))
            horiz_pt_offset     = int(WFMOut_bytes_list[13].decode('ascii'))

            time_data           = horiz_xzero + (np.arange(data_len) - horiz_pt_offset)*horiz_xincr
        else:
            data_format         = 'RI'
            nbytes_per_point    = 2                
        ############################################################################
    
        ############################################################################
        ## get the waveform data
            
        chunk_size              = nbytes_per_point*data_len*channels_len

        read_term               = self.session.read_termination
        self.session.read_termination  = None
        self.session.write('CURVE?')
        raw_data                = self.session.read_raw(chunk_size)
        self.session.read_termination  = read_term
        ############################################################################

        ############################################################################
        ## post-processing for curve raw data to real voltage data
        raw_data_channel_len    = int(len(raw_data)/channels_len)
        raw_data_list           = [bytearray()]*channels_len
        for idx in range(0, channels_len):
            raw_data_list[idx]  = raw_data[idx*raw_data_channel_len: (idx+1)*raw_data_channel_len]

        ## calculate the voltage axis        
        if 'RI' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>b'
            elif nbytes_per_point == 2:
                unpack_fmt = '>h'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>l'  
        
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])
        ############################################################################
        
        end = time.perf_counter()
        logger.info(f"the time consumed by wfm transfer is {end-start:.5f} seconds")

        if horizontal_flg:        
            return volt_data, time_data
        else:
            return volt_data, None



    def transfer_wfm_se2(self, 
                     channels: List[str], 
                     dataStart: int, 
                     dataStop: int,
                     vertScales: Iterable,
                     vertPositions: Optional[Iterable] = None,
                     vertOffsets: Optional[Iterable] = None,                  
                     horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        logger.info("the program will transfer the waveform data to the remote controller")
        start = time.perf_counter()

        start_local = time.perf_counter()
        ############################################################################
        ## specify channel sources of the transferred waveforms    
        channels_str    = ''
        channels_len    = len(channels)

        data_len = dataStop - dataStart + 1

        for channel in channels:
            channels_str = channels_str + channel + ', '
        channels_str = channels_str[0:-2]    
        self.session.write('DATa:SOUrce %s'%channels_str)
        #self.session.query('DATa:SOUrce?')
        ############################################################################

        ############################################################################
        self.session.write('DATa:ENCdg RIBinary')
        #self.session.query('DATa:ENCdg?')

        # self.session.write('WFMOutpre:ENCdg BIN')
        # self.session.write('WFMOutpre:BN_Fmt RI')
        #self.session.write('WFMOutpre:BYT_Or MSB')
                
        self.session.write('WFMOutpre:BYT_Nr 2')
        #self.session.query('WFMOutpre:BYT_Nr?')
                
        self.session.write('DATa:STARt %s'% dataStart)   
        self.session.write('DATa:STOP %s'% dataStop)
        #self.session.query('DATa:STARt?')   
        #self.session.query('DATa:STOP?')
        end_local = time.perf_counter()
        logger.info(f"the time consumed by setting wfm format is {end_local-start_local:.5f} seconds")  
        ############################################################################
    
        ############################################################################ 
        ## get the waveform infos(WFMOutpre?)
        start_local = time.perf_counter()

        if horizontal_flg:
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')

            data_format         = WFMOut_bytes_list[3].decode('ascii')
            nbytes_per_point    = int(WFMOut_bytes_list[0].decode('ascii'))

            horiz_xincr         = float(WFMOut_bytes_list[11].decode('ascii'))
            horiz_xzero         = float(WFMOut_bytes_list[12].decode('ascii'))
            horiz_pt_offset     = int(WFMOut_bytes_list[13].decode('ascii'))

            time_data           = horiz_xzero + (np.arange(data_len) - horiz_pt_offset)*horiz_xincr
        else:
            data_format         = 'RI'
            nbytes_per_point    = 2


        vertScales  = np.array(vertScales)

        if vertPositions == None:
            vertPositions = np.zeros(channels_len)
        else:
            vertPositions = np.array(vertPositions)            

        if vertOffsets == None:
            vertOffsets = np.zeros(channels_len)
        else:
            vertOffsets = np.array(vertOffsets)   


        digitZeros      = vertOffsets - vertPositions * vertScales
        digitOffsets    = np.zeros(channels_len)
        digitScales     = 10.24*vertScales/2**(8*nbytes_per_point)

        end_local = time.perf_counter()
        logger.info(f"the time consumed by generate wfm info is {end_local-start_local:.5f} seconds")        
        ############################################################################


        ############################################################################
        ## get the waveform data
        chunk_size = nbytes_per_point*data_len*channels_len
        self.session.write('DATa:SOUrce %s'%channels_str)

        start_local = time.perf_counter() 
        self.session.write('CURVE?')
        self.query_data_ready()
        raw_data    = self.session.read_raw(chunk_size)
        end_local = time.perf_counter()
        logger.info(f"the time consumed by CURVE? is {end_local-start_local:.5f} seconds")         
        ############################################################################


        ############################################################################    
        raw_data_channel_len    = int(len(raw_data)/channels_len)
        raw_data_list           = [bytearray()]*channels_len
        for idx in range(0, channels_len):
            raw_data_list[idx]  = raw_data[idx*raw_data_channel_len: (idx+1)*raw_data_channel_len]


        ## calculate the voltage axis
        start_local = time.perf_counter()          
        if 'RI' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>b'
            elif nbytes_per_point == 2:
                unpack_fmt = '>h'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>l'  
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])
        end_local = time.perf_counter()
        logger.info(f"the time consumed by volt_data is {end_local-start_local:.5f} seconds")
        ############################################################################ 

        end = time.perf_counter()
        logger.info(f"the time consumed by wfm transfer is {end-start:.5f} seconds")

        if horizontal_flg:        
            return volt_data, time_data
        else:
            return volt_data, None



    def display_analog_channel(self, channels: List[str], disp_flgs: List[int]):
        cmdStr = ''
        for i,channel in enumerate(channels):
            cmdStr += ':DISplay:GLObal:%s:STATE %d;'%(channel, disp_flgs[i])        
        self.session.write(cmdStr)  



    def set_high_res(self):
        self.session.write("ACQuire:MODe HIRes")


    def set_horizontal(self, sampleRate, recordLen):
        cmdStr =   (':HORizontal:MODE MANual;' +
                    ':HORizontal:MODE:SAMPLERate %s;'%sampleRate +
                    ':HORizontal:MODE:RECOrdlength %s'%recordLen
                    )
        self.session.write(cmdStr)

    def zoom_off(self):
        self.session.write(':DISplay:WAVEView1:ZOOM:ZOOM1:STATe OFF;')  


    def zoom_on(self, zoom_window_xstart, zoom_window_xend):
        self.session.write('WFMOutpre?')
        WFMOut_bytes        = self.session.read_raw()
        WFMOut_bytes_list   = WFMOut_bytes.split(b';')

        horiz_xincr         = float(WFMOut_bytes_list[11].decode('ascii'))
        horiz_xzero         = float(WFMOut_bytes_list[12].decode('ascii'))
        horiz_pt_offset     = int(WFMOut_bytes_list[13].decode('ascii'))

        zoom_span_abs       = abs(zoom_window_xend - zoom_window_xstart)
        zoom_positon_abs    = (zoom_window_xend + zoom_window_xstart) / 2
        
        horiz_scale         = self.get_horizontal_scale()
        horiz_xstart        = horiz_xzero - horiz_xincr * horiz_pt_offset

        zoom_positon        = 10*(zoom_positon_abs - horiz_xstart)/(horiz_scale)
        cmdStr = (':DISplay:WAVEView1:ZOOM:ZOOM1:STATe ON;' +
                f':DISplay:WAVEView1:ZOOM:ZOOM1:HORizontal:WINSCALe {zoom_span_abs / 10};' +
                f':DISplay:WAVEView1:ZOOM:ZOOM1:HORizontal:POSition {zoom_positon};' +
                ':DISplay:WAVEView1:ZOOM:ZOOM1:VERTical:POSition 0;' +
                ':DISplay:WAVEView1:ZOOM:ZOOM1:VERTical:SCALe 1;')
        self.session.write(cmdStr)
        

    def set_cursors(self,
                   source_a: str, 
                   source_b: str, 
                   cursor_a_t: float, 
                   cursor_b_t: float, 
                   cursor_a_v: Optional[float]          = None, 
                   cursor_b_v: Optional[float]          = None,
                   cursor_a_search_direction_preferred  = None,
                   cursor_b_search_direction_preferred  = None,
                   zoom: bool                           = True,
                   zoom_elegant_ratio: float            = 5, 
                   vtol: float                          = 1e-6):
        cmdStr = ( ':DISplay:WAVEView1:CURSor:CURSOR1:FUNCtion WAVEFORM;' +
                   ':DISplay:WAVEView1:CURSor:CURSOR1:SPLITMODE SPLIT;' +
                   ':DISplay:WAVEView1:CURSor:CURSOR1:MODe INDEPENDENT;' +
                   f':DISplay:WAVEView1:CURSor:CURSOR1:ASOUrce {source_a};' +
                   f':DISplay:WAVEView1:CURSor:CURSOR1:BSOUrce {source_b};' +
                   f':DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:APOSition {cursor_a_t};' +                   
                   f':DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:BPOSition {cursor_b_t};' +
                   ':DISplay:WAVEView1:CURSor:CURSOR1:STATE ON;')
        self.session.write(cmdStr)


        if zoom or cursor_a_v or cursor_b_v:
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')

            horiz_xincr         = float(WFMOut_bytes_list[11].decode('ascii'))
            horiz_xzero         = float(WFMOut_bytes_list[12].decode('ascii'))
            horiz_pt_offset     = int(WFMOut_bytes_list[13].decode('ascii'))

            zoom_span_abs       = zoom_elegant_ratio*abs(cursor_b_t - cursor_a_t)
            zoom_positon_abs    = (cursor_b_t + cursor_a_t) / 2
            
            if zoom:
                horiz_scale         = self.get_horizontal_scale()
                horiz_xstart        = horiz_xzero - horiz_xincr * horiz_pt_offset

                zoom_positon        = 10*(zoom_positon_abs - horiz_xstart)/(horiz_scale)
                cmdStr = (':DISplay:WAVEView1:ZOOM:ZOOM1:STATe ON;' +
                        f':DISplay:WAVEView1:ZOOM:ZOOM1:HORizontal:WINSCALe {zoom_span_abs / 10};' +
                        f':DISplay:WAVEView1:ZOOM:ZOOM1:HORizontal:POSition {zoom_positon};' +
                        ':DISplay:WAVEView1:ZOOM:ZOOM1:VERTical:POSition 0;' +
                        ':DISplay:WAVEView1:ZOOM:ZOOM1:VERTical:SCALe 1;')
                self.session.write(cmdStr)

            if cursor_a_v:
                step_rel        = 0.5
                cursor_v_trgt   = cursor_a_v
                cursor_t_curr   = cursor_a_t
                cursor_t_init   = cursor_a_t
                have_crossed    = False
                target_find     = True
                direction_rev   = False

                cursor_v_curr   = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:AVPOSition?").rstrip('\n'))
                if cursor_a_search_direction_preferred == None:                                   
                    if cursor_v_trgt - vtol <= cursor_v_curr <= cursor_v_trgt + vtol:
                        step_direction = 0

                    cursor_t_next = cursor_t_curr + step_rel *horiz_xincr
                    self.session.write(f':DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:APOSition {cursor_t_next};')
                    cursor_v_next = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:AVPOSition?").rstrip('\n'))
                    if cursor_v_curr < cursor_v_trgt - vtol and cursor_v_curr < cursor_v_next:
                        step_direction = +1
                    elif  cursor_v_curr < cursor_v_trgt - vtol and cursor_v_curr > cursor_v_next:
                        step_direction = -1
                    elif cursor_v_curr > cursor_v_trgt + vtol and cursor_v_curr < cursor_v_next: 
                        step_direction = -1
                    else:
                        step_direction = +1                     
                elif cursor_a_search_direction_preferred >= 0:
                    step_direction = 1
                else:
                    step_direction = -1                    
                
                cursor_t_next = cursor_t_curr + step_direction * horiz_xincr
                cursor_t_cand = cursor_t_next
                while step_direction != 0:
                    self.session.write(f'DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:APOSition {cursor_t_cand};')
                    cursor_v_cand = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:AVPOSition?").rstrip('\n'))
                    if abs(cursor_v_cand - cursor_v_trgt) < vtol:
                        break
                    elif not have_crossed:
                         if (cursor_v_curr < cursor_v_trgt and cursor_v_cand < cursor_v_trgt or 
                             cursor_v_curr > cursor_v_trgt and cursor_v_cand > cursor_v_trgt):
                            cursor_t_curr = cursor_t_next
                            cursor_t_next += step_direction * horiz_xincr
                            cursor_t_cand = cursor_t_next

                            if  direction_rev == False and (cursor_t_next <= zoom_positon_abs - zoom_span_abs/2 or 
                                                            cursor_t_next >= zoom_positon_abs + zoom_span_abs/2):
                                step_direction  = -step_direction
                                cursor_t_curr   = cursor_t_init
                                cursor_t_next   = cursor_t_curr + step_direction * horiz_xincr
                                cursor_t_cand   = cursor_t_next
                                direction_rev   = True
                            elif direction_rev and (cursor_t_next <= zoom_positon_abs - zoom_span_abs/2 or 
                                                    cursor_t_next >= zoom_positon_abs + zoom_span_abs/2):
                                target_find = False
                                break
                         elif cursor_v_curr < cursor_v_trgt < cursor_v_cand or cursor_v_curr > cursor_v_trgt > cursor_v_cand:
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                            have_crossed  = True                       
                    else:
                         if cursor_v_curr < cursor_v_cand < cursor_v_trgt or cursor_v_curr > cursor_v_cand > cursor_v_trgt:
                            cursor_t_curr = cursor_t_cand
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                         elif cursor_v_curr < cursor_v_trgt < cursor_v_cand or cursor_v_curr > cursor_v_trgt > cursor_v_cand:
                            cursor_t_next = cursor_t_cand
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                
                if target_find == False:
                    self.session.write(f'DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:APOSition {cursor_t_init};')    

            if cursor_b_v:
                step_rel        = 0.5
                cursor_v_trgt   = cursor_b_v
                cursor_t_curr   = cursor_b_t
                cursor_t_init   = cursor_b_t
                have_crossed    = False
                target_find     = True
                direction_rev   = False

                cursor_v_curr   = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:BVPOSition?").rstrip('\n'))
                if cursor_b_search_direction_preferred == None:                                     
                    if cursor_v_trgt - vtol <= cursor_v_curr <= cursor_v_trgt + vtol:
                        step_direction = 0

                    cursor_t_next = cursor_t_curr + step_rel *horiz_xincr
                    self.session.write(f':DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:BPOSition {cursor_t_next};')
                    cursor_v_next = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:BVPOSition?").rstrip('\n'))
                    if cursor_v_curr < cursor_v_trgt - vtol and cursor_v_curr < cursor_v_next:
                        step_direction = +1
                    elif  cursor_v_curr < cursor_v_trgt - vtol and cursor_v_curr > cursor_v_next:
                        step_direction = -1
                    elif cursor_v_curr > cursor_v_trgt + vtol and cursor_v_curr < cursor_v_next: 
                        step_direction = -1
                    else:
                        step_direction = +1                     
                elif cursor_b_search_direction_preferred >= 0:
                    step_direction = 1
                else:
                    step_direction = -1

                cursor_t_next = cursor_t_curr + step_direction * horiz_xincr
                cursor_t_cand = cursor_t_next
                while step_direction != 0:
                    self.session.write(f'DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:BPOSition {cursor_t_cand};')
                    cursor_v_cand = float(self.session.query("DISplay:WAVEView1:CURSor:CURSOR:WAVEform:BVPOSition?").rstrip('\n'))
                    if abs(cursor_v_cand - cursor_v_trgt) < vtol:
                        break
                    elif not have_crossed:
                         if (cursor_v_curr < cursor_v_trgt and cursor_v_cand < cursor_v_trgt or 
                             cursor_v_curr > cursor_v_trgt and cursor_v_cand > cursor_v_trgt):
                            cursor_t_curr = cursor_t_next
                            cursor_t_next += step_direction * horiz_xincr
                            cursor_t_cand = cursor_t_next

                            if  direction_rev == False and (cursor_t_next <= zoom_positon_abs - zoom_span_abs/2 or 
                                                            cursor_t_next >= zoom_positon_abs + zoom_span_abs/2):
                                step_direction  = -step_direction
                                cursor_t_curr   = cursor_t_init
                                cursor_t_next   = cursor_t_curr + step_direction * horiz_xincr
                                cursor_t_cand   = cursor_t_next
                                direction_rev   = True
                            elif direction_rev and (cursor_t_next <= zoom_positon_abs - zoom_span_abs/2 or 
                                                    cursor_t_next >= zoom_positon_abs + zoom_span_abs/2):
                                target_find = False
                                break
                         elif cursor_v_curr < cursor_v_trgt < cursor_v_cand or cursor_v_curr > cursor_v_trgt > cursor_v_cand:
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                            have_crossed  = True                       
                    else:
                         if cursor_v_curr < cursor_v_cand < cursor_v_trgt or cursor_v_curr > cursor_v_cand > cursor_v_trgt:
                            cursor_t_curr = cursor_t_cand
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                         elif cursor_v_curr < cursor_v_trgt < cursor_v_cand or cursor_v_curr > cursor_v_trgt > cursor_v_cand:
                            cursor_t_next = cursor_t_cand
                            cursor_t_cand = (cursor_t_curr + cursor_t_next)/2
                
                if target_find == False:
                    self.session.write(f'DISplay:WAVEView1:CURSor:CURSOR1:WAVEform:BPOSition {cursor_t_init};')    




class TekScopePerf(TekScopeBase):
    def display_analog_channel(self, channels: List[str], disp_flgs: List[int]): # the same as MDO3
        cmdStr = ''
        for i,channel in enumerate(channels):
            cmdStr += ':SELect:%s %d;'%(channel, disp_flgs[i])        
        self.session.write(cmdStr)



    def transfer_screenshot(self, fileDir: str, fileName: str) -> None:
        logger.info("the program will transfer the screenshot to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## check the file format
        fileExt = os.path.splitext(fileName)[1]
        if fileExt == '':
            fileExt = '.jpg'
            fileName = fileName + fileExt
        elif fileExt != '.bmp' or fileExt != '.BMP' or fileExt != '.jpg' or fileExt != '.JPG' or fileExt != '.png' or fileExt != '.PNG':        
            pass
        ############################################################################

        ############################################################################ 
        scopeDir = "C:/temp"
        self.session.write('FILESystem:CWD "C:/"')

        dir_contents_str = self.session.query('FILESystem:DIR?')
        m = re.search('"[Tt][Ee][Mm][Pp]"', dir_contents_str)
        if m is None:   
            self.session.write('FILESystem:MKDir "temp"')

        self.session.clear()
        # self.session.write("HARDCopy:PORT FILE")
        self.session.write("EXPort:FORMat %s"%fileExt[1:])
        self.session.write("EXPort:PALEtte COLOr")
        # self.session.write("EXPort:LAYout LANdscape")         
        self.session.write("EXPort:VIEW FULLSCREEN")        
        self.session.write('EXPort:FILEName "%s"'%(scopeDir + '/' + fileName))
        self.session.write("EXPort STARt")
        # self.session.write('*WAI') 
        self.session.query('*OPC?')   
        self.session.write('FILESystem:READFile "%s"'%(scopeDir + '/' + fileName)) 
        img_data = self.session.read_raw()
        ############################################################################

        ############################################################################
        fileDir     = fileDir.replace("\\", "/") 
        if fileDir[-1] != "/": # change the dir form into "C:/temp/"-like form
            fileDir = fileDir +'/'  

        filePath    = fileDir + '/' + fileName
        if os.path.isdir(fileDir):
            pass
        else:
            os.makedirs(fileDir)

        fid = open(filePath, 'wb')
        fid.write(img_data)
        fid.close()
        ############################################################################       
        end = time.perf_counter()
        logger.info(f"the time consumed by screenshot transfer is {end-start:.5f} seconds")



    def transfer_wfm(self, 
                     channels: List[str], 
                     dataStart: int, 
                     dataStop: int, 
                     horizontal_flg: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        ## comments: the same as the implementation on the MSO4/5/6, except the "WFMOUTPRE?" response index
        logger.info("the program will transfer the waveform data to the remote controller")
        start = time.perf_counter()
        ############################################################################
        ## specify channel sources of the transferred waveforms    
        channels_str    = ''
        channels_len    = len(channels)

        data_len = dataStop - dataStart + 1

        for channel in channels:
            channels_str = channels_str + channel + ', '
        channels_str = channels_str[0:-2]    
        self.session.write('DATa:SOUrce %s'%channels_str)
        #self.session.query('DATa:SOUrce?')
        ############################################################################

        ############################################################################
        self.session.write('DATa:ENCdg RIBinary')
        #self.session.query('DATa:ENCdg?')

        #self.session.write('WFMOutpre:ENCdg BIN')
        #self.session.write('WFMOutpre:BN_Fmt RI')
        #self.session.write('WFMOutpre:BYT_Or MSB')

        self.session.write('WFMOutpre:BYT_Nr 2')
        #self.session.query('WFMOutpre:BYT_Nr?')
                
        self.session.write('DATa:STARt %s'% dataStart)   
        self.session.write('DATa:STOP %s'% dataStop)
        #self.session.query('DATa:STARt?')   
        #self.session.query('DATa:STOP?')
        ############################################################################
    
        ############################################################################ 
        ## get the waveform infos(WFMOutpre?)
        digitScales    = [0]*channels_len
        digitZeros     = [0]*channels_len
        digitOffsets   = [0]*channels_len

        start_local = time.perf_counter()
        # method 1: during actual testing , this method is faster
        for idx, channel in enumerate(channels):
            self.session.write('DATa:SOUrce %s'%channel)
            self.session.write('WFMOutpre?')
            WFMOut_bytes        = self.session.read_raw()
            WFMOut_bytes_list   = WFMOut_bytes.split(b';')
            if idx == 0:    
                data_format         = WFMOut_bytes_list[3].decode('ascii')  #BN_Fmt
                nbytes_per_point    = int(WFMOut_bytes_list[0].decode('ascii')) #BYT_Nr

                horiz_xincr         = float(WFMOut_bytes_list[9].decode('ascii')) #XINcr
                horiz_xzero         = float(WFMOut_bytes_list[10].decode('ascii')) #XZEro
                horiz_pt_offset     = int(WFMOut_bytes_list[11].decode('ascii'))   #PT_Off

            digitScales[idx]   =  float(WFMOut_bytes_list[13].decode('ascii')) #YMUlt
            digitOffsets[idx]  = float(WFMOut_bytes_list[14].decode('ascii'))  #YOFf
            digitZeros[idx]    = float(WFMOut_bytes_list[15].decode('ascii'))  #YZEro
        end_local = time.perf_counter()
        logger.info(f"the time consumed by wfm info query 1 is {end_local-start_local:.5f} seconds")

        # start_local = time.perf_counter()
        ## method 2: during actual testing , this method is slower
        # cmd_str =  (":WFMOutpre:BN_Fmt?;" +
        #             ":WFMOutpre:BYT_Nr?;" +
        #             ":WFMOutpre:XINcr?;" +
        #             ":WFMOutpre:PT_Off?;" +
        #             ":WFMOutpre:XZEro?")        

        # for idx, channel in enumerate(channels):
        #     cmd_str = cmd_str + ';:DATa:SOUrce %s'%channel
        #     cmd_str = cmd_str + (";:WFMOutpre:YMUlt?;" +
        #                         ":WFMOutpre:YOFf?;" +
        #                         ":WFMOutpre:YZEro?")
        # resp_str            = self.session.query(cmd_str).rstrip("\n")
        # resp_str_list       = resp_str.split(";")
        # data_format         = resp_str_list[0]
        # nbytes_per_point    = int(resp_str_list[1])

        # horiz_xincr         = float(resp_str_list[2])
        # horiz_pt_offset     = int(resp_str_list[3])  
        # horiz_xzero         = float(resp_str_list[4])

        # for idx, channel in enumerate(channels):            
        #     digitScales[idx]   = float(resp_str_list[5+ 3*idx])
        #     digitOffsets[idx]  = float(resp_str_list[6+ 3*idx])
        #     digitZeros[idx]    = float(resp_str_list[7+ 3*idx])
        # end_local = time.perf_counter()
        # logger.info("the time consumed by wfm info query 2 is %f"%(end_local-start_local))    
        ############################################################################

        ############################################################################
        ## get the waveform data
        chunk_size = nbytes_per_point*data_len*channels_len
        self.session.write('DATa:SOUrce %s'%channels_str)

        start_local = time.perf_counter()   
        self.session.write('CURVE?')
        raw_data    = self.session.read_raw(chunk_size)
        end_local = time.perf_counter()
        logger.info(f"the time consumed by CURVE? is {end_local-start_local:.5f} seconds") 
        ############################################################################

        ############################################################################    
        raw_data_channel_len    = int(len(raw_data)/channels_len)
        raw_data_list           = [bytearray()]*channels_len
        for idx in range(0, channels_len):
            raw_data_list[idx]  = raw_data[idx*raw_data_channel_len: (idx+1)*raw_data_channel_len]

        ## calculate the time axis
        start_local = time.perf_counter() 
        if horizontal_flg:          
            time_data           = horiz_xzero + (np.arange(data_len) - horiz_pt_offset) * horiz_xincr
        end_local = time.perf_counter()
        logger.info(f"the time consumed by time_data is {end_local-start_local:.5f} seconds") 

        ## calculate the voltage axis
        start_local = time.perf_counter()         
        if 'RI' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>b'
            elif nbytes_per_point == 2:
                unpack_fmt = '>h'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>l'  
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])
        elif 'RP' in data_format:
            if nbytes_per_point == 1:        
                unpack_fmt = '>B'
            elif nbytes_per_point == 2:
                unpack_fmt = '>H'        
            elif nbytes_per_point == 4:  
                unpack_fmt = '>L'  
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])            
        else:
            if nbytes_per_point == 4:        
                unpack_fmt = '>f'
            elif nbytes_per_point == 8:
                unpack_fmt = '>d'         
                                
            volt_data           = np.zeros((channels_len, data_len))
            for idx, raw_data_channel in enumerate(raw_data_list):
                offset, _       = visa.util.parse_ieee_block_header(raw_data_list[idx])
                digit           = np.frombuffer(raw_data_channel, unpack_fmt, data_len, offset)
                volt_data[idx]  = digitZeros[idx] + digitScales[idx]*(np.array(digit) -digitOffsets[idx])            
        end_local = time.perf_counter()
        logger.info(f"the time consumed by volt_data is {end_local-start_local:.5f} seconds") 
        ############################################################################ 

        end = time.perf_counter()
        logger.info(f"the time consumed by wfm transfer is {end-start:.5f} seconds")

        if horizontal_flg:        
            return volt_data, time_data
        else:
            return volt_data, None



