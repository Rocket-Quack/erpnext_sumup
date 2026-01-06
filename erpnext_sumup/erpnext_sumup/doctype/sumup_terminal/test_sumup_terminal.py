# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.doctype.sumup_terminal import sumup_terminal


class Dummy:
	def __init__(self, **kwargs):
		for key, value in kwargs.items():
			setattr(self, key, value)


class DictReader:
	def __init__(self, payload):
		self._payload = payload

	def dict(self, exclude_none=True):
		return dict(self._payload)


class TestSumUpTerminal(FrappeTestCase):
	def test_normalize_pairing_code(self):
		self.assertEqual(sumup_terminal._normalize_pairing_code(" abcd-1234 "), "ABCD1234")
		with self.assertRaises(frappe.ValidationError):
			sumup_terminal._normalize_pairing_code("")
		with self.assertRaises(frappe.ValidationError):
			sumup_terminal._normalize_pairing_code("123")
		with self.assertRaises(frappe.ValidationError):
			sumup_terminal._normalize_pairing_code("invalid-code!")

	def test_normalize_terminal_name(self):
		self.assertEqual(sumup_terminal._normalize_terminal_name(" Main "), "Main")
		with self.assertRaises(frappe.ValidationError):
			sumup_terminal._normalize_terminal_name("  ")

	def test_parse_terminal_names(self):
		self.assertEqual(sumup_terminal._parse_terminal_names(None), [])
		self.assertEqual(sumup_terminal._parse_terminal_names("[]"), [])
		self.assertEqual(
			sumup_terminal._parse_terminal_names('["A", "B"]'),
			["A", "B"],
		)
		self.assertEqual(sumup_terminal._parse_terminal_names('"A"'), ["A"])
		self.assertEqual(sumup_terminal._parse_terminal_names("Terminal A"), ["Terminal A"])
		self.assertEqual(sumup_terminal._parse_terminal_names(["A", "B"]), ["A", "B"])
		self.assertEqual(sumup_terminal._parse_terminal_names({"name": "A"}), [{"name": "A"}])

	def test_normalize_status_values(self):
		self.assertEqual(sumup_terminal._normalize_connection_status("paired"), "Paired")
		self.assertEqual(sumup_terminal._normalize_connection_status("processing"), "Processing")
		self.assertEqual(sumup_terminal._normalize_connection_status("expired"), "Expired")
		self.assertEqual(sumup_terminal._normalize_connection_status("other"), "Unknown")
		self.assertEqual(sumup_terminal._normalize_connection_status(None), "Unknown")

		self.assertEqual(sumup_terminal._normalize_online_status("online"), "Online")
		self.assertEqual(sumup_terminal._normalize_online_status("offline"), "Offline")
		self.assertEqual(sumup_terminal._normalize_online_status("other"), "Unknown")
		self.assertEqual(sumup_terminal._normalize_online_status(None), "Unknown")

		self.assertEqual(sumup_terminal._normalize_activity_status("idle"), "Idle")
		self.assertEqual(sumup_terminal._normalize_activity_status("SELECTING_TIP"), "Selecting Tip")
		self.assertEqual(sumup_terminal._normalize_activity_status("waiting_for_card"), "Waiting For Card")
		self.assertEqual(sumup_terminal._normalize_activity_status("n/a"), "Unknown")

	def test_extract_status_payload(self):
		self.assertEqual(
			sumup_terminal._extract_status_payload({"data": {"status": "ONLINE"}}),
			{"status": "ONLINE"},
		)
		response = Dummy(data={"status": "OFFLINE"})
		self.assertEqual(sumup_terminal._extract_status_payload(response), {"status": "OFFLINE"})
		self.assertEqual(sumup_terminal._extract_status_payload(None), {})

	def test_extract_reader_items_and_data(self):
		self.assertEqual(sumup_terminal._extract_reader_items(None), [])
		self.assertEqual(sumup_terminal._extract_reader_items(Dummy(items=[1, 2])), [1, 2])
		self.assertEqual(sumup_terminal._extract_reader_items({"items": ["A"]}), ["A"])

		reader_id, status = sumup_terminal._extract_reader_data(Dummy(id=123, status="Paired"))
		self.assertEqual(reader_id, "123")
		self.assertEqual(status, "Paired")

		reader_id, status = sumup_terminal._extract_reader_data(
			DictReader({"id": 456, "status": "Processing"})
		)
		self.assertEqual(reader_id, "456")
		self.assertEqual(status, "Processing")

	def test_extract_status_values(self):
		self.assertEqual(
			sumup_terminal._extract_activity_status_value({"screen_state": "IDLE"}),
			"IDLE",
		)
		self.assertEqual(
			sumup_terminal._extract_activity_status_value({"screenState": "WAITING_FOR_CARD"}),
			"WAITING_FOR_CARD",
		)
		self.assertEqual(
			sumup_terminal._extract_activity_status_value({"state": "WAITING_FOR_PIN"}),
			"WAITING_FOR_PIN",
		)
		self.assertIsNone(sumup_terminal._extract_activity_status_value({}))

		self.assertEqual(sumup_terminal._extract_online_status_value({"status": "ONLINE"}), "ONLINE")
		self.assertEqual(
			sumup_terminal._extract_online_status_value({"device_status": "OFFLINE"}),
			"OFFLINE",
		)
		self.assertEqual(
			sumup_terminal._extract_online_status_value({"deviceStatus": "OFFLINE"}),
			"OFFLINE",
		)
		self.assertIsNone(sumup_terminal._extract_online_status_value({}))

	def test_format_sumup_error(self):
		class DummyError(Exception):
			def __init__(self):
				super().__init__("boom")
				self.status = 400
				self.body = {"detail": "bad"}

		message = sumup_terminal._format_sumup_error(DummyError())
		self.assertIn("boom", message)
		self.assertIn("status 400", message)
		self.assertIn("body", message)
