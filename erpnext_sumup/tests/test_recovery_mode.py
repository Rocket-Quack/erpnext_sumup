# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.doctype.sumup_terminal import sumup_terminal


class DummyReaders:
	def __init__(self, items):
		self._items = items

	def list(self, merchant_code):
		return SimpleNamespace(items=self._items)


class DummyClient:
	def __init__(self, items):
		self.readers = DummyReaders(items)


class TestRecoveryMode(FrappeTestCase):
	def _make_settings(self, *, enabled=True, recovery=True, merchant_code="MRC-TEST"):
		return SimpleNamespace(
			enabled=1 if enabled else 0,
			enable_recovery_mode=1 if recovery else 0,
			merchant_code=merchant_code,
		)

	def _create_terminal(self, terminal_id, terminal_name):
		doc = frappe.get_doc(
			{
				"doctype": "SumUp Terminal",
				"terminal_id": terminal_id,
				"terminal_name": terminal_name,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.db.exists("SumUp Terminal", doc.name)
			and frappe.delete_doc("SumUp Terminal", doc.name, force=1)
		)
		return doc

	def test_recovery_mode_disabled(self):
		settings = self._make_settings(recovery=False)
		with patch.object(sumup_terminal, "get_sumup_settings", return_value=settings):
			with self.assertRaises(frappe.ValidationError):
				sumup_terminal.recover_terminals_from_sumup()

	def test_recovery_creates_and_updates(self):
		self._create_terminal("READER-1", "Old Name")
		items = [
			SimpleNamespace(id="READER-1", name="New Name"),
			SimpleNamespace(id="READER-2", name="Front Desk"),
		]
		settings = self._make_settings()
		client = DummyClient(items)

		with (
			patch.object(sumup_terminal, "get_sumup_settings", return_value=settings),
			patch.object(sumup_terminal, "get_sumup_client", return_value=client),
		):
			result = sumup_terminal.recover_terminals_from_sumup()

		self.assertEqual(len(result["created"]), 1)
		self.assertEqual(len(result["updated"]), 1)
		self.assertTrue(frappe.db.exists("SumUp Terminal", "READER-2"))

		updated = frappe.get_doc("SumUp Terminal", "READER-1")
		self.assertEqual(updated.terminal_name, "New Name")

	def test_recovery_no_readers(self):
		settings = self._make_settings()
		client = DummyClient([])

		with (
			patch.object(sumup_terminal, "get_sumup_settings", return_value=settings),
			patch.object(sumup_terminal, "get_sumup_client", return_value=client),
		):
			result = sumup_terminal.recover_terminals_from_sumup()

		self.assertEqual(result["created"], [])
		self.assertEqual(result["updated"], [])
		self.assertEqual(result["failed"], [])
