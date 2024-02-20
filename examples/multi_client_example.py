#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Main script

Do your stuff here, this file is similar to the loop() function on Arduino

Create an async Modbus TCP and RTU client (slave) which run simultaneously,
share the same register definitions, and can be requested for data or set
with specific values by a host device.

The TCP port and IP address, and the RTU communication pins can both be
chosen freely (check MicroPython device/port specific limitations).

The register definitions of the client as well as its connection settings like
bus address and UART communication speed can be defined by the user.
"""

# system imports
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

# import modbus client classes
from umodbus.asynchronous.tcp import AsyncModbusTCP as ModbusTCP
from umodbus.asynchronous.serial import AsyncModbusRTU as ModbusRTU
from examples.common.tcp_client_common import register_definitions
from examples.common.tcp_client_common import local_ip, tcp_port
from examples.common.rtu_client_common import IS_DOCKER_MICROPYTHON
from examples.common.rtu_client_common import slave_addr, rtu_pins
from examples.common.rtu_client_common import baudrate, uart_id, exit
from examples.common.multi_client_sync import sync_registers


async def init_rtu_server(slave_addr,
                          rtu_pins,
                          baudrate,
                          uart_id,
                          **kwargs) -> ModbusRTU:
    """Creates an RTU client."""

    client = ModbusRTU(addr=slave_addr,
                       pins=rtu_pins,
                       baudrate=baudrate,
                       uart_id=uart_id,
                       **kwargs)

    if IS_DOCKER_MICROPYTHON:
        # works only with fake machine UART
        assert client._itf._uart._is_server is True

    # start listening in background
    await client.bind()

    # return client -- do not initialize registers yet
    # as update callbacks have not been added
    return client


async def init_tcp_server(host, port, backlog) -> ModbusTCP:
    client = ModbusTCP()  # TODO: rename to `server`

    # start listening in background
    print('Binding TCP client on {}:{}'.format(local_ip, tcp_port))
    await client.bind(local_ip=host, local_port=port, max_connections=backlog)

    # return client -- do not initialize registers yet
    # as update callbacks have not been added
    return client


async def start_all_servers(*server_tasks):
    all_servers = await asyncio.gather(*server_tasks)
    sync_registers(register_definitions, *all_servers)
    await asyncio.gather(*[server.serve_forever() for server in all_servers])


if __name__ == "__main__":
    # define arbitrary backlog of 10
    backlog = 10

    # create TCP server task
    tcp_server_task = init_tcp_server(local_ip, tcp_port, backlog)

    # create RTU server task
    rtu_server_task = init_rtu_server(addr=slave_addr,
                                      pins=rtu_pins,          # given as tuple (TX, RX)
                                      baudrate=baudrate,      # optional, default 9600
                                      # data_bits=8,          # optional, default 8
                                      # stop_bits=1,          # optional, default 1
                                      # parity=None,          # optional, default None
                                      # ctrl_pin=12,          # optional, control DE/RE
                                      uart_id=uart_id)        # optional, default 1, see port specific docs

    # combine and run both tasks together
    run_servers = start_all_servers(tcp_server_task, rtu_server_task)
    asyncio.run(run_servers)

    exit()
