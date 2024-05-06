#!/usr/bin/env python3

from typing import Any
from dataclasses import dataclass

class BadBlockID(Exception):
    pass

class ConfigBlock:
    _PARAMETERS = {}
    READONLY = False
    _ID: int=None
    BLOCK: int=None
    def __init__(self) -> None:
        self._PARAMETERS['checksum'] = {'offset': 28,  'size': 2}
        self._PARAMETERS['wchecksum'] = {'offset': 30,  'size': 2}
        self._PARAMETERS['id'] = {'offset': 0,   'size': 1}

        for param in self._PARAMETERS:
            setattr(self, param, 0)
    
    def calc_checksums(self, payload: list[int]) -> tuple[bytes, bytes]:
        """Generates checksums of telegram
           
           checksum: 2-byte sum of all the bytes in the message excluding stx and checksums
           wchecksum: 2-byte sum of all the checksums, with 1 added on overflows

        Returns:
            tuple[int, int]: The checksum and weighted checksum
        """
        
        checksum = 0
        wchecksum = 0
        for itm in payload:
            checksum += itm
            checksum &= 0xFFFF

            wchecksum += checksum
            wchecksum &= 0xFFFF
        
        return checksum.to_bytes(2), wchecksum.to_bytes(2)

    def from_payload(self, payload: list[int]) -> None:
        block_num = payload[0]
        if block_num != self.BLOCK:
            print(len(payload))
            raise BadBlockID(f'Expected block: {self.BLOCK}, got block {block_num}')
        payload = payload[1:]
        
        for attr in self._PARAMETERS:
            if attr in ['checksum', 'wchecksum']:
                continue            

            value = 0
            idx = self._PARAMETERS[attr]['offset']
            for _ in range(self._PARAMETERS[attr]['size']):
                value = value << 8
                value += payload[idx]                
                idx += 1

            if 'LUT' in self._PARAMETERS[attr]:
                if value in self._PARAMETERS[attr]['LUT']:
                    value = self._PARAMETERS[attr]['LUT'][value]
            
            setattr(self, attr, value)

    def gen_payload(self) -> list[int]:
        payload = [0 for _ in range(27)]
        payload[0] = self._ID

        for attr in self._PARAMETERS:
            if attr in ['checksum', 'wchecksum']:
                continue

            value = getattr(self, attr)
            if 'LUT' in attr:
                REVERSE_LUT = {v: k for k, v in attr['LUT']} 
                
                if value in REVERSE_LUT:
                    value = REVERSE_LUT[value]           
 
            idx = attr['offset'] + attr['size'] -1
            for _ in range(attr['size']):
                payload[idx] = value & 0xFF
                value >> 8
                idx -= 1
            
        return payload

    def serialize(self) -> bytes:
        if self.READONLY:
            raise AttributeError(f'{self.__class__.__name__} is read only')
        payload = self.gen_payload()
            
        checksum, wchecksum = self.calc_checksums(payload)
        return bytes(payload) + checksum + wchecksum

@dataclass
class STATOR_HEADER(ConfigBlock):
    BLOCK: int=0
    _ID: int=0x10
    READONLY: bool=True

    _PARAMETERS = {
            'type':                 {'offset': 1,   'size': 3}, 
            'serial':               {'offset': 4,   'size': 4}, 
            'si_idx':               {'offset': 8,   'size': 1},
            'active_port_count':    {'offset': 9,   'size': 1}
    }

