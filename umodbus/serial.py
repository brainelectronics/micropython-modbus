#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

# system packages
from machine import UART
from machine import Pin
import struct
import time

# custom packages
from . import const as Const
from . import functions
from .common import Request, CommonModbusFunctions
from .common import ModbusException
from .modbus import Modbus

# typing not natively supported on MicroPython
from .typing import List, Optional, Union


class ModbusRTU(Modbus):
    """
    Modbus RTU client class

    :param      addr:        The address of this device on the bus
    :type       addr:        int
    :param      baudrate:    The baudrate, default 9600
    :type       baudrate:    int
    :param      data_bits:   The data bits, default 8
    :type       data_bits:   int
    :param      stop_bits:   The stop bits, default 1
    :type       stop_bits:   int
    :param      parity:      The parity, default None
    :type       parity:      Optional[int]
    :param      pins:        The pins as list [TX, RX]
    :type       pins:        List[Union[int, Pin], Union[int, Pin]]
    :param      ctrl_pin:    The control pin
    :type       ctrl_pin:    int
    :param      uart_id:     The ID of the used UART
    :type       uart_id:     int
    """
    def __init__(self,
                 addr: int,
                 baudrate: int = 9600,
                 data_bits: int = 8,
                 stop_bits: int = 1,
                 parity: Optional[int] = None,
                 pins: List[Union[int, Pin], Union[int, Pin]] = None,
                 ctrl_pin: int = None,
                 uart_id: int = 1):
        super().__init__(
            # set itf to Serial object, addr_list to [addr]
            Serial(uart_id=uart_id,
                   baudrate=baudrate,
                   data_bits=data_bits,
                   stop_bits=stop_bits,
                   parity=parity,
                   pins=pins,
                   ctrl_pin=ctrl_pin),
            [Const.BROADCAST_ADDR, addr]
        )


