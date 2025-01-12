#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#
# Description summary taken from
# https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf

from micropython import const

# function codes
# defined as const(), see https://github.com/micropython/micropython/issues/573
#: Read contiguous status of coils
READ_COILS = const(0x01)                # COILS, [0, 1]
#: Read contiguous status of discrete inputs
READ_DISCRETE_INPUTS = const(0x02)      # ISTS,  [0, 1]
#: Read the contents of a contiguous block of holding registers
READ_HOLDING_REGISTERS = const(0x03)    # HREGS, [0, 65535]
#: Read contiguous input registers
READ_INPUT_REGISTER = const(0x04)       # IREGS, [0, 65535]

#: Write a single coil output status to ON or OFF
WRITE_SINGLE_COIL = const(0x05)         # COILS, [0, 1]
#: Write a single holding register
WRITE_SINGLE_REGISTER = const(0x06)     # HREGS, [0, 65535]
#: Force each coil in a sequence of coils to either ON or OFF
WRITE_MULTIPLE_COILS = const(0x0F)      # COILS, [0, 1]
#: Write a block of contiguous registers
WRITE_MULTIPLE_REGISTERS = const(0x10)  # HREGS, [0, 65535]

"""
Modify the contents of a specified holding register using a combination of an
AND mask, an OR mask, and the register's current contents
"""
MASK_WRITE_REGISTER = const(0x16)
"""
Perform a combination of one read operation and one write operation in a
single MODBUS transaction
"""
READ_WRITE_MULTIPLE_REGISTERS = const(0x17)

#: Read the contents of a First-In-First-Out (FIFO) queue of register
READ_FIFO_QUEUE = const(0x18)

#: Perform a file record read
READ_FILE_RECORD = const(0x14)
#: Perform a file record write
WRITE_FILE_RECORD = const(0x15)

#: Read the contents of eight Exception Status outputs
READ_EXCEPTION_STATUS = const(0x07)
#: Provide series of tests for checking the communication system (serial only)
DIAGNOSTICS = const(0x08)
#: Get status word and an event count from the remote device com event counter
GET_COM_EVENT_COUNTER = const(0x0B)
#: Get a status word, event count, message count, and a field of event bytes
GET_COM_EVENT_LOG = const(0x0C)
#: Read the description of the type, the current status, and other informations
REPORT_SERVER_ID = const(0x11)
#: Encapsulated Interface Transport
READ_DEVICE_IDENTIFICATION = const(0x2B)

# exception codes
#: Function code received in query is not an allowable action for the server
ILLEGAL_FUNCTION = const(0x01)
#: Data address received in query is not an allowable address for the server
ILLEGAL_DATA_ADDRESS = const(0x02)
#: A value contained in the query is not an allowable value for the server
ILLEGAL_DATA_VALUE = const(0x03)
"""
An unrecoverable error occurred while the server was attempting to perform the
requested action
"""
SERVER_DEVICE_FAILURE = const(0x04)
#: Response is returned to prevent a timeout error from occurring in the client
ACKNOWLEDGE = const(0x05)
#: Server is engaged in processing a long duration program command
SERVER_DEVICE_BUSY = const(0x06)
#: Server attempted to read record file, but detected a parity error in memory
MEMORY_PARITY_ERROR = const(0x08)
"""
Gateway was unable to allocate an internal communication path from the input
port to the output port for processing the request
"""
GATEWAY_PATH_UNAVAILABLE = const(0x0A)
#: No response was obtained from the target device
DEVICE_FAILED_TO_RESPOND = const(0x0B)

# Protocol Data Unit (PDU) constants
#: CRC length
CRC_LENGTH = const(0x02)
#: Error code offset
ERROR_BIAS = const(0x80)
#: High Data Response length
RESPONSE_HDR_LENGTH = const(0x02)
#: Error response length
ERROR_RESP_LEN = const(0x05)
#: Fixed response length
FIXED_RESP_LEN = const(0x08)
#: Modbus Application Protocol High Data Response length
MBAP_HDR_LENGTH = const(0x07)

#: CRC16 lookup table
CRC16_TABLE = (
    0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241, 0xC601,
    0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440, 0xCC01, 0x0CC0,
    0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40, 0x0A00, 0xCAC1, 0xCB81,
    0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841, 0xD801, 0x18C0, 0x1980, 0xD941,
    0x1B00, 0xDBC1, 0xDA81, 0x1A40, 0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01,
    0x1DC0, 0x1C80, 0xDC41, 0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0,
    0x1680, 0xD641, 0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081,
    0x1040, 0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
    0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441, 0x3C00,
    0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41, 0xFA01, 0x3AC0,
    0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840, 0x2800, 0xE8C1, 0xE981,
    0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41, 0xEE01, 0x2EC0, 0x2F80, 0xEF41,
    0x2D00, 0xEDC1, 0xEC81, 0x2C40, 0xE401, 0x24C0, 0x2580, 0xE541, 0x2700,
    0xE7C1, 0xE681, 0x2640, 0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0,
    0x2080, 0xE041, 0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281,
    0x6240, 0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
    0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41, 0xAA01,
    0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840, 0x7800, 0xB8C1,
    0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41, 0xBE01, 0x7EC0, 0x7F80,
    0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40, 0xB401, 0x74C0, 0x7580, 0xB541,
    0x7700, 0xB7C1, 0xB681, 0x7640, 0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101,
    0x71C0, 0x7080, 0xB041, 0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0,
    0x5280, 0x9241, 0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481,
    0x5440, 0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
    0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841, 0x8801,
    0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40, 0x4E00, 0x8EC1,
    0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41, 0x4400, 0x84C1, 0x8581,
    0x4540, 0x8701, 0x47C0, 0x4680, 0x8641, 0x8201, 0x42C0, 0x4380, 0x8341,
    0x4100, 0x81C1, 0x8081, 0x4040
)

#: Broadcast address
BROADCAST_ADDR = const(0x00)


# Code to generate the CRC-16 lookup table:
# def generate_crc16_table():
#     crc_table = []
#     for byte in range(256):
#         crc = 0x0000
#         for _ in range(8):
#             if (byte ^ crc) & 0x0001:
#                 crc = (crc >> 1) ^ 0xa001
#             else:
#                 crc >>= 1
#             byte >>= 1
#         crc_table.append(crc)
#     return crc_table
