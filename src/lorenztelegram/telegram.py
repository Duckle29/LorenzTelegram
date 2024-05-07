#!/usr/bin/env python3
import warnings

import serial
from pathlib import Path

from enum import IntEnum

from lorenztelegram.configBlocks import Config

class UnsupportedCommand(Exception):
    pass

class CommunicationError(Exception):
    pass

class Error(IntEnum):
    OK =                            0
    GENERIC =                       1
    WATCHDOG =                      2
    ROTOR_GENERIC =                 3
    ROTOR_WRONG_SPEED =             4
    ROTOR_TOO_SLOW =                5
    ROTOR_TOO_FAST =                6
    ROTOR_NOT_COMPATIBLE =          7
    ROTOR_GOT_RESET =               8
    ROTOR_NOT_FOUND =               9
    ROTOR_UNSTABLE =                10
    ROTOR_TIMEOUT =                 11
    ROTOR_GOT_NACK =                12
    ROTOR_BAD_CMD_ECHO =            13
    ROTOR_BAD_EE_WRITE =            14
    ROTOR_BAD_COMUNICAITON =        15
    
    ROTOR_CONFIG =                  31
    
    CONFIG_BLOCK =                  20
    STATOR_CONFIG =                 21
    
    STATOR_HARDWARE_CONFIG =        26
    STATOR_OPERATION_CONFIG =       27
    
    FACTORY_CALIBRATE =             32
    USER_CALIBRATE =                33
    FACTORY_CALIBRATE_CONTENTS =    34
    USER_CALIBRATE_CONTENTS =       35

    BAD_PARM_SIZE =                 40
    BAD_CMD =                       41
    BAD_CHECKSUM =                  42
    BAD_PARM =                      43
    BAD_ADDR =                      44
    CANT_OVERWRITE =                45

    STACK_OVERFLOW =                60
    ANGLE_OVERFLOW =                61

class Command(IntEnum):
    STX =                           0x02,
    SCMD_ACK =                      0x06,
    SCMD_NACK =                     0x15,
    SCMD_Hello =                    0x40,
    SCMD_ReadRaw =                  0x41,
    SCMD_ReadStatus =               0x42,
    SCMD_ReadStatusShort =          0x43,
    SCMD_ReadConfig =               0x44,
    SCMD_WriteCalibrationControl =  0x45,
    SCMD_WriteConfig =              0x46,
    #SCMD_ReadConfigHalfBlocks =     0x47, # No longer supported by lorenz
    #SCMD_WriteConfigHalfBlocks =    0x48, # No longer supported by lorenz
    SCMD_RestartDevice =            0x49,
    SCMD_SetAngleToZero =           0x4B,
    SCMD_GotoSpecialMode =          0x5A

cmd_parameter_counts = {
    'RX': {
        Command.SCMD_ACK: 0,
        Command.SCMD_NACK: 1,
        Command.SCMD_Hello: 1,
        Command.SCMD_ReadRaw: 9,
        Command.SCMD_ReadStatus: 14,
        Command.SCMD_ReadStatusShort: 1,
        Command.SCMD_ReadConfig: 33,
        Command.SCMD_WriteConfig: Command.SCMD_ACK,
        Command.SCMD_WriteCalibrationControl: Command.SCMD_ACK,
        Command.SCMD_RestartDevice: Command.SCMD_Hello,
        Command.SCMD_SetAngleToZero: Command.SCMD_ACK,
        Command.SCMD_GotoSpecialMode: Command.SCMD_ACK
    },
    'TX': {

    }
}

class Telegram:
    def __init__(self, command: Command=None, addr_from: int=0xFF, addr_to: int=0x01, parameters: list[int] = []) -> None:
        self.command = command
        self.addr_to = addr_to
        self.addr_from = addr_from

        if type(parameters) in [bytes, bytearray]:
            parameters = list(parameters)
        self.parameters = parameters

        self.parameter_cnt = len(parameters)
        self.checksum = 0
        self.wchecksum = 0

        self.stuffed = False
        self.valid = False
        if command is not None:
            self.checksum, self.wchecksum = self.calc_checksums()
    
    def from_bytes(self, bytes_obj: bytes):
        """Construct a Telegram object from a bytes object

        Args:
            bytes_obj (bytes): The serialized telegram
        """

        if bytes_obj[1] == Command.STX:
            bytes_obj = bytes_obj[2:] # Telegram must be stuffed with an extra STX, remove both
            self.stuffed = True
        else:
            bytes_obj = bytes_obj[1:] # Remove STX
        
        self.command = Command(bytes_obj[0])
        self.addr_to = bytes_obj[1]
        self.addr_from = bytes_obj[2]
        self.parameter_cnt = bytes_obj[3]
        
        if self.parameter_cnt > 0:
            self.parameters = []
            for b in bytes_obj[4:-2]:
                self.parameters.append(b)
        
        self.checksum, self.wchecksum = self.calc_checksums()
        self.valid = self.checksum == bytes_obj[-2] and self.wchecksum == bytes_obj[-1]

    def calc_checksums(self):
        """Generates checksums of telegram
           
           checksum: 1-byte sum of all the bytes in the message excluding stx and checksums
           wchecksum: 1-byte sum of all the checksums, with 1 added on overflows

        Returns:
            tuple[int, int]: The checksum and weighted checksum
        """

        tg = [self.command, self.addr_to, self.addr_from, self.parameter_cnt] + self.parameters
        
        checksum = 0
        wchecksum = 0
        for itm in tg:
            checksum += itm
            checksum = checksum & 0xFF
            
            wchecksum += checksum
            if wchecksum > 0xFF:
                wchecksum += 1
            wchecksum = wchecksum & 0xFF
        
        return checksum, wchecksum

    def stuff(self, payload: list[int]) -> list[int]:
        out = []
        for itm in payload:
            out.append(itm)
            if itm == Command.STX:
                out.append(itm)
        return out

    def serialize(self) -> bytes:
        """Serialize the Telegram to a bytes string for sending

        Returns:
            bytes: bytes string to send to sensor
        """
        tg = [self.command, self.addr_to, self.addr_from, self.parameter_cnt] + self.parameters
        tg += list(self.calc_checksums())

        tg = self.stuff(tg)

        return bytes([Command.STX] + tg)