class Serial(CommonModbusFunctions):
    def __init__(self,
                 uart_id: int = 1,
                 baudrate: int = 9600,
                 data_bits: int = 8,
                 stop_bits: int = 1,
                 parity=None,
                 pins: List[Union[int, Pin], Union[int, Pin]] = None,
                 ctrl_pin: int = None):
        """
        Setup Serial/RTU Modbus

        :param      uart_id:     The ID of the used UART
        :type       uart_id:     int
        :param      baudrate:    The baudrate, default 9600
        :type       baudrate:    int
        :param      data_bits:   The data bits, default 8
        :type       data_bits:   int
        :param      stop_bits:   The stop bits, default 1
        :type       stop_bits:   int
        :param      parity:      The parity, default None
        :type       parity:      Optional[int]
        :param      pins:        The pins as list [TX, RX]
        :type       pins:        List[Union[int, Pin], Union[int, Pin]]
        :param      ctrl_pin:    The control pin
        :type       ctrl_pin:    int
        """
        # UART flush function is introduced in Micropython v1.20.0
        self._has_uart_flush = callable(getattr(UART, "flush", None))
        self._uart = UART(uart_id,
                          baudrate=baudrate,
                          bits=data_bits,
                          parity=parity,
                          stop=stop_bits,
                          # timeout_chars=2,  # WiPy only
                          # pins=pins         # WiPy only
                          tx=pins[0],
                          rx=pins[1]
                          )

        if ctrl_pin is not None:
            self._ctrlPin = Pin(ctrl_pin, mode=Pin.OUT)
        else:
            self._ctrlPin = None

        # timing of 1 character in microseconds (us)
        self._t1char = (1000000 * (data_bits + stop_bits + 2)) // baudrate

        # inter-frame delay in microseconds (us)
        # - <= 19200 bps: 3.5x timing of 1 character
        # - > 19200 bps: 1750 us
        if baudrate <= 19200:
            self._inter_frame_delay = (self._t1char * 3500) // 1000
        else:
            self._inter_frame_delay = 1750

    def _calculate_crc16(self, data: bytearray) -> bytes:
        """
        Calculates the CRC16.

        :param      data:        The data
        :type       data:        bytearray

        :returns:   The crc 16.
        :rtype:     bytes
        """
        crc = 0xFFFF

        for char in data:
            crc = (crc >> 8) ^ Const.CRC16_TABLE[((crc) ^ char) & 0xFF]

        return struct.pack('<H', crc)

    def _exit_read(self, response: bytearray) -> bool:
        """
        Return on modbus read error

        :param      response:    The response
        :type       response:    bytearray

        :returns:   State of basic read response evaluation,
                    True if entire response has been read
        :rtype:     bool
        """
        response_len = len(response)
        if response_len >= 2 and response[1] >= Const.ERROR_BIAS:
            if response_len < Const.ERROR_RESP_LEN:
                return False
        elif response_len >= 3 and (Const.READ_COILS <= response[1] <= Const.READ_INPUT_REGISTER):
            expected_len = Const.RESPONSE_HDR_LENGTH + 1 + response[2] + Const.CRC_LENGTH
            if response_len < expected_len:
                return False
        elif response_len < Const.FIXED_RESP_LEN:
            return False

        return True

    def _uart_read(self) -> bytearray:
        """
        Read incoming slave response from UART

        :returns:   Read content
        :rtype:     bytearray
        """
        response = bytearray()

        # TODO: use some kind of hint or user-configurable delay
        #       to determine this loop counter
        for x in range(1, 120):
            if self._uart.any():
                # WiPy only
                # response.extend(self._uart.readall())
                response.extend(self._uart.read())

                # variable length function codes may require multiple reads
                if self._exit_read(response):
                    break

            # wait for the maximum time between two frames
            time.sleep_us(self._inter_frame_delay)

        return response

    def _uart_read_frame(self, timeout: Optional[int] = None) -> bytearray:
        """
        Read a Modbus frame

        :param      timeout:  The timeout
        :type       timeout:  Optional[int]

        :returns:   Received message
        :rtype:     bytearray
        """
        received_bytes = bytearray()

        # set default timeout to at twice the inter-frame delay
        if timeout == 0 or timeout is None:
            timeout = 2 * self._inter_frame_delay  # in microseconds

        start_us = time.ticks_us()

        # stay inside this while loop at least for the timeout time
        while (time.ticks_diff(time.ticks_us(), start_us) <= timeout):
            # check amount of available characters
            if self._uart.any():
                # remember this time in microseconds
                last_byte_ts = time.ticks_us()

                # do not stop reading and appending the result to the buffer
                # until the time between two frames elapsed
                while time.ticks_diff(time.ticks_us(), last_byte_ts) <= self._inter_frame_delay:
                    # WiPy only
                    # r = self._uart.readall()
                    r = self._uart.read()

                    # if something has been read after the first iteration of
                    # this inner while loop (within self._inter_frame_delay)
                    if r is not None:
                        # append the new read stuff to the buffer
                        received_bytes.extend(r)

                        # update the timestamp of the last byte being read
                        last_byte_ts = time.ticks_us()

            # if something has been read before the overall timeout is reached
            if len(received_bytes) > 0:
                return received_bytes

        # return the result in case the overall timeout has been reached
        return received_bytes

    def _send(self, modbus_pdu: bytes, slave_addr: int) -> None:
        """
        Send Modbus frame via UART

        If a flow control pin has been setup, it will be controlled accordingly

        :param      modbus_pdu:  The modbus Protocol Data Unit
        :type       modbus_pdu:  bytes
        :param      slave_addr:  The slave address
        :type       slave_addr:  int
        """
        # modbus_adu: Modbus Application Data Unit
        # consists of the Modbus PDU, with slave address prepended and checksum appended
        modbus_adu = bytearray()
        modbus_adu.append(slave_addr)
        modbus_adu.extend(modbus_pdu)
        modbus_adu.extend(self._calculate_crc16(modbus_adu))

        if self._ctrlPin:
            self._ctrlPin.on()
            # wait until the control pin really changed
            # 85-95us (ESP32 @ 160/240MHz)
            time.sleep_us(200)

        # the timing of this part is critical:
        # - if we disable output too early,
        #   the command will not be received in full
        # - if we disable output too late,
        #   the incoming response will lose some data at the beginning
        # easiest to just wait for the bytes to be sent out on the wire

        send_start_time = time.ticks_us()
        # 360-400us @ 9600-115200 baud (measured) (ESP32 @ 160/240MHz)
        self._uart.write(modbus_adu)
        send_finish_time = time.ticks_us()

        if self._has_uart_flush:
            self._uart.flush()
            time.sleep_us(self._t1char)
        else:
            sleep_time_us = (
                self._t1char * len(modbus_adu) -    # total frame time in us
                time.ticks_diff(send_finish_time, send_start_time) +
                100     # only required at baudrates above 57600, but hey 100us
            )
            time.sleep_us(sleep_time_us)

        if self._ctrlPin:
            self._ctrlPin.off()

    def _send_receive(self,
                      modbus_pdu: bytes,
                      slave_addr: int,
                      count: bool) -> Union[bytes, None]:
        """
        Send a modbus message and receive the reponse.

        :param      modbus_pdu:  The modbus Protocol Data Unit
        :type       modbus_pdu:  bytes
        :param      slave_addr:  The slave address
        :type       slave_addr:  int
        :param      count:       The count
        :type       count:       bool

        :returns:   Validated response content
        :rtype:     bytes
        """
        # flush the Rx FIFO buffer
        self._uart.read()

        self._send(modbus_pdu=modbus_pdu, slave_addr=slave_addr)

        if slave_addr == Const.BROADCAST_ADDR:
            # Do not wait for response after a broadcast
            return None

        return self._validate_resp_hdr(response=self._uart_read(),
                                       slave_addr=slave_addr,
                                       function_code=modbus_pdu[0],
                                       count=count)

    def _validate_resp_hdr(self,
                           response: bytearray,
                           slave_addr: int,
                           function_code: int,
                           count: bool) -> bytes:
        """
        Validate the response header.

        :param      response:       The response
        :type       response:       bytearray
        :param      slave_addr:     The slave address
        :type       slave_addr:     int
        :param      function_code:  The function code
        :type       function_code:  int
        :param      count:          The count
        :type       count:          bool

        :returns:   Modbus response content
        :rtype:     bytes
        """
        if len(response) == 0:
            raise OSError('no data received from slave')

        resp_crc = response[-Const.CRC_LENGTH:]
        expected_crc = self._calculate_crc16(
            response[0:len(response) - Const.CRC_LENGTH]
        )

        if ((resp_crc[0] is not expected_crc[0]) or
                (resp_crc[1] is not expected_crc[1])):
            raise OSError('invalid response CRC')

        if (response[0] != slave_addr):
            raise ValueError('wrong slave address')

        if (response[1] == (function_code + Const.ERROR_BIAS)):
            raise ValueError('slave returned exception code: {:d}'.
                             format(response[2]))

        hdr_length = (Const.RESPONSE_HDR_LENGTH + 1) if count else \
            Const.RESPONSE_HDR_LENGTH

        return response[hdr_length:len(response) - Const.CRC_LENGTH]

    def send_response(self,
                      slave_addr: int,
                      function_code: int,
                      request_register_addr: int,
                      request_register_qty: int,
                      request_data: list,
                      values: Optional[list] = None,
                      signed: bool = True) -> None:
        """
        Send a response to a client.

        :param      slave_addr:             The slave address
        :type       slave_addr:             int
        :param      function_code:          The function code
        :type       function_code:          int
        :param      request_register_addr:  The request register address
        :type       request_register_addr:  int
        :param      request_register_qty:   The request register qty
        :type       request_register_qty:   int
        :param      request_data:           The request data
        :type       request_data:           list
        :param      values:                 The values
        :type       values:                 Optional[list]
        :param      signed:                 Indicates if signed
        :type       signed:                 bool
        """

        if slave_addr == Const.BROADCAST_ADDR:
            # Do not reply to broadcast messages
            return

        modbus_pdu = functions.response(
            function_code=function_code,
            request_register_addr=request_register_addr,
            request_register_qty=request_register_qty,
            request_data=request_data,
            value_list=values,
            signed=signed
        )
        self._send(modbus_pdu=modbus_pdu, slave_addr=slave_addr)

    def send_exception_response(self,
                                slave_addr: int,
                                function_code: int,
                                exception_code: int) -> None:
        """
        Send an exception response to a client.

        :param      slave_addr:      The slave address
        :type       slave_addr:      int
        :param      function_code:   The function code
        :type       function_code:   int
        :param      exception_code:  The exception code
        :type       exception_code:  int
        """
        modbus_pdu = functions.exception_response(
            function_code=function_code,
            exception_code=exception_code)
        self._send(modbus_pdu=modbus_pdu, slave_addr=slave_addr)

    def get_request(self,
                    unit_addr_list: List[int],
                    timeout: Optional[int] = None) -> Union[Request, None]:
        """
        Check for request within the specified timeout

        :param      unit_addr_list:  The unit address list
        :type       unit_addr_list:  Optional[list]
        :param      timeout:         The timeout
        :type       timeout:         Optional[int]

        :returns:   A request object or None.
        :rtype:     Union[Request, None]
        """
        req = self._uart_read_frame(timeout=timeout)

        if len(req) < 8:
            return None

        if req[0] not in unit_addr_list:
            return None

        req_crc = req[-Const.CRC_LENGTH:]
        req_no_crc = req[:-Const.CRC_LENGTH]
        expected_crc = self._calculate_crc16(req_no_crc)

        if (req_crc[0] != expected_crc[0]) or (req_crc[1] != expected_crc[1]):
            return None

        try:
            request = Request(interface=self, data=req_no_crc)
        except ModbusException as e:
            self.send_exception_response(
                slave_addr=req[0],
                function_code=e.function_code,
                exception_code=e.exception_code)
            return None

        return request
