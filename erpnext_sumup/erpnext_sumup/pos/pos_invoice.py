# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import get_sumup_settings


def _get_sumup_payment_modes(pos_profile_doc):
	return {
		row.mode_of_payment for row in pos_profile_doc.payments or [] if getattr(row, "use_sumup_terminal", 0)
	}


def _invoice_uses_sumup_payment(payments, sumup_modes):
	if not sumup_modes:
		return False

	for row in payments or []:
		if row.mode_of_payment in sumup_modes and flt(getattr(row, "amount", 0)) > 0:
			return True

	return False


def validate_pos_invoice_sumup_currency(doc, method=None):
	if not doc or not getattr(doc, "pos_profile", None):
		return

	if not getattr(doc, "payments", None):
		return

	pos_profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	sumup_modes = _get_sumup_payment_modes(pos_profile)
	if not _invoice_uses_sumup_payment(doc.payments, sumup_modes):
		return

	settings = get_sumup_settings()
	merchant_currency = (getattr(settings, "merchant_currency", "") or "").strip()
	if not merchant_currency:
		frappe.throw(_("SumUp merchant currency is missing. Please run Test Connection in SumUp Settings."))

	invoice_currency = (getattr(doc, "currency", "") or "").strip()
	if invoice_currency != merchant_currency:
		frappe.throw(
			_("POS currency {0} does not match SumUp merchant currency {1}.").format(
				invoice_currency,
				merchant_currency,
			)
		)