@dataclass
class STATOR_HARDWARE(ConfigBlock):
    BLOCK: int=1
    _ID: int=0x12
    READONLY: bool=True

    _PARAMETERS = {
            'production_time':      {'offset': 1,   'size': 4}, 
            'STAS':                 {'offset': 5,   'size': 5}, 
            'OEM':                  {'offset': 10,  'size': 1},
            'pulse_pr_rev':         {'offset': 11,  'size': 1, 'LUT': {
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
                                    }       
    }

@dataclass
class STATOR_OPERATION(ConfigBlock):
    BLOCK: int=2
    _ID: int=0x13
    READONLY: bool=False
    _PARAMETERS = {
            'modification_time':    {'offset': 1,   'size': 4}, 
            'reserved_0':           {'offset': 5,   'size': 1}, 
            'wakeup_flag':          {'offset': 6,   'size': 1},
            'bus_address':          {'offset': 7,   'size': 1},
            'reserved_1':           {'offset': 8,   'size': 1},
            'op_flags':             {'offset': 9,   'size': 1},
            'baudrate':             {'offset': 10,  'size': 1, 'LUT': {
                                                                0x00:    None,      # Device default
                                                                0x09:    115200,
                                                                0x10:    230400,
                                                                0xFF:    None       # Device default
                                                                }
                                    },
            'output_A':             {'offset': 11,  'size': 1, 'LUT': {
                                                                0x00:    None,
                                                                0x01:    "A",
                                                                0x02:    "B",
                                                                0x03:    "SPEED",
                                                                0x04:    "ANGLE",
                                                                0x05:    "FORCE",
                                                                0x06:    "POWER",
                                                                0xFF:    None
                                                                }
                                    },
            'output_B':             {'offset': 12,  'size': 1, 'LUT':{
                                                                0x00:    None,
                                                                0x01:    "A",
                                                                0x02:    "B",
                                                                0x03:    "SPEED",
                                                                0x04:    "ANGLE",
                                                                0x05:    "FORCE",
                                                                0x06:    "POWER",
                                                                0xFF:    None
                                                                }
                                    },
            'lp_filter_A':          {'offset': 13,  'size': 2},
            'lp_filter_B':          {'offset': 15,  'size': 2},
    }

@dataclass
class STATOR_SOFTWARE_CONFIG(ConfigBlock):
    BLOCK: int=3
    _ID: int=0x14
    READONLY: int=False
    _PARAMETERS = {
            'software_id':      {'offset': 1,   'size': 1, 'LUT':
                                 {
                                     0x00:    None,
                                     0x01:    "LCV-USB-VS2",
                                     0x02:    "DR-USB-VS",
                                     0xFF:    None
                                 }}, 
            'software_config':  {'offset': 2,   'size': 26}, 
    }

@dataclass
class ROTOR_HEADER(ConfigBlock):
    BLOCK: int=128
    _ID: int=0x40
    READONLY: bool=True
    _PARAMETERS = {
            'type':             {'offset': 1,   'size': 3}, 
            'serial':           {'offset': 4,   'size': 4}, 
            'dimension':        {'offset': 8,   'size': 1},
            'type_A':           {'offset': 9,   'size': 1},
            'load_A':           {'offset': 10,  'size': 2},
            'accuracy_A':       {'offset': 12,  'size': 1},
            'type_B':           {'offset': 13,  'size': 1},
            'load_B':           {'offset': 14,  'size': 2},
            'accuracy_B':       {'offset': 16,  'size': 1},
    }

@dataclass
class ROTOR_FACTORY_CALIBRATION(ConfigBlock):
    BLOCK: int=129
    _ID: int=0x41
    READONLY: bool=True
    _PARAMETERS = {
            'calibration_time': {'offset': 1,   'size': 4},
            'gain_A':           {'offset': 5,   'size': 2},
            'offset_A':         {'offset': 7,   'size': 2},
            'gain_B':           {'offset': 9,   'size': 2},
            'offset_B':         {'offset': 11,  'size': 2},
            'cal_gain_A':       {'offset': 13,  'size': 2},
            'cal_gain_B':       {'offset': 15,  'size': 2},
            'nom_adap_fact_A':  {'offset': 17,  'size': 2},
            'nom_adap_fact_B':  {'offset': 19,  'size': 2},
            'uncertainty_A':    {'offset': 21,  'size': 2},
            'uncertainty_B':    {'offset': 23,  'size': 2},            
    }

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        match(name):
            case ['uncertainty_A', 'uncertainty_B']:
                value = value/10000
        return value

@dataclass
class ROTOR_USER_CALIBRATION(ROTOR_FACTORY_CALIBRATION):
    BLOCK: int=130
    _ID: int=0x42
    READONLY: bool=False

@dataclass
class ROTOR_OPERATION(ConfigBlock):
    BLOCK: int=131
    _ID: int=0x43
    READONLY: bool=False
    _PARAMETERS = {
        'calibration_time':     {'offset': 1,   'size': 4}, 
        'reserved_0':           {'offset': 5,   'size': 1},
        'radio_channel':        {'offset': 8,   'size': 1},
        'sensor_serials':       {'offset': 17,  'size': 9},
    }

class Config:
    def __init__(self) -> None:
        self.stator_header              = STATOR_HEADER()
        self.stator_hardware            = STATOR_HARDWARE()
        self.stator_operation           = STATOR_OPERATION()
        self.stator_software_config     = STATOR_SOFTWARE_CONFIG()

        self.rotor_header               = ROTOR_HEADER()
        self.rotor_factory_calibration  = ROTOR_FACTORY_CALIBRATION()
        self.rotor_user_calibration     = ROTOR_USER_CALIBRATION()
        self.rotor_operation            = ROTOR_OPERATION()

        self._blocks = [
            "stator_header",         
            "stator_hardware",
            "stator_operation",      
            "stator_software_config",
            "rotor_header",   
            "rotor_factory_calibration",
            "rotor_user_calibration",
            "rotor_operation"
        ]
    
    def __iter__(self):
        self.iter_idx = 0
        return self

    def __next__(self) -> ConfigBlock:
        try:
            block = getattr(self, self._blocks[self.iter_idx])
            self.iter_idx += 1
            return block
        except IndexError:
            raise StopIteration