# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.pos.pos_profile import validate_pos_profile_sumup_terminal


class DummyPayment:
	def __init__(self, use_sumup_terminal, mode_of_payment="Card"):
		self.use_sumup_terminal = use_sumup_terminal
		self.mode_of_payment = mode_of_payment


class DummyDoc:
	def __init__(self, sumup_terminal, payments):
		self.sumup_terminal = sumup_terminal
		self.payments = payments


class TestPOSProfileSumUp(FrappeTestCase):
	def setUp(self):
		self.enabled_terminal = self._create_terminal(enabled=1)
		self.disabled_terminal = self._create_terminal(enabled=0)

	def tearDown(self):
		for terminal in (self.enabled_terminal, self.disabled_terminal):
			if terminal and frappe.db.exists("SumUp Terminal", terminal):
				frappe.delete_doc("SumUp Terminal", terminal, force=1)

	def _create_terminal(self, enabled):
		terminal_id = f"TEST-SUMUP-{frappe.generate_hash(length=8)}"
		doc = frappe.get_doc(
			{
				"doctype": "SumUp Terminal",
				"terminal_id": terminal_id,
				"terminal_name": "Test Terminal",
				"enabled": 1 if enabled else 0,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def test_requires_terminal_when_sumup_payment_used(self):
		doc = DummyDoc(None, [DummyPayment(1)])
		with self.assertRaises(frappe.ValidationError):
			validate_pos_profile_sumup_terminal(doc)

	def test_missing_terminal_raises(self):
		doc = DummyDoc("MISSING-TERMINAL", [DummyPayment(1)])
		with self.assertRaises(frappe.ValidationError):
			validate_pos_profile_sumup_terminal(doc)

	def test_disabled_terminal_raises(self):
		doc = DummyDoc(self.disabled_terminal, [DummyPayment(1)])
		with self.assertRaises(frappe.ValidationError):
			validate_pos_profile_sumup_terminal(doc)

	def test_enabled_terminal_passes(self):
		doc = DummyDoc(self.enabled_terminal, [DummyPayment(1)])
		validate_pos_profile_sumup_terminal(doc)

	def test_no_sumup_payment_skips_validation(self):
		doc = DummyDoc(None, [DummyPayment(0)])
		validate_pos_profile_sumup_terminal(doc)
