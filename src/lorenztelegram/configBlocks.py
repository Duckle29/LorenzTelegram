#!/usr/bin/env python3

from typing import Any

class ConfigBlock:
    _PARAMETERS = {}
    _READONLY = False
    _ID = None
    def __init__(self, payload: int=[0 for _ in range(27)]) -> None:
        self.payload = payload

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
            offset = self._PARAMETERS[name]['offset'] # Read the parameter from the configblock payload
            size = self._PARAMETERS[name]['size']
            attr = self.payload[offset:1+offset+size]
            
            # Convert from bytes to one int
            res = 0
            for itm in attr:
                res = res << 8 
                res += itm
        
            # If this value has a LUT associated with it. Convert it. If this fails it'll return the raw value
            # This is used for settings such as options for custom user values not in the LUT
            if 'LUT' in self._PARAMETERS[name]:
                LUT = self._PARAMETERS[name]['LUT']
                try:
                    tmp = LUT[res]
                except KeyError:
                    tmp = res
                return tmp
            return res
            
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if self._READONLY:
            raise AttributeError(f'{self.__class__.__name__} is read only')
        
        if name in self._PARAMETERS:
            offset = self._PARAMETERS[name]['offset']
            size = self._PARAMETERS[name]['size'] -1

            # Construct a reverse LUT. Duped keys will be squashed.
            # If this fails it'll return the raw value.
            # This is used for settings such as options for custom user values not in the LUT
            if 'LUT' in self._PARAMETERS[name]['LUT']:
                REVERSE_LUT = {v: k for k, v in self._PARAMETERS[name]['LUT']} 
                try:
                    tmp = REVERSE_LUT[value]
                except KeyError:
                    tmp = value
                value = tmp
        
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
    _READONLY = True
    _PARAMETERS = {
            'type':                 {'offset': 1,   'size': 3}, 
            'serial':               {'offset': 4,   'size': 4}, 
            'si_idx':               {'offset': 8,   'size': 1},
            'active_port_count':    {'offset': 9,   'size': 1},
    }

    def __init__(self) -> None:
        super().__init__()

class STATOR_HARDWARE(ConfigBlock):
    _BLOCK = 1
    _ID = 0x12
    _READONLY = True
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

    def __init__(self) -> None:
        super().__init__()

class STATOR_OPERATION(ConfigBlock):
    _BLOCK = 2
    _ID = 0x13
    _READONLY = False
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

    def __init__(self) -> None:
        super().__init__()

class STATOR_SOFTWARE_CONFIG(ConfigBlock):
    _BLOCK = 3
    _ID = 0x14
    _READONLY = False
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

    def __init__(self) -> None:
        super().__init__()

class ROTOR_HEADER(ConfigBlock):
    _BLOCK = 128
    _ID = 0x40
    _READONLY = True
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

    def __init__(self) -> None:
        super().__init__()

class ROTOR_FACTORY_CALIBRATION(ConfigBlock):
    _BLOCK = 129
    _ID = 0x41
    _READONLY = True
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

    def __init__(self) -> None:
        super().__init__()

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        match(name):
            case ['uncertainty_A', 'uncertainty_B']:
                value = value/10000
        return value

class ROTOR_USER_CALIBRATION(ROTOR_FACTORY_CALIBRATION):
    _BLOCK = 130
    _ID = 0x42
    _READONLY = False

    def __init__(self) -> None:
        super().__init__()

class ROTOR_OPERATION(ConfigBlock):
    _BLOCK = 131
    _ID = 0x43
    _READONLY = False
    _PARAMETERS = {
        'calibration_time':     {'offset': 1,   'size': 4}, 
        'reserved_0':           {'offset': 5,   'size': 1},
        'radio_channel':        {'offset': 8,   'size': 1},
        'sensor_serials':       {'offset': 17,  'size': 9},
    }

    def __init__(self) -> None:
        super().__init__()

class Config:
    def __init__(self) -> None:
        self.stator_hardware = STATOR_HARDWARE()
        self.stator_header = STATOR_HEADER()
        self.stator_operation = STATOR_OPERATION()
        self.stator_software_config = STATOR_SOFTWARE_CONFIG()

        self.rotor_header = ROTOR_HEADER()
        self.rotor_factory_calibration = ROTOR_FACTORY_CALIBRATION()
        self.rotor_user_calibration = ROTOR_USER_CALIBRATION()
        self.rotor_operation = ROTOR_OPERATION()
