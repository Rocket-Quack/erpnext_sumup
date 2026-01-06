# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.pos import pos_invoice


class DummyReturnDoc:
	def __init__(
		self,
		*,
		name="RET-1",
		return_against="INV-1",
		currency="EUR",
		grand_total=-50,
		rounded_total=-50,
		sumup_refund_status=None,
		sumup_refund_amount=None,
		docstatus=1,
	):
		self.name = name
		self.is_return = 1
		self.return_against = return_against
		self.currency = currency
		self.grand_total = grand_total
		self.rounded_total = rounded_total
		self.sumup_refund_status = sumup_refund_status
		self.sumup_refund_amount = sumup_refund_amount
		self.docstatus = docstatus
		self.sumup_transaction_id = None


class DummyOriginalDoc:
	def __init__(
		self,
		*,
		name="INV-1",
		sumup_transaction_id="TX-1",
		sumup_status="SUCCESSFUL",
		sumup_amount=100,
		sumup_refund_amount=0,
		sumup_currency="EUR",
		currency="EUR",
	):
		self.name = name
		self.sumup_transaction_id = sumup_transaction_id
		self.sumup_status = sumup_status
		self.sumup_amount = sumup_amount
		self.sumup_refund_amount = sumup_refund_amount
		self.sumup_currency = sumup_currency
		self.currency = currency


class DummyTransactions:
	def __init__(self):
		self.calls = []

	def refund(self, transaction_id, payload):
		self.calls.append((transaction_id, payload))


class DummyClient:
	def __init__(self):
		self.transactions = DummyTransactions()


class TestSumUpReturnRefund(FrappeTestCase):
	def _patch_defaults(self):
		return patch(
			"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.get_default",
			return_value=0,
		)

	def _patch_settings(self, enabled=True):
		return patch(
			"erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_settings",
			return_value=SimpleNamespace(enabled=1 if enabled else 0),
		)

	def test_validate_refund_amount_exceeds(self):
		return_doc = DummyReturnDoc(grand_total=-90, rounded_total=-90)
		original_doc = DummyOriginalDoc(sumup_amount=100, sumup_refund_amount=20)

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				return_value=original_doc,
			),
		):
			with self.assertRaises(frappe.ValidationError):
				pos_invoice.validate_sumup_return_refund(return_doc)

	def test_validate_refund_currency_mismatch(self):
		return_doc = DummyReturnDoc(currency="EUR")
		original_doc = DummyOriginalDoc(sumup_currency="USD", currency="USD")

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				return_value=original_doc,
			),
		):
			with self.assertRaises(frappe.ValidationError):
				pos_invoice.validate_sumup_return_refund(return_doc)

	def test_validate_refund_passes(self):
		return_doc = DummyReturnDoc(grand_total=-40, rounded_total=-40)
		original_doc = DummyOriginalDoc(sumup_amount=100, sumup_refund_amount=20)

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				return_value=original_doc,
			),
		):
			pos_invoice.validate_sumup_return_refund(return_doc)

	def test_execute_refund_success(self):
		return_doc = DummyReturnDoc(
			sumup_refund_status="PENDING",
			sumup_refund_amount=10,
			grand_total=-10,
			rounded_total=-10,
		)
		original_doc = DummyOriginalDoc(sumup_amount=100, sumup_refund_amount=20)
		client = DummyClient()
		set_calls = []

		def fake_get_doc(doctype, name):
			if name == return_doc.name:
				return return_doc
			if name == original_doc.name:
				return original_doc
			raise frappe.DoesNotExistError

		def fake_set_value(doctype, name, values, *args, **kwargs):
			set_calls.append((doctype, name, values, args, kwargs))

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				side_effect=fake_get_doc,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.set_value",
				side_effect=fake_set_value,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_client",
				return_value=client,
			),
		):
			context = pos_invoice._get_sumup_refund_context(return_doc, strict_missing_transaction=True)
			pos_invoice._attempt_sumup_return_refund(return_doc, context, raise_on_error=False)

		self.assertEqual(len(client.transactions.calls), 1)
		self.assertTrue(
			any(
				call[2].get("sumup_refund_status") == "SUCCESSFUL"
				for call in set_calls
				if call[1] == return_doc.name and isinstance(call[2], dict)
			)
		)

	def test_execute_refund_failure_sets_failed(self):
		return_doc = DummyReturnDoc(
			sumup_refund_status="PENDING",
			sumup_refund_amount=10,
			grand_total=-10,
			rounded_total=-10,
		)
		original_doc = DummyOriginalDoc(sumup_amount=100, sumup_refund_amount=0)

		class FailingTransactions:
			def refund(self, transaction_id, payload):
				raise Exception("fail")

		client = SimpleNamespace(transactions=FailingTransactions())
		set_calls = []

		def fake_get_doc(doctype, name):
			if name == return_doc.name:
				return return_doc
			if name == original_doc.name:
				return original_doc
			raise frappe.DoesNotExistError

		def fake_set_value(doctype, name, values, *args, **kwargs):
			set_calls.append((doctype, name, values, args, kwargs))

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				side_effect=fake_get_doc,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.set_value",
				side_effect=fake_set_value,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_client",
				return_value=client,
			),
		):
			context = pos_invoice._get_sumup_refund_context(return_doc, strict_missing_transaction=True)
			pos_invoice._attempt_sumup_return_refund(return_doc, context, raise_on_error=False)

		self.assertTrue(
			any(
				call[2].get("sumup_refund_status") == "FAILED"
				for call in set_calls
				if call[1] == return_doc.name and isinstance(call[2], dict)
			)
		)

	def test_retry_requires_failed_status(self):
		return_doc = DummyReturnDoc(sumup_refund_status="SUCCESSFUL")
		original_doc = DummyOriginalDoc()

		def fake_get_doc(doctype, name):
			if name == return_doc.name:
				return return_doc
			return original_doc

		with (
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				side_effect=fake_get_doc,
			),
			self._patch_settings(),
		):
			with self.assertRaises(frappe.ValidationError):
				pos_invoice.retry_sumup_return_refund(return_doc.name)

	def test_retry_sets_pending_and_calls_execute(self):
		return_doc = DummyReturnDoc(sumup_refund_status="FAILED")
		original_doc = DummyOriginalDoc()
		set_calls = []
		attempt_calls = []

		def fake_get_doc(doctype, name):
			if name == return_doc.name:
				return return_doc
			return original_doc

		def fake_set_value(doctype, name, values, *args, **kwargs):
			set_calls.append((doctype, name, values))

		def fake_attempt(doc, context, raise_on_error):
			attempt_calls.append((doc.name, context, raise_on_error))
			return True

		with (
			self._patch_defaults(),
			self._patch_settings(),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_doc",
				side_effect=fake_get_doc,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.set_value",
				side_effect=fake_set_value,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice._attempt_sumup_return_refund",
				side_effect=fake_attempt,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.get_value",
				return_value="PENDING",
			),
		):
			result = pos_invoice.retry_sumup_return_refund(return_doc.name)

		self.assertEqual([call[0] for call in attempt_calls], [return_doc.name])
		self.assertTrue(
			any(
				call[1] == return_doc.name
				and isinstance(call[2], dict)
				and call[2].get("sumup_refund_status") == "PENDING"
				for call in set_calls
			)
		)
		self.assertEqual(result.get("status"), "PENDING")
