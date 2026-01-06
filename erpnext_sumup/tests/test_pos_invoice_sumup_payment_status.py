# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.pos.pos_invoice import validate_pos_invoice_sumup_payment_status


class DummyPosPaymentMethod:
	def __init__(self, mode_of_payment, use_sumup_terminal):
		self.mode_of_payment = mode_of_payment
		self.use_sumup_terminal = use_sumup_terminal


class DummyPosProfile:
	def __init__(self, payments):
		self.payments = payments


class DummyInvoicePayment:
	def __init__(self, mode_of_payment, amount):
		self.mode_of_payment = mode_of_payment
		self.amount = amount


class DummyInvoice:
	def __init__(
		self,
		*,
		pos_profile="POS-TEST",
		payments=None,
		currency="EUR",
		sumup_status="PENDING",
		sumup_client_transaction_id=None,
		sumup_amount=None,
		sumup_currency=None,
		grand_total=100,
		rounded_total=100,
	):
		self.pos_profile = pos_profile
		self.payments = payments or []
		self.currency = currency
		self.sumup_status = sumup_status
		self.sumup_client_transaction_id = sumup_client_transaction_id
		self.sumup_amount = sumup_amount
		self.sumup_currency = sumup_currency
		self.grand_total = grand_total
		self.rounded_total = rounded_total


class TestPosInvoiceSumUpPaymentStatus(FrappeTestCase):
	def _run_validation(self, doc, pos_profile):
		with (
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_cached_doc",
				return_value=pos_profile,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.db.get_default",
				return_value=0,
			),
		):
			validate_pos_invoice_sumup_payment_status(doc)

	def test_requires_successful_status(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(
			payments=[DummyInvoicePayment("Card", 100)],
			sumup_status="PENDING",
			sumup_client_transaction_id="TX-1",
			sumup_amount=100,
			sumup_currency="EUR",
		)

		with self.assertRaises(frappe.ValidationError):
			self._run_validation(doc, pos_profile)

	def test_requires_transaction_id(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(
			payments=[DummyInvoicePayment("Card", 100)],
			sumup_status="SUCCESSFUL",
			sumup_client_transaction_id=None,
			sumup_amount=100,
			sumup_currency="EUR",
		)

		with self.assertRaises(frappe.ValidationError):
			self._run_validation(doc, pos_profile)

	def test_amount_and_currency_must_match(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(
			payments=[DummyInvoicePayment("Card", 100)],
			sumup_status="SUCCESSFUL",
			sumup_client_transaction_id="TX-2",
			sumup_amount=90,
			sumup_currency="USD",
			currency="EUR",
		)

		with self.assertRaises(frappe.ValidationError):
			self._run_validation(doc, pos_profile)

	def test_successful_payment_passes(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(
			payments=[DummyInvoicePayment("Card", 100)],
			sumup_status="SUCCESSFUL",
			sumup_client_transaction_id="TX-3",
			sumup_amount=100,
			sumup_currency="EUR",
			currency="EUR",
		)

		self._run_validation(doc, pos_profile)
