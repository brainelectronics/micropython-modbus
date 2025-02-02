#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Unittest for testing functions of umodbus"""

import json
from random import randint
import struct
import ulogging as logging
import mpy_unittest as unittest
from umodbus.tcp import TCP as ModbusTCPMaster


class TestTcpExample(unittest.TestCase):
    def setUp(self) -> None:
        """Run before every test method"""
        # set basic config and level for the logger
        logging.basicConfig(level=logging.INFO)

        # create a logger for this TestSuite
        self.test_logger = logging.getLogger(__name__)

        # set the test logger level
        self.test_logger.setLevel(logging.DEBUG)

        # enable/disable the log output of the device logger for the tests
        # if enabled log data inside this test will be printed
        self.test_logger.disabled = False

        self._client_tcp_port = 502     # port of client
        self._client_addr = 10          # bus address of client
        self._client_ip = '172.24.0.2'  # static Docker IP address
        self._host = ModbusTCPMaster(
            slave_ip=self._client_ip,
            slave_port=self._client_tcp_port,
            timeout=5.0)

        test_register_file = 'registers/example.json'
        try:
            with open(test_register_file, 'r') as file:
                self._register_definitions = json.load(file)
        except Exception as e:
            self.test_logger.error(
                'Is the test register file available at {}?'.format(
                    test_register_file))
            raise e

    def test_setup(self) -> None:
        """Test successful setup of ModbusTCPMaster and the defined register"""
        self.assertEqual(self._host.trans_id_ctr, 0)
        self.assertIsInstance(self._register_definitions, dict)

        for reg_type in ['COILS', 'HREGS', 'ISTS', 'IREGS']:
            with self.subTest(reg_type=reg_type):
                self.assertIn(reg_type, self._register_definitions.keys())
                self.assertIsInstance(self._register_definitions[reg_type],
                                      dict)
                self.assertGreaterEqual(
                    len(self._register_definitions[reg_type]), 1)

    def test__create_mbap_hdr(self) -> None:
        """Test creating a Modbus header"""
        trans_id = randint(1, 1000)     # create a random transaction ID
        modbus_pdu = b'\x05\x00\x7b\xff\x00'    # WRITE_SINGLE_COIL 123 to True
        self._host.trans_id_ctr = trans_id

        # 0x00 0x06 is the length of the Modbus Protocol Data Unit +1
        # 0x0A is the cliend address
        expectation = (struct.pack('>H', trans_id) + b'\x00\x00\x00\x06\x0A',
                       trans_id)

        result = self._host._create_mbap_hdr(slave_addr=self._client_addr,
                                             modbus_pdu=modbus_pdu)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), len(expectation))
        self.assertEqual(result, expectation)
        self.assertEqual(self._host.trans_id_ctr, trans_id + 1)

    def test__validate_resp_hdr(self) -> None:
        """Test response header validation"""
        # positive path
        # similar to @params in python
        parameters = [
            # (response, transaction ID, function_code, expectation)
            # reading a single coil
            (b'\x00\x01\x00\x00\x00\x04\x0a\x01\x01\x01', 1, 1, b'\x01\x01'),
            (b'\x00\x02\x00\x00\x00\x04\x0a\x01\x01\x01', 2, 1, b'\x01\x01'),
            # reading an input register
            (b'\x00\x03\x00\x00\x00\x04\x0a\x02\x01\x00', 3, 2, b'\x01\x00'),
            # reading a holding register
            (
                b'\x00\x04\x00\x00\x00\x05\x0a\x03\x02\x00\x13',
                4,  # transaction ID
                3,  # function code
                b'\x02\x00\x13'
            ),
            # setting an input register
            (
                b'\x00\x05\x00\x00\x00\x05\x0a\x04\x02\xea\x0a',
                5,  # transaction ID
                4,  # function code
                b'\x02\xea\x0a'
            ),
            # setting a single coil
            (
                b'\x00\x06\x00\x00\x00\x06\x0a\x05\x00\x7b\x00\x00',
                6,  # transaction ID
                5,  # function code
                b'\x00\x7b\x00\x00'
            ),
            # setting a holding register
            (
                b'\x00\x07\x00\x00\x00\x06\x0a\x06\x00\x5d\x00\x14',
                7,  # transaction ID
                6,  # function code
                b'\x00\x5d\x00\x14'
            ),
        ]

        for pair in parameters:
            with self.subTest(pair=pair):
                response = pair[0]
                trans_id = pair[1]
                function_code = pair[2]
                expectation = pair[3]

                result = self._host._validate_resp_hdr(
                    response=response,
                    trans_id=trans_id,
                    slave_addr=self._client_addr,
                    function_code=function_code)
                self.test_logger.debug('result: {}, expectation: {}'.format(
                    result, expectation))

                self.assertIsInstance(result, bytes)
                self.assertEqual(result, expectation)

        # negative path, trigger asserts
        data = {
            #               TID                 SID FC
            'input': b'\x00\x09\x00\x00\x00\x05\x0a\x03\x02\x00\x13',
            'tid': 9,   # transaction ID
            'sid': 10,  # slave ID
            'fid': 3,   # function code, read holding register
            'response': b'\x02\x00\x13'
        }
        # trigger wrong transaction ID assert
        with self.assertRaises(ValueError):
            self._host._validate_resp_hdr(
                response=response,
                trans_id=data['tid'] + 1,
                slave_addr=data['sid'],
                function_code=data['fid'])

        # trigger wrong function ID/throw Modbus exception code assert
        with self.assertRaises(ValueError):
            self._host._validate_resp_hdr(
                response=response,
                trans_id=data['tid'],
                slave_addr=data['sid'],
                function_code=data['fid'] + 1)

        # trigger wrong slave ID assert
        with self.assertRaises(ValueError):
            self._host._validate_resp_hdr(
                response=response,
                trans_id=data['tid'],
                slave_addr=data['sid'] + 1,
                function_code=data['fid'])

    @unittest.skip('Test not yet implemented')
    def test__send_receive(self) -> None:
        pass

    def test_read_coils_single(self) -> None:
        """Test reading sinlge coil of client"""
        # read coil with state ON/True
        coil_address = \
            self._register_definitions['COILS']['EXAMPLE_COIL']['register']
        coil_qty = self._register_definitions['COILS']['EXAMPLE_COIL']['len']
        expectation_list = [
            bool(self._register_definitions['COILS']['EXAMPLE_COIL']['val'])
        ]

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug('Status of COIL {}: {}, expectation: {}'.
                               format(coil_address,
                                      coil_status,
                                      expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        # read coil with state OFF/False
        coil_address = \
            self._register_definitions['COILS']['EXAMPLE_COIL_OFF']['register']
        coil_qty = \
            self._register_definitions['COILS']['EXAMPLE_COIL_OFF']['len']
        expectation_list = [bool(
            self._register_definitions['COILS']['EXAMPLE_COIL_OFF']['val']
        )]

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug('Status of COIL {}: {}, expectation: {}'.
                               format(coil_address,
                                      coil_status,
                                      expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

    def test_read_coils_multiple(self) -> None:
        """Test reading multiple coils of client"""
        coil_address = \
            self._register_definitions['COILS']['EXAMPLE_COIL_MIXED']['register']     # noqa: E501
        coil_qty = \
            self._register_definitions['COILS']['EXAMPLE_COIL_MIXED']['len']
        expectation_list = list(
            map(bool,
                self._register_definitions['COILS']['EXAMPLE_COIL_MIXED']['val']    # noqa: E501
                )
        )

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        coil_address = \
            self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['register']     # noqa: E501
        coil_qty = \
            self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['len']
        expectation_list = list(
            map(bool,
                self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['val']    # noqa: E501
                )
        )

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        coil_address = \
            self._register_definitions['COILS']['MANY_COILS']['register']
        coil_qty = \
            self._register_definitions['COILS']['MANY_COILS']['len']
        expectation_list = list(
            map(bool, self._register_definitions['COILS']['MANY_COILS']['val'])
        )

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

    # Reading coil data bits is reversed
    # see https://github.com/brainelectronics/micropython-modbus/issues/38
    #
    # Read/Write register at some location of definition
    # see https://github.com/brainelectronics/micropython-modbus/issues/35
    def test_read_coils_partially(self) -> None:
        """Test reading coils partially of client"""
        coil_address = \
            self._register_definitions['COILS']['MANY_COILS']['register']
        coil_qty = \
            self._register_definitions['COILS']['MANY_COILS']['len']
        expectation_list_full = list(
            map(bool,
                self._register_definitions['COILS']['MANY_COILS']['val'])
        )

        coil_qty_less_8 = randint(2, 7)
        coil_qty_more_8 = randint(8, coil_qty - 1)
        possibilities = [coil_qty_less_8, coil_qty_more_8]

        for partial_coil_qty in possibilities:
            with self.subTest(partial_coil_qty=partial_coil_qty):
                expectation_list_partial = \
                    expectation_list_full[:partial_coil_qty]

                coil_status = self._host.read_coils(
                    slave_addr=self._client_addr,
                    starting_addr=coil_address,
                    coil_qty=partial_coil_qty)

                self.test_logger.debug(
                    'Status of COIL {} length {}/{}: {}, expectation: {}'.
                    format(coil_address, partial_coil_qty, coil_qty,
                           coil_status, expectation_list_partial))
                self.assertIsInstance(coil_status, list)
                self.assertEqual(len(coil_status), partial_coil_qty)
                self.assertTrue(all(isinstance(x, bool) for x in coil_status))
                self.assertEqual(coil_status, expectation_list_partial)

    def test_read_coils_specific_of_multiple(self) -> None:
        """Test reading specific coils of client defined as list"""
        # the offset based on the specified register
        # e.g. register = 150, offset = 3, qty = 5, the requested coils are
        # 153-158
        base_coil_offset = 3
        coil_qty = 5    # read only 5 coils of multiple defined ones

        coil_address = (
            self._register_definitions['COILS']['MANY_COILS']['register'] +
            base_coil_offset
        )
        expectation_list_full = list(
            map(bool,
                self._register_definitions['COILS']['MANY_COILS']['val'])
        )
        expectation_list = expectation_list_full[
            base_coil_offset:base_coil_offset + coil_qty
        ]

        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.
            format(coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

    def test_read_discrete_inputs_single(self) -> None:
        """Test reading discrete inputs of client"""
        ist_address = \
            self._register_definitions['ISTS']['EXAMPLE_ISTS']['register']
        input_qty = self._register_definitions['ISTS']['EXAMPLE_ISTS']['len']
        expectation_list = [
            bool(self._register_definitions['ISTS']['EXAMPLE_ISTS']['val'])
        ]

        input_status = self._host.read_discrete_inputs(
            slave_addr=self._client_addr,
            starting_addr=ist_address,
            input_qty=input_qty)

        self.test_logger.debug('Status of IST {}: {}, expectation: {}'.
                               format(ist_address,
                                      input_status,
                                      expectation_list))
        self.assertIsInstance(input_status, list)
        self.assertEqual(len(input_status), input_qty)
        self.assertTrue(all(isinstance(x, bool) for x in input_status))
        self.assertEqual(input_status, expectation_list)

    def test_read_discrete_inputs_multiple(self) -> None:
        """Test reading multiple discrete inputs of client"""
        ist_address = \
            self._register_definitions['ISTS']['EXAMPLE_ISTS_MIXED']['register']     # noqa: E501
        input_qty = \
            self._register_definitions['ISTS']['EXAMPLE_ISTS_MIXED']['len']
        expectation_list = \
            self._register_definitions['ISTS']['EXAMPLE_ISTS_MIXED']['val']

        input_status = self._host.read_discrete_inputs(
            slave_addr=self._client_addr,
            starting_addr=ist_address,
            input_qty=input_qty)

        self.test_logger.debug(
            'Status of IST {} length {}: {}, expectation: {}'.format(
                ist_address, input_qty, input_status, expectation_list))
        self.assertIsInstance(input_status, list)
        self.assertEqual(len(input_status), input_qty)
        self.assertTrue(all(isinstance(x, bool) for x in input_status))
        # self.assertEqual(input_status, expectation_list)

        ist_address = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['register']     # noqa: E501
        input_qty = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['len']
        expectation_list = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['val']

        input_status = self._host.read_discrete_inputs(
            slave_addr=self._client_addr,
            starting_addr=ist_address,
            input_qty=input_qty)

        self.test_logger.debug(
            'Status of IST {} length {}: {}, expectation: {}'.format(
                ist_address, input_qty, input_status, expectation_list))
        self.assertIsInstance(input_status, list)
        self.assertEqual(len(input_status), input_qty)
        self.assertTrue(all(isinstance(x, bool) for x in input_status))
        self.assertEqual(input_status, expectation_list)

    # Read/Write register at some location of definition
    # see https://github.com/brainelectronics/micropython-modbus/issues/35
    def test_read_discrete_inputs_partially(self) -> None:
        """Test reading discrete inputs partially of client"""
        ist_address = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['register']     # noqa: E501
        input_qty = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['len']
        expectation_list_full = \
            self._register_definitions['ISTS']['ANOTHER_EXAMPLE_ISTS']['val']

        input_qty_less = input_qty - 1
        possibilities = [input_qty_less]

        for partial_input_qty in possibilities:
            with self.subTest(partial_input_qty=partial_input_qty):
                expectation_list_partial = \
                    expectation_list_full[:partial_input_qty]

                input_status = self._host.read_discrete_inputs(
                    slave_addr=self._client_addr,
                    starting_addr=ist_address,
                    input_qty=partial_input_qty)

                self.test_logger.debug(
                    'Status of IST {} length {}/{}: {}, expectation: {}'.
                    format(ist_address, partial_input_qty, input_qty,
                           input_status, expectation_list_partial))
                self.assertIsInstance(input_status, list)
                self.assertEqual(len(input_status), partial_input_qty)
                self.assertTrue(all(isinstance(x, bool) for x in input_status))
                self.assertEqual(input_status, expectation_list_partial)

    def test_read_holding_registers_single(self) -> None:
        """Test reading holding registers of client"""
        # read holding register with negative value
        hreg_address = \
            self._register_definitions['HREGS']['EXAMPLE_HREG_NEGATIVE']['register']    # noqa: E501
        register_qty = \
            self._register_definitions['HREGS']['EXAMPLE_HREG_NEGATIVE']['len']

        setup_val = \
            self._register_definitions['HREGS']['EXAMPLE_HREG_NEGATIVE']['val']
        # ensure the register value defined in the JSON is really negative
        self.assertLessEqual(setup_val, -1)

        expectation = (setup_val, )     # tuple is returned

        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug('Status of HREG {}: {}, expectation: {}'.
                               format(hreg_address,
                                      register_value,
                                      expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

        # read holding register with positive value
        hreg_address = \
            self._register_definitions['HREGS']['EXAMPLE_HREG']['register']
        register_qty = \
            self._register_definitions['HREGS']['EXAMPLE_HREG']['len']
        expectation = \
            (self._register_definitions['HREGS']['EXAMPLE_HREG']['val'], )

        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug('Status of HREG {}: {}, expectation: {}'.
                               format(hreg_address,
                                      register_value,
                                      expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

    def test_read_holding_registers_multiple(self) -> None:
        """Test reading multiple holding registers of client"""
        hreg_address = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['register']     # noqa: E501
        register_qty = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['len']
        expectation = tuple(
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['val']
        )

        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug(
            'Status of HREG {} length {}: {}, expectation: {}'.format(
                hreg_address, register_qty, register_value, expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

    # Read/Write register at some location of definition
    # see https://github.com/brainelectronics/micropython-modbus/issues/35
    def test_read_holding_registers_partially(self) -> None:
        """Test reading holding registers partially of client"""
        hreg_address = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['register']     # noqa: E501
        register_qty = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['len']
        expectation_tuple_full = tuple(
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['val']
        )
        register_qty_less = register_qty - 1
        possibilities = [register_qty_less]

        for partial_register_qty in possibilities:
            with self.subTest(partial_register_qty=partial_register_qty):
                expectation_tuple_partial = \
                    expectation_tuple_full[:partial_register_qty]

                register_value = self._host.read_holding_registers(
                    slave_addr=self._client_addr,
                    starting_addr=hreg_address,
                    register_qty=partial_register_qty)

                self.test_logger.debug(
                    'Status of HREG {} length {}/{}: {}, expectation: {}'.
                    format(hreg_address, partial_register_qty, register_qty,
                           register_value, expectation_tuple_partial))
                self.assertIsInstance(register_value, tuple)
                self.assertEqual(len(register_value), partial_register_qty)
                self.assertTrue(all(isinstance(x, int)
                                for x in register_value))
                self.assertEqual(register_value, expectation_tuple_partial)

    def test_read_input_registers_single(self) -> None:
        """Test reading input registers of client"""
        ireg_address = \
            self._register_definitions['IREGS']['EXAMPLE_IREG']['register']
        register_qty = \
            self._register_definitions['IREGS']['EXAMPLE_IREG']['len']
        expectation = \
            (self._register_definitions['IREGS']['EXAMPLE_IREG']['val'], )

        # due to value increment by registered callback in
        # tcp_client_example.py, see #31 and #51
        expectation = (expectation[0] + 1, )

        register_value = self._host.read_input_registers(
            slave_addr=self._client_addr,
            starting_addr=ireg_address,
            register_qty=register_qty,
            signed=False)

        self.test_logger.debug('Status of IREG {}: {}, expectation: {}'.
                               format(ireg_address,
                                      register_value,
                                      expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

    def test_read_input_registers_multiple(self) -> None:
        """Test reading multiple input registers of client"""
        ireg_address = \
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['register']     # noqa: E501
        register_qty = \
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['len']
        expectation = tuple(
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['val']
        )

        register_value = self._host.read_input_registers(
            slave_addr=self._client_addr,
            starting_addr=ireg_address,
            register_qty=register_qty,
            signed=False)

        self.test_logger.debug(
            'Status of IREG {} length {}: {}, expectation: {}'.format(
                ireg_address, register_qty, register_value, expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

    # Read/Write register at some location of definition
    # see https://github.com/brainelectronics/micropython-modbus/issues/35
    def test_read_input_registers_partially(self) -> None:
        """Test reading input registers partially of client"""
        ireg_address = \
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['register']     # noqa: E501
        register_qty = \
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['len']
        expectation_tuple_full = tuple(
            self._register_definitions['IREGS']['ANOTHER_EXAMPLE_IREG']['val']
        )
        register_qty_less = register_qty - 1
        possibilities = [register_qty_less]

        for partial_register_qty in possibilities:
            with self.subTest(partial_register_qty=partial_register_qty):
                expectation_tuple_partial = \
                    expectation_tuple_full[:partial_register_qty]

                register_value = self._host.read_input_registers(
                    slave_addr=self._client_addr,
                    starting_addr=ireg_address,
                    register_qty=partial_register_qty,
                    signed=False)

                self.test_logger.debug(
                    'Status of IREG {} length {}/{}: {}, expectation: {}'.
                    format(ireg_address, partial_register_qty, register_qty,
                           register_value, expectation_tuple_partial))
                self.assertIsInstance(register_value, tuple)
                self.assertEqual(len(register_value), partial_register_qty)
                self.assertTrue(all(isinstance(x, int)
                                for x in register_value))
                self.assertEqual(register_value, expectation_tuple_partial)

    def test_reset_client_data(self) -> None:
        """Test resettig client data to default"""
        coil_address = \
            self._register_definitions['COILS']['RESET_REGISTER_DATA_COIL']['register']     # noqa: E501
        coil_qty = \
            self._register_definitions['COILS']['RESET_REGISTER_DATA_COIL']['len']  # noqa: E501

        operation_status = self._host.write_single_coil(
            slave_addr=self._client_addr,
            output_address=coil_address,
            output_value=True)

        self.test_logger.debug(
            'Result of setting COIL {} to {}: {}, expectation: {}'.format(
                coil_address, True, operation_status, [True]))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # The coil value is actually True for a very short time

        # verify setting of state by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {}: {}, expectation: {}'.format(
                coil_address, coil_status, [False]))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, [False])

    def test_write_single_coil(self) -> None:
        """Test updating single coil of client"""
        coil_address = \
            self._register_definitions['COILS']['EXAMPLE_COIL']['register']
        coil_qty = self._register_definitions['COILS']['EXAMPLE_COIL']['len']
        expectation_list = [
            bool(self._register_definitions['COILS']['EXAMPLE_COIL']['val'])
        ]

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading coil states
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Initial status of COIL {}: {}, expectation: {}'.format(
                coil_address,
                coil_status,
                expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coil to True
        #
        # update coil state of client with a different than the current state
        new_coil_val = not expectation_list[0]
        expectation_list[0] = new_coil_val

        operation_status = self._host.write_single_coil(
            slave_addr=self._client_addr,
            output_address=coil_address,
            output_value=new_coil_val)

        self.test_logger.debug(
            '1. Result of setting COIL {} to {}: {}, expectation: {}'.format(
                coil_address, new_coil_val, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of state by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug('1. Status of COIL {}: {}, expectation: {}'.
                               format(coil_address,
                                      coil_status,
                                      expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coil to False
        #
        # update coil state of client again with/to original state
        new_coil_val = not expectation_list[0]
        expectation_list[0] = new_coil_val

        operation_status = self._host.write_single_coil(
            slave_addr=self._client_addr,
            output_address=coil_address,
            output_value=new_coil_val)

        self.test_logger.debug(
            '2. Result of setting COIL {} to {}: {}, expectation: {}'.format(
                coil_address, new_coil_val, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of state by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug('2. Status of COIL {}: {}, expectation: {}'.
                               format(coil_address,
                                      coil_status,
                                      expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        # test setting a coil in a list of coils
        base_coil_offset = 3
        coil_qty = 1
        coil_address = (
            self._register_definitions['COILS']['MANY_COILS']['register'] +
            base_coil_offset
        )
        expectation_list_full = list(
            map(bool,
                self._register_definitions['COILS']['MANY_COILS']['val'])
        )
        expectation_list = expectation_list_full[
            base_coil_offset:base_coil_offset + coil_qty
        ]

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading coil states
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Initial status of COIL {}: {}, expectation: {}'.format(
                coil_address,
                coil_status,
                expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coil to True
        #
        # update coil state of client with a different than the current state
        new_coil_val = not expectation_list[0]
        expectation_list[0] = new_coil_val

        operation_status = self._host.write_single_coil(
            slave_addr=self._client_addr,
            output_address=coil_address,
            output_value=new_coil_val)

        self.test_logger.debug(
            'Result of setting COIL {} to {}: {}, expectation: {}'.format(
                coil_address, new_coil_val, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of state by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug('Status of COIL {}: {}, expectation: {}'.
                               format(coil_address,
                                      coil_status,
                                      expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

    def test_write_single_register(self) -> None:
        """Test updating single holding register of client"""
        hreg_address = \
            self._register_definitions['HREGS']['EXAMPLE_HREG']['register']
        register_qty = \
            self._register_definitions['HREGS']['EXAMPLE_HREG']['len']
        expectation = \
            (self._register_definitions['HREGS']['EXAMPLE_HREG']['val'], )

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading holding register data
        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug(
            'Initial status of HREG {}: {}, expectation: {}'.format(
                hreg_address,
                register_value,
                expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

        #
        # Test setting holding register to x+1
        #
        # update holding register of client with a different than the current
        # value
        new_hreg_val = \
            self._register_definitions['HREGS']['EXAMPLE_HREG']['val'] + 1

        operation_status = self._host.write_single_register(
            slave_addr=self._client_addr,
            register_address=hreg_address,
            register_value=new_hreg_val,
            signed=False)
        self.test_logger.debug(
            '1. Result of setting HREG {} to {}: {}, expectation: {}'.format(
                hreg_address, new_hreg_val, operation_status, (new_hreg_val, )))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of state by reading data back again
        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug('1. Status of HREG {}: {}, expectation: {}'.
                               format(hreg_address,
                                      register_value,
                                      new_hreg_val))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, (new_hreg_val, ))

    def test_write_multiple_coils(self) -> None:
        """Test updating multiple coils of client"""
        # test with less than 8 coils
        coil_address = \
            self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['register']     # noqa: E501
        coil_qty = \
            self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['len']
        expectation_list = list(
            map(bool,
                self._register_definitions['COILS']['ANOTHER_EXAMPLE_COIL']['val']    # noqa: E501
                )
        )

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading coil states
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Initial status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coils to inverted initial states
        #
        # update coil states of client with a different than the current state
        new_coil_vals = [not val for val in expectation_list]
        expectation_list = new_coil_vals

        operation_status = self._host.write_multiple_coils(
            slave_addr=self._client_addr,
            starting_address=coil_address,
            output_values=new_coil_vals)

        self.test_logger.debug(
            'Result of setting COIL {} length {} to {}: {}, expectation: {}'.
            format(
                coil_address, coil_qty, new_coil_vals, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of states by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        # test with more than 8 coils
        coil_address = \
            self._register_definitions['COILS']['MANY_COILS']['register']
        coil_qty = \
            self._register_definitions['COILS']['MANY_COILS']['len']
        expectation_list = list(
            map(bool, self._register_definitions['COILS']['MANY_COILS']['val'])
        )

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading coil states
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Initial status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coils to inverted initial states
        #
        # update coil states of client with a different than the current state
        new_coil_vals = [not val for val in expectation_list]
        expectation_list = new_coil_vals

        operation_status = self._host.write_multiple_coils(
            slave_addr=self._client_addr,
            starting_address=coil_address,
            output_values=new_coil_vals)

        self.test_logger.debug(
            'Result of setting COIL {} length {} to {}: {}, expectation: {}'.
            format(
                coil_address, coil_qty, new_coil_vals, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of states by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        # Reading coil data bits is reversed, see #38
        # https://github.com/brainelectronics/micropython-modbus/issues/38
        # self.assertEqual(coil_status, expectation_list)

    def test_write_multiple_coils_specific_of_multiple(self) -> None:
        """Test updating specific coils of client defined as list"""
        # test with more than 8 coils
        coil_address = \
            self._register_definitions['COILS']['MANY_COILS']['register']
        coil_qty = \
            self._register_definitions['COILS']['MANY_COILS']['len']
        expectation_list = list(
            map(bool, self._register_definitions['COILS']['MANY_COILS']['val'])
        )

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading coil states
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Initial status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        self.assertEqual(coil_status, expectation_list)

        #
        # Test setting coils to inverted initial states
        #
        # update coil states of client with a different than the current state
        new_coil_vals_full = [not val for val in expectation_list]

        # the offset based on the specified register
        # e.g. register = 150, offset = 3, qty = 5, the requested coils are
        # 153-158
        base_coil_offset = 3
        coil_qty = 5    # read only 5 coils of multiple defined ones

        new_coil_vals = new_coil_vals_full[
            base_coil_offset:(base_coil_offset + coil_qty)
        ]
        expectation_list = (
            expectation_list[:base_coil_offset] +
            new_coil_vals +
            expectation_list[base_coil_offset + coil_qty:]
        )

        operation_status = self._host.write_multiple_coils(
            slave_addr=self._client_addr,
            starting_address=coil_address,
            output_values=new_coil_vals)

        self.test_logger.debug(
            'Result of setting COIL {} length {} to {}: {}, expectation: {}'.
            format(
                coil_address, coil_qty, new_coil_vals, operation_status, True))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of states by reading data back again
        coil_status = self._host.read_coils(
            slave_addr=self._client_addr,
            starting_addr=coil_address,
            coil_qty=coil_qty)

        self.test_logger.debug(
            'Status of COIL {} length {}: {}, expectation: {}'.format(
                coil_address, coil_qty, coil_status, expectation_list))
        self.assertIsInstance(coil_status, list)
        self.assertEqual(len(coil_status), coil_qty)
        self.assertTrue(all(isinstance(x, bool) for x in coil_status))
        # Reading coil data bits is reversed, see #38
        # https://github.com/brainelectronics/micropython-modbus/issues/38
        # self.assertEqual(coil_status, expectation_list)

    def test_write_multiple_registers(self) -> None:
        """Test updating multiple holding register of client"""
        hreg_address = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['register']     # noqa: E501
        register_qty = \
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['len']
        expectation = tuple(
            self._register_definitions['HREGS']['ANOTHER_EXAMPLE_HREG']['val']
        )

        #
        # Check clean system (client register data is as initially defined)
        #
        # verify current state by reading holding register data
        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug(
            'Initial status of HREG {} length {}: {}, expectation: {}'.format(
                hreg_address, register_qty, register_value, expectation))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, expectation)

        #
        # Test setting multiple holding registers to random values
        #
        # update holding register of client with a different than the current
        # value, but at least one negative value
        new_hreg_vals = (
            randint(-32768, 32767),
            randint(-32768, -1),
            randint(-32768, 32767),
        )

        operation_status = self._host.write_multiple_registers(
            slave_addr=self._client_addr,
            starting_address=hreg_address,
            register_values=new_hreg_vals,
            signed=True)
        self.test_logger.debug(
            'Result of setting HREG {} length {} to {}: {}, expectation: {}'.
            format(
                hreg_address, register_qty, new_hreg_vals, operation_status,
                new_hreg_vals))
        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)

        # verify setting of state by reading data back again
        register_value = self._host.read_holding_registers(
            slave_addr=self._client_addr,
            starting_addr=hreg_address,
            register_qty=register_qty)

        self.test_logger.debug(
            'Status of HREG {} length {}: {}, expectation: {}'.format(
                hreg_address, register_qty, register_value, new_hreg_vals))
        self.assertIsInstance(register_value, tuple)
        self.assertEqual(len(register_value), register_qty)
        self.assertTrue(all(isinstance(x, int) for x in register_value))
        self.assertEqual(register_value, new_hreg_vals)

    def tearDown(self) -> None:
        """Run after every test method"""
        # reset the client data back to the default values
        coil_address = \
            self._register_definitions['COILS']['RESET_REGISTER_DATA_COIL']['register']     # noqa: E501

        operation_status = self._host.write_single_coil(
            slave_addr=self._client_addr,
            output_address=coil_address,
            output_value=True)

        self.assertIsInstance(operation_status, bool)
        self.assertTrue(operation_status)


if __name__ == '__main__':
    unittest.main()
