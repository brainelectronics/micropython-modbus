#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Auxiliary script

Defines the common imports and functions for running the host
examples for both the synchronous and asynchronous RTU hosts.
"""

IS_DOCKER_MICROPYTHON = False
try:
    import machine
    machine.reset_cause()
except ImportError:
    raise Exception('Unable to import machine, are all fakes available?')
except AttributeError:
    # machine fake class has no "reset_cause" function
    IS_DOCKER_MICROPYTHON = True


def exit():
    if IS_DOCKER_MICROPYTHON:
        import sys
        sys.exit(0)


# ===============================================
# RTU Slave setup
slave_addr = 10             # address on bus of the client/slave

# RTU Master setup
# act as host, collect Modbus data via RTU from a client device
# ModbusRTU can perform serial requests to a client device to get/set data
# check MicroPython UART documentation
# https://docs.micropython.org/en/latest/library/machine.UART.html
# for Device/Port specific setup
#
# RP2 needs "rtu_pins = (Pin(4), Pin(5))" whereas ESP32 can use any pin
# the following example is for an ESP32
# For further details check the latest MicroPython Modbus RTU documentation
# example https://micropython-modbus.readthedocs.io/en/latest/EXAMPLES.html#rtu
rtu_pins = (25, 26)         # (TX, RX)
baudrate = 9600
uart_id = 1
read_timeout = 120

try:
    from machine import Pin
    import os
    from umodbus import version

    os_info = os.uname()
    print('MicroPython infos: {}'.format(os_info))
    print('Used micropthon-modbus version: {}'.format(version.__version__))

    if 'pyboard' in os_info:
        # NOT YET TESTED !
        # https://docs.micropython.org/en/latest/library/pyb.UART.html#pyb-uart
        # (TX, RX) = (X9, X10) = (PB6, PB7)
        uart_id = 1
        # (TX, RX)
        rtu_pins = (Pin(PB6), Pin(PB7))     # noqa: F821
    elif 'esp8266' in os_info:
        # https://docs.micropython.org/en/latest/esp8266/quickref.html#uart-serial-bus
        raise Exception(
            'UART0 of ESP8266 is used by REPL, UART1 can only be used for TX'
        )
    elif 'esp32' in os_info:
        # https://docs.micropython.org/en/latest/esp32/quickref.html#uart-serial-bus
        uart_id = 1
        rtu_pins = (25, 26)             # (TX, RX)
    elif 'rp2' in os_info:
        # https://docs.micropython.org/en/latest/rp2/quickref.html#uart-serial-bus
        uart_id = 0
        rtu_pins = (Pin(0), Pin(1))     # (TX, RX)
except AttributeError:
    pass
except Exception as e:
    raise e

print('Using pins {} with UART ID {}'.format(rtu_pins, uart_id))