class LorenzConnector:
    UNSUPPORTED_COMMANDS = [
    ]

    def __init__(self, port: str, timeout=0.01, **kwargs):
        """Create an object with a connection to a serial device

        Args:
            port (str): The serial port to connect to the device
            timeout (float): The timeout in to wait for new bytes from device when reading [s]

            kwargs: Supports all the keyword args that Serial.Serial() supports
        """

        if not 'baudrate' in kwargs:
            kwargs['baudrate'] = 115200
        
        kwargs['bytesize'] = serial.EIGHTBITS
        kwargs['stopbits'] = serial.STOPBITS_ONE
        kwargs['parity'] = serial.PARITY_NONE

        # Serial immediately opens the port if the port argument is passed it it's init. We don't want that.
        if 'port' in kwargs:
            port = kwargs['port']
            del kwargs['port']

        self.ser = serial.Serial(**kwargs)
        self.ser.port = port
        self.ser.timeout = timeout

        self.mode = "undefined"

        self.config = Config()
    
    def __enter__(self):
        self.ser.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ser.write(Command.STX.to_bytes(1, 'big')) # stop SOSM
        self.ser.close()
    
    def _send_telegram(self, tg: Telegram) -> Telegram | None:
        """Send a Telegram and return the response (if any)

        Args:
            tg (Telegram): The Telegram object to send

        Returns:
            Telegram: Telegram response. None if sent telegram was a broadcast
        """

        if tg.command in self.UNSUPPORTED_COMMANDS:
            raise UnsupportedCommand(f'{self.__class__.__name__} does not support {tg.command}')

        self.ser.write(tg.serialize())
        if tg.addr_to != 0:
            rx_tg = self._recv_telegram(tg)
            return rx_tg
                
    def _recv_telegram(self, tx_tg: Telegram) -> Telegram:
        """Recieve a telegram from a sensor

        Args:
            tx_tg (Telegram): The telegram that was sent to the sensor prior to the response

        Returns:
            Telegram: The telegram from the sensor
        """

        # TODO handle when sensors shouldn't respond, like on an RS485 bus
        
        rx_params = cmd_parameter_counts['RX'][tx_tg.command]
        
        if rx_params == Command.SCMD_ACK:
            rx_params = 0
        if rx_params == Command.SCMD_Hello:
            rx_params = 1

        expected_len = rx_params + 7
        
        resp = None
        while resp != Command.STX.to_bytes(1,'big') and resp != b'':
            resp = self.ser.read()
        rx = [resp]

        while resp != b'' and len(rx) < expected_len:
            resp = self.ser.read()
            if resp == Command.STX.to_bytes(1,'big'):
                resp = self.ser.read()
            rx.append(resp)
            if len(rx) == 2 and rx[1] == int.to_bytes(Command.SCMD_NACK):
                expected_len = 8

        
        if resp == b'':
            return None

        rx = [int.from_bytes(b, "big") for b in rx]
        
        tg = Telegram()
        tg.from_bytes(bytes(rx))
        return tg

    def hello(self, addr_to: int=1) -> Telegram | None:
        return self._send_telegram(Telegram(Command.SCMD_Hello, addr_to=addr_to))

    def get_raw(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Return a single set of raw and calibrated values from channel 0 and 1

        Returns:
            tuple[tuple[int, int], tuple[int, int]]: Returns a tuple of channel 0 and 1. (raw, cal)
        """

        tg = Telegram(Command.SCMD_ReadRaw)
        
        resp_tg = self._send_telegram(tg)

        raw0 = (resp_tg.parameters[0] << 8) + resp_tg.parameters[1]
        raw1 = (resp_tg.parameters[2] << 8) + resp_tg.parameters[3]

        cal0 = (resp_tg.parameters[4] << 8) + resp_tg.parameters[5]
        cal1 = (resp_tg.parameters[6] << 8) + resp_tg.parameters[7]
        return (raw0, cal0), (raw1, cal1)

    def get_status_short(self, addr_to: int=1) -> Telegram:
        return self._send_telegram(Telegram(Command.SCMD_ReadStatusShort, addr_to=addr_to))
    
    def get_status(self, addr_to: int=1) -> Telegram:
        return self._send_telegram(Telegram(Command.SCMD_ReadStatus, addr_to=addr_to))

    def restart_device(self, addr_to: int=1) -> Telegram:
        return self._send_telegram(Telegram(Command.SCMD_RestartDevice, addr_to=addr_to))

    def zero_angle(self, addr_to: int=1) -> Telegram:
        return self._send_telegram(Telegram(Command.SCMD_SetAngleToZero, addr_to=addr_to))

    def _dump_all_blocks(self, addr_to: int=1, dump_file_path: Path=None):

        if dump_file_path is None:
            dump_file_path = (Path(__file__).parent) / 'dump.txt'

        with dump_file_path.open('w') as fp:
            for block in range(0xFF):
                tg = Telegram(Command.SCMD_ReadConfig, parameters=[block])
                
                fp.write(f'BLOCK{block:>3}:\n\tTX:')
                for b in tg.serialize():
                    fp.write(f'{b:02X} ')
                fp.write('\n\tRX:')
                
                rx_tg = self._send_telegram(tg)
                if rx_tg is None:
                    fp.write(f'Failed to read: {block}\n')
                    continue

                for b in rx_tg.serialize():
                    fp.write(f'{b:02X} ')
                fp.write('\n')

    def read_config(self, addr_to: int=1):
        for block in self.config:
            tg = Telegram(Command.SCMD_ReadConfig, parameters=[block.BLOCK])
            rx_tg = self._send_telegram(tg)
            if rx_tg is None:
                print(f'Failed to read: {block.__class__.__name__}')
                continue
            
            block.from_payload(rx_tg.parameters)

    def write_config(self, addr_to: int=1):
        for block in self.config:
            if not block.READONLY:
                payload = block.serialize()
                params = block.BLOCK.to_bytes(1, 'big') + payload
                tg = Telegram(Command.SCMD_WriteConfig, addr_to=addr_to, parameters=params)
                self._send_telegram(tg)

    def start_streaming(self, sample_rate: int, count: int=0, channel: str='A'):

        if channel not in ['A', 'B', 'C']:
            raise ValueError('Channel can only be A B or C')

        if channel == 'C':
            self.mode = 'SOSM_DUAL'
        else:
            self.mode = 'SOSM_SINGLE'

        # Sample rate is the period / 200us
        # 0xFF ~ 19.61 Hz
        sample_rate = int(1/sample_rate // 0.0002)
        sample_rate = min(0xFF, max(0, sample_rate))
        params = [3, sample_rate]
        
        count = min(0xFFFF, max(0, count))
        params.append(count >> 8)
        params.append(count & 0xFF)
        params.append(ord(channel))
        
        # Switch to SOSM mode #3
        tg = Telegram(Command.SCMD_GotoSpecialMode, parameters=params)
        rx_tg = self._send_telegram(tg)
        if rx_tg.command != Command.SCMD_ACK:
            raise ConnectionError(f'\n\tStart streaming failed with error: {repr(Error(rx_tg.parameters[-1]))}.\n\tIs the sampling rate too high?')
    
    def streaming_recv_poll(self):
        if not 'SOSM' in self.mode:
            return None
        
        expected_bytes = 5 if self.mode == 'SOSM_DUAL' else 3

        idx = 0
        val = None
        if self.ser.in_waiting >= expected_bytes:
            resp = self.ser.read(expected_bytes)
            idx = resp[0]
            val = int.from_bytes(resp[1:3], 'big', signed=True)
            if expected_bytes == 5:
                val = [val, int.from_bytes(resp[3:], 'big', signed=True), resp]
        return idx, val
    
    def stop_streaming(self):
        self.ser.write(Command.STX.to_bytes(1, 'big'))
        self.ser.write(Command.STX.to_bytes(1, 'big'))
        self.ser.write(Command.STX.to_bytes(1, 'big'))

        self.mode = 'idle'


if __name__ == '__main__':
    with LorenzConnector('COM7') as lc:
        lc.read_config()
        #lc.dump_all_blocks()
        print('horse')
        #start = time.time()
        ret = lc.start_streaming(20)

        while True: # time.time() < start+5:
            idx, val = lc.streaming_recv_poll()
            if val is not None:
                print(f'{idx:3d}: {val:6d}')
            #time.sleep(0.01)
        lc.stop_streaming()