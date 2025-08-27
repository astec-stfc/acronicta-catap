import unittest
from unittest.mock import MagicMock

import numpy as np
from p4p.client.thread import Cancelled, Disconnected, RemoteError, TimeoutError
from p4p.nt import NTEnum, NTNDArray
from p4p.nt.enum import ntenum
from p4p.nt.ndarray import ntndarray
from p4p.nt.scalar import ntbool, ntfloat, ntint, ntnumericarray, ntstr, ntstringarray

from catapcore.common.exceptions import FailedEPICSOperationWarning
from catapcore.common.machine.protocol import PVA


def make_example_enum(index=0, choices=["False", "True"]) -> ntenum:
    """
    p4p creation of Enums is still limited so this small fudge is needed to create the
    `ntenum` class, it can't be made directly like the others
    """
    initial = NTEnum.buildType()()
    initial.value.index = index
    initial.value.choices = choices
    enum = NTEnum.unwrap(NTEnum(), initial)
    return enum


def make_example_ntnumericarray(array=np.array([1, 2, 3])) -> ntnumericarray:
    value = ntnumericarray.build(array)
    return value


def make_example_ntndarray(array=np.full((2, 3), 5.0)) -> ntndarray:
    val = NTNDArray().wrap(array)
    value = NTNDArray.unwrap(val)
    return value


class TestPVA(unittest.TestCase):
    def setUp(self):
        self.protocol = PVA(pvname="TEST-PV-1", timeout=0.01)
        self.protocol._ctx = MagicMock()

    def test_connection_callback(self):
        expected_types = [
            (ntfloat(5.0), "ntfloat"),
            (ntint(1), "ntint"),
            (ntstr("test"), "ntstr"),
            (ntbool(True), "ntbool"),
            (make_example_enum(), "ntenum"),
            (make_example_ntnumericarray(), "ntnumericarray"),
            (make_example_ntndarray(), "ntndarray"),
        ]
        for i, (state, expected_type) in enumerate(expected_types):
            self.protocol._connected = False
            with self.subTest(i=i):
                self.protocol._dispatch_callback(state)
                self.assertTrue(self.protocol.connected)
                self.assertEqual(self.protocol.type, expected_type)

    def test_connection_callback_errors(self):
        expected_types = [
            TimeoutError("timeout"),
            Disconnected("disconnected"),
            RemoteError("remote"),
            Cancelled("cancelled"),
        ]
        for i, state in enumerate(expected_types):
            self.protocol._connected = False
            with self.subTest(i=i):
                with self.assertWarns(FailedEPICSOperationWarning) as w:
                    self.protocol._dispatch_callback(state)
                    self.assertTrue(str(state) in str(w.warnings[0].message))

                self.assertFalse(self.protocol.connected)

    def test_get(self):
        expected_values = [
            (ntfloat(5.0), 5.0),
            (ntint(1), 1.0),
            (ntstr("test"), "test"),
            (ntbool(True), 1),
            (make_example_enum(), 0),
        ]
        for i, (state, expected_val) in enumerate(expected_values):
            state.timestamp = 123.456
            with self.subTest(i=i):
                self.protocol._value = None
                self.protocol._timestamp = None
                self.protocol._ctx.get = MagicMock(return_value=state)

                result = self.protocol.get()

                self.assertEqual(self.protocol.value, expected_val)
                self.assertEqual(self.protocol.timestamp, 123.456)
                self.assertEqual(result, expected_val)

    def test_get_array_values(self):
        expected_values = [
            (ntstringarray(["0", "1", "2"]), np.array(["0", "1", "2"])),
            (ntstringarray(np.array(["0", "1", "2"])), np.array(["0", "1", "2"])),
            (make_example_ntnumericarray(), np.array([1, 2, 3])),
            (make_example_ntndarray(np.full((2, 3), 5.0)), np.full((2, 3), 5.0)),
        ]
        for i, (state, expected_val) in enumerate(expected_values):
            state.timestamp = 123.456
            with self.subTest(i=i):
                self.protocol._value = None
                self.protocol._timestamp = None
                self.protocol._ctx.get = MagicMock(return_value=state)

                result = self.protocol.get()

                self.assertIsNone(
                    np.testing.assert_array_equal(self.protocol.value, expected_val)
                )
                self.assertEqual(self.protocol.timestamp, 123.456)
                self.assertIsNone(np.testing.assert_array_equal(result, expected_val))

    def test_get_errors(self):
        error = TimeoutError("timeout")
        self.protocol._ctx.get = MagicMock(return_value=error)

        with self.assertWarns(FailedEPICSOperationWarning) as w:
            self.protocol.get()
            self.assertTrue(str(error) in str(w.warnings[0].message))

        self.assertIsNone(self.protocol._value)
        self.assertIsNone(self.protocol._timestamp)

    def test_put(self):
        self.protocol._ctx.put = MagicMock(return_value=None)
        self.protocol.put(value=5.0)

        self.protocol._ctx.put.assert_called_once_with(
            self.protocol.pvname, 5.0, timeout=self.protocol.timeout, throw=False
        )

    def test_put_errors(self):
        error = TimeoutError("timeout")
        self.protocol._ctx.put = MagicMock(return_value=error)

        with self.assertWarns(FailedEPICSOperationWarning) as w:
            self.protocol.put(value=5.0)
            self.assertTrue(str(error) in str(w.warnings[0].message))
