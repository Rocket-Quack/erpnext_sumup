# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.pos.pos_invoice import (
	_get_sumup_payment_modes,
	_invoice_uses_sumup_payment,
)


class DummyPaymentMethod:
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


class TestPosInvoiceSumUpCurrency(FrappeTestCase):
	def test_get_sumup_payment_modes(self):
		profile = DummyPosProfile(
			[
				DummyPaymentMethod("Cash", 0),
				DummyPaymentMethod("Card", 1),
				DummyPaymentMethod("Voucher", 1),
			]
		)
		self.assertEqual(_get_sumup_payment_modes(profile), {"Card", "Voucher"})

	def test_invoice_uses_sumup_payment(self):
		sumup_modes = {"Card"}
		self.assertTrue(
			_invoice_uses_sumup_payment(
				[DummyInvoicePayment("Card", 10), DummyInvoicePayment("Cash", 5)],
				sumup_modes,
			)
		)
		self.assertFalse(
			_invoice_uses_sumup_payment(
				[DummyInvoicePayment("Card", 0), DummyInvoicePayment("Cash", 5)],
				sumup_modes,
			)
		)
		self.assertFalse(
			_invoice_uses_sumup_payment(
				[DummyInvoicePayment("Cash", 5)],
				sumup_modes,
			)
		)
