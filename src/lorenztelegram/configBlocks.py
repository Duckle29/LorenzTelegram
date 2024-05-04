#!/usr/bin/env python3

from typing import Any


class ConfigBlock:
    PARAMETERS = {}
    def __init__(self, block_id: int, payload: int=[], readonly: bool=True) -> None:
        self._ID = block_id
        self.payload = payload
        self.readonly = readonly
        self._PARAMETERS['checksum'] = {'offset': 28,  'size': 2}
        self._PARAMETERS['wchecksum'] = {'offset': 30,  'size': 2}
        self._PARAMETERS['id'] = {'offset': 0,   'size': 1}
        
        last_param = self._PARAMETERS[list(self._PARAMETERS)[-1]]
        offset = last_param['offset']+last_param['size']
        self._PARAMETERS['reserved_n'] = {'offset': offset,   'size': 28-offset}

    
    
    def calc_checksums(self) -> tuple[bytes, bytes]:
        """Generates checksums of telegram
           
           checksum: 2-byte sum of all the bytes in the message excluding stx and checksums
           wchecksum: 2-byte sum of all the checksums, with 1 added on overflows

        Returns:
            tuple[int, int]: The checksum and weighted checksum
        """

        data = [self._ID] + self.payload
        
        checksum = 0
        wchecksum = 0
        for itm in data:
            checksum += itm
            checksum &= 0xFFFF

            wchecksum += checksum
            wchecksum &= 0xFFFF
        
        return checksum.to_bytes(2), wchecksum.to_bytes(2)
    
    def __getattribute__(self, name: str) -> Any:
        if name in self._PARAMETERS:
            offset = self._PARAMETERS[name]['offset']
            size = self._PARAMETERS[name]['size']
            attr = self.payload[offset:1+offset+size]
            
            res = 0
            for itm in attr:
                res = res << 8
                res += itm
            return res
            
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if self.readonly:
            raise AttributeError(f'{self.__class__.__name__} is read only')
        
        if name in self._PARAMETERS:
            offset = self._PARAMETERS[name]['offset']
            size = self._PARAMETERS[name]['size'] -1

            while size >= 0:
                self.payload[offset+size] = value & 0xFF
                value = value >> 8
                size -= 1
        return super().__setattr__(name, value)

    def serialize(self) -> bytes:
        checksum, wchecksum = self.calc_checksums()
        packet = [self._ID, self.payload]
        return bytes(packet) + checksum + wchecksum

class STATOR_HEADER(ConfigBlock):
    _BLOCK = 0
    _ID = 0x10
    _PARAMETERS = {
            'type':                 {'offset': 1,   'size': 3}, 
            'serial':               {'offset': 4,   'size': 4}, 
            'si_idx':               {'offset': 8,   'size': 1},
            'active_port_count':    {'offset': 9,   'size': 1},
    }

    def __init__(self) -> None:
        super().__init__(self._ID, readonly=True)

class STATOR_HARDWARE(ConfigBlock):
    _BLOCK = 1
    _ID = 0x12
    _PARAMETERS = {
            'production_time':      {'offset': 1,   'size': 4}, 
            'STAS':                 {'offset': 5,   'size': 5}, 
            'OEM':                  {'offset': 10,  'size': 1},
            'pulse_pr_rev':         {'offset': 11,  'size': 1}       
    }

    _PULSE_PR_REV_LUT = {
               0x00:    None,
               0x01:    6,
               0x02:    30,
               0x03:    60,
               0x04:    90,
               0x05:    120,
               0x06:    180,
               0x07:    360,
               0x08:    720,
               0x09:    1440,
               0x10:    100,
               0x11:    200,
               0x12:    400,
               0x13:    500,
               0x14:    1000,
               0xFF:    None
    }
    _PULSE_PR_REV_REVERSE_LUT = { v: k for k, v in _PULSE_PR_REV_LUT}

    def __init__(self) -> None:
        super().__init__(self._ID, readonly=True)

    def __getattribute__(self, name: str) -> Any:
        val = super().__getattribute__(name)
        if name == 'pulse_pr_rev':
           val = self._PULSE_PR_REV_LUT[val]
        return val
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'pulse_pr_rev':
            value = self._PULSE_PR_REV_REVERSE_LUT[value]
        return super().__setattr__(name, value)

class STATOR_OPERATION(ConfigBlock):
    _BLOCK = 2
    _ID = 0x13
    _PARAMETERS = {
            'modification_time':    {'offset': 1,   'size': 4}, 
            'reserved_0':           {'offset': 5,   'size': 1}, 
            'wakeup_flag':          {'offset': 6,   'size': 1},
            'bus_address':          {'offset': 7,   'size': 1},
            'reserved_1':           {'offset': 8,   'size': 1},
            'op_flags':             {'offset': 9,   'size': 1},
            'baudrate':             {'offset': 10,  'size': 1},
            'output_A':             {'offset': 11,  'size': 1},
            'output_B':             {'offset': 12,  'size': 1},
            'lp_filter_A':          {'offset': 13,  'size': 2},
            'lp_filter_B':          {'offset': 15,  'size': 2},
    }

    _BAUD_LUT = {
               0x00:    None,      # Device default
               0x09:    115200,
               0x10:    230400,
               0xFF:    None       # Device default
    }
    _BAUD_REVERSE_LUT = { v: k for k, v in _BAUD_LUT}

    _OUTPUT_LUT = {
               0x00:    None,
               0x01:    "A",
               0x02:    "B",
               0x03:    "SPEED",
               0x04:    "ANGLE",
               0x05:    "FORCE",
               0x06:    "POWER",
               0xFF:    None
           }
    _OUTPUT_REVERSE_LUT = { v: k for k, v in _OUTPUT_LUT}

    def __init__(self) -> None:
        super().__init__(self._ID, readonly=True)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)

        match(name):
            case 'baudrate':
                value = self._BAUD_LUT[value]
            case ['output_A', 'output_B']:
                value = self._OUTPUT_LUT[value]
        return value
    
    def __setattr__(self, name: str, value: Any) -> None:
        match(name):
            case 'baudrate':
                value = self._BAUD_REVERSE_LUT[value]
            case ['output_A', 'output_B']:
                value = self._OUTPUT_REVERSE_LUT[value]
        return super().__setattr__(name, value)