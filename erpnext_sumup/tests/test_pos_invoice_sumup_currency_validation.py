# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.pos.pos_invoice import validate_pos_invoice_sumup_currency


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
	def __init__(self, *, pos_profile="POS-TEST", payments=None, currency="EUR"):
		self.pos_profile = pos_profile
		self.payments = payments or []
		self.currency = currency


class TestPosInvoiceSumUpCurrencyValidation(FrappeTestCase):
	def _run_validation(self, doc, pos_profile, merchant_currency):
		settings = SimpleNamespace(merchant_currency=merchant_currency)
		with (
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.frappe.get_cached_doc",
				return_value=pos_profile,
			),
			patch(
				"erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_settings",
				return_value=settings,
			),
		):
			validate_pos_invoice_sumup_currency(doc)

	def test_currency_mismatch_raises(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(payments=[DummyInvoicePayment("Card", 100)], currency="EUR")

		with self.assertRaises(frappe.ValidationError):
			self._run_validation(doc, pos_profile, merchant_currency="USD")

	def test_currency_match_passes(self):
		pos_profile = DummyPosProfile([DummyPosPaymentMethod("Card", 1)])
		doc = DummyInvoice(payments=[DummyInvoicePayment("Card", 100)], currency="EUR")

		self._run_validation(doc, pos_profile, merchant_currency="EUR")
