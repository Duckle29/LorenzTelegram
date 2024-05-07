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
    changed: bool=False

    checksum    : int=0
    wchecksum   : int=0

    def __init__(self) -> None:
        self._PARAMETERS['checksum'] = {'offset': 28,  'size': 2}
        self._PARAMETERS['wchecksum'] = {'offset': 30,  'size': 2}
        self._PARAMETERS['_ID'] = {'offset': 0,   'size': 1}

        # for param in self._PARAMETERS:
        #     setattr(self, param, None)

        
    
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

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._PARAMETERS:
            self.changed = True
        super().__setattr__(name, value)

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

    STATOR_TYPE         : int=None
    SERIAL              : int=None
    SI_IDX              : int=None
    ACTIVE_PORT_COUNT   : int=None

    _PARAMETERS = {
            'STATOR_TYPE':          {'offset': 1,   'size': 3}, 
            'SERIAL':               {'offset': 4,   'size': 4}, 
            'SI_IDX':               {'offset': 8,   'size': 1},
            'ACTIVE_PORT_COUNT':    {'offset': 9,   'size': 1}
    }

@dataclass
class STATOR_HARDWARE(ConfigBlock):
    BLOCK           : int=1
    _ID             : int=0x12
    READONLY        : bool=True

    PRODUCTION_TIME : int=None
    STAS            : int=None
    OEM             : int=None
    PULSES_PR_REV   : int=None

    _PARAMETERS = {
            'PRODUCTION_TIME':      {'offset': 1,   'size': 4}, 
            'STAS':                 {'offset': 5,   'size': 5}, 
            'OEM':                  {'offset': 10,  'size': 1},
            'PULSES_PR_REV':        {'offset': 11,  'size': 1, 'LUT': {
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

    modification_time   : int=None
    wakeup_flag         : int=None
    bus_address         : int=None
    op_flags            : int=None
    baudrate            : int=None
    output_A            : int=None
    output_B            : int=None
    lp_filter_A         : int=None
    lp_filter_B         : int=None

    _PARAMETERS = {
            'modification_time':    {'offset': 1,   'size': 4}, 
            'wakeup_flag':          {'offset': 6,   'size': 1},
            'bus_address':          {'offset': 7,   'size': 1},
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

    software_id     : int=None
    software_config : int=None

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

    ROTOR_TYPE  : int=None
    SERIAL      : int=None
    DIMENSION   : int=None
    TYPE_A      : int=None
    LOAD_A      : int=None
    ACCURACY_A  : int=None
    TYPE_B      : int=None
    LOAD_B      : int=None
    ACCURACY_B  : int=None

    _PARAMETERS = {
            'ROTOR_TYPE':       {'offset': 1,   'size': 3}, 
            'SERIAL':           {'offset': 4,   'size': 4}, 
            'DIMENSION':        {'offset': 8,   'size': 1},
            'TYPE_A':           {'offset': 9,   'size': 1},
            'LOAD_A':           {'offset': 10,  'size': 2},
            'ACCURACY_A':       {'offset': 12,  'size': 1},
            'TYPE_B':           {'offset': 13,  'size': 1},
            'LOAD_B':           {'offset': 14,  'size': 2},
            'ACCURACY_B':       {'offset': 16,  'size': 1},
    }

@dataclass
class ROTOR_FACTORY_CALIBRATION(ConfigBlock):
    BLOCK: int=129
    _ID: int=0x41
    READONLY: bool=True

    CALIBRATION_TIME    : int=None
    GAIN_A              : int=None
    OFFSET_A            : int=None
    GAIN_B              : int=None
    OFFSET_B            : int=None
    CAL_GAIN_A          : int=None
    CAL_GAIN_B          : int=None
    NOM_ADAP_FACT_A     : int=None
    NOM_ADAP_FACT_B     : int=None
    UNCERTAINTY_A       : int=None
    UNCERTAINTY_B       : int=None

    _PARAMETERS = {
            'CALIBRATION_TIME': {'offset': 1,   'size': 4},
            'GAIN_A':           {'offset': 5,   'size': 2},
            'OFFSET_A':         {'offset': 7,   'size': 2},
            'GAIN_B':           {'offset': 9,   'size': 2},
            'OFFSET_B':         {'offset': 11,  'size': 2},
            'CAL_GAIN_A':       {'offset': 13,  'size': 2},
            'CAL_GAIN_B':       {'offset': 15,  'size': 2},
            'NOM_ADAP_FACT_A':  {'offset': 17,  'size': 2},
            'NOM_ADAP_FACT_B':  {'offset': 19,  'size': 2},
            'UNCERTAINTY_A':    {'offset': 21,  'size': 2},
            'UNCERTAINTY_B':    {'offset': 23,  'size': 2},            
    }

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        match(name):
            case ['UNCERTAINTY_A', 'UNCERTAINTY_B']:
                value = value/10000
        return value

@dataclass
class ROTOR_USER_CALIBRATION(ROTOR_FACTORY_CALIBRATION):
    BLOCK: int=130
    _ID: int=0x42
    READONLY: bool=False

    def __setattr__(self, name: str, value: Any) -> None:
        match(name):
            case ['UNCERTAINTY_A', 'UNCERTAINTY_B']:
                value = int(value*10000)
        return super().__setattr__(name, value)

@dataclass
class ROTOR_OPERATION(ConfigBlock):
    BLOCK: int=131
    _ID: int=0x43
    READONLY: bool=False

    calibration_time    : int=None
    radio_channel       : int=None
    sensor_serials      : int=None

    _PARAMETERS = {
        'calibration_time':     {'offset': 1,   'size': 4}, 
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