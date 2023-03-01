#!/usr/bin/env python3
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

# system packages
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from ..sys_imports import time, UART, Pin
from ..sys_imports import List, Tuple, Optional, Union

# custom packages
from .common import CommonAsyncModbusFunctions, AsyncRequest
from ..common import ModbusException
from .modbus import AsyncModbus
from ..serial import CommonRTUFunctions

US_TO_S = 1 / 1_000_000


class AsyncModbusRTU(AsyncModbus):
    """
    Asynchronous equivalent of the Modbus RTU class

    @see ModbusRTU
    """
    def __init__(self,
                 addr: int,
                 baudrate: int = 9600,
                 data_bits: int = 8,
                 stop_bits: int = 1,
                 parity: Optional[int] = None,
                 pins: Tuple[Union[int, Pin], Union[int, Pin]] = None,
                 ctrl_pin: int = None,
                 uart_id: int = 1):
        super().__init__(
            # set itf to AsyncSerial object, addr_list to [addr]
            AsyncRTUServer(uart_id=uart_id,
                           baudrate=baudrate,
                           data_bits=data_bits,
                           stop_bits=stop_bits,
                           parity=parity,
                           pins=pins,
                           ctrl_pin=ctrl_pin),
            [addr]
        )


class AsyncRTUServer(CommonRTUFunctions, CommonAsyncModbusFunctions):
    def __init__(self,
                 uart_id: int = 1,
                 baudrate: int = 9600,
                 data_bits: int = 8,
                 stop_bits: int = 1,
                 parity=None,
                 pins: Tuple[Union[int, Pin], Union[int, Pin]] = None,
                 ctrl_pin: int = None):
        """
        Setup asynchronous Serial/RTU Modbus

        @see Serial
        """
        self._uart = UART(uart_id,
                          baudrate=baudrate,
                          bits=data_bits,
                          parity=parity,
                          stop=stop_bits,
                          # timeout_chars=2,  # WiPy only
                          # pins=pins         # WiPy only
                          tx=pins[0],
                          rx=pins[1])

        self._uart_reader = asyncio.StreamReader(self._uart)
        self._uart_writer = asyncio.StreamWriter(self._uart, {})

        if ctrl_pin is not None:
            self._ctrlPin = Pin(ctrl_pin, mode=Pin.OUT)
        else:
            self._ctrlPin = None

        char_const = data_bits + stop_bits + 2
        self._t1char = (1_000_000 * char_const) // baudrate
        if baudrate <= 19200:
            # 4010us (approx. 4ms) @ 9600 baud
            self._t35chars = (3_500_000 * char_const) // baudrate
        else:
            self._t35chars = 1750   # 1750us (approx. 1.75ms)

    async def _uart_read(self) -> bytearray:
        """@see Serial._uart_read"""

        response = bytearray()
        wait_period = self._t35chars * US_TO_S

        for _ in range(1, 40):
            # WiPy only
            # response.extend(await self._uart_reader.readall())
            response.extend(await self._uart_reader.read())

            # variable length function codes may require multiple reads
            if self._exit_read(response):
                break

            # wait for the maximum time between two frames
            await asyncio.sleep(wait_period)

        return response

    async def _uart_read_frame(self,
                               timeout: Optional[int] = None) -> bytearray:
        """@see Serial._uart_read_frame"""

        # set timeout to at least twice the time between two
        # frames in case the timeout was set to zero or None
        if not timeout:
            timeout = 2 * self._t35chars  # in milliseconds

        received_bytes = bytearray()
        total_timeout = timeout * US_TO_S
        frame_timeout = self._t35chars * US_TO_S

        try:
            # wait until overall timeout to read at least one byte
            current_timeout = total_timeout
            while True:
                read_task = self._uart_reader.read()
                data = await asyncio.wait_for(read_task, current_timeout)
                received_bytes.extend(data)

                # if data received, switch to waiting until inter-frame
                # timeout is exceeded, to delineate two separate frames
                current_timeout = frame_timeout
        except asyncio.TimeoutError:
            pass  # stop when no data left to read before timeout
        return received_bytes

    async def _send(self,
                    modbus_pdu: bytes,
                    slave_addr: int) -> None:
        """@see Serial._send"""

        serial_pdu = self._form_serial_pdu(modbus_pdu, slave_addr)
        send_start_time = 0

        if self._ctrlPin:
            self._ctrlPin(1)
            # wait 1 ms to ensure control pin has changed
            await asyncio.sleep(1/1000)
            send_start_time = time.ticks_us()

        self._uart_writer.write(serial_pdu)
        await self._uart_writer.drain()

        if self._ctrlPin:
            total_frame_time_us = self._t1char * len(serial_pdu)
            target_time = send_start_time + total_frame_time_us
            time_difference = target_time - time.ticks_us()
            # idle until data sent
            await asyncio.sleep(time_difference * US_TO_S)
            self._ctrlPin(0)

    async def _send_receive(self,
                            slave_addr: int,
                            modbus_pdu: bytes,
                            count: bool) -> bytes:
        """@see Serial._send_receive"""

        # flush the Rx FIFO
        await self._uart_reader.read()
        await self._send(modbus_pdu=modbus_pdu, slave_addr=slave_addr)

        response = await self._uart_read()
        return self._validate_resp_hdr(response=response,
                                       slave_addr=slave_addr,
                                       function_code=modbus_pdu[0],
                                       count=count)

    async def send_response(self,
                            slave_addr: int,
                            function_code: int,
                            request_register_addr: int,
                            request_register_qty: int,
                            request_data: list,
                            values: Optional[list] = None,
                            signed: bool = True,
                            request: Optional[AsyncRequest] = None) -> None:
        """
        Asynchronous equivalent to Serial.send_response
        @see Serial.send_response for common (leading) parameters

        :param      request:     Ignored; kept for compatibility
                                 with AsyncRequest
        :type       request:     AsyncRequest, optional
        """

        task = super().send_response(slave_addr=slave_addr,
                                     function_code=function_code,
                                     request_register_addr=request_register_addr,  # noqa: E501
                                     request_register_qty=request_register_qty,
                                     request_data=request_data,
                                     values=values,
                                     signed=signed)
        if task is not None:
            await task

    async def send_exception_response(self,
                                      slave_addr: int,
                                      function_code: int,
                                      exception_code: int,
                                      request: Optional[AsyncRequest] = None) \
            -> None:
        """
        Asynchronous equivalent to Serial.send_exception_response
        @see Serial.send_exception_response for common (leading) parameters

        :param      request:     Ignored; kept for compatibility
                                 with AsyncRequest
        :type       request:     AsyncRequest, optional
        """

        task = super().send_exception_response(slave_addr=slave_addr,
                                               function_code=function_code,
                                               exception_code=exception_code)
        if task is not None:
            await task

    async def get_request(self,
                          unit_addr_list: Optional[List[int]] = None,
                          timeout: Optional[int] = None) -> \
            Optional[AsyncRequest]:
        """@see Serial.get_request"""

        req = await self._uart_read_frame(timeout=timeout)
        req_no_crc = self._parse_request(req=req,
                                         unit_addr_list=unit_addr_list)
        try:
            if req_no_crc is not None:
                return AsyncRequest(interface=self, data=req_no_crc)
        except ModbusException as e:
            await self.send_exception_response(slave_addr=req[0],
                                               function_code=e.function_code,
                                               exception_code=e.exception_code)
