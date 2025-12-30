# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _pos_profile_has_sumup_payment(doc, mode_of_payment: str | None = None) -> bool:
	for row in doc.payments or []:
		if not getattr(row, "use_sumup_terminal", 0):
			continue
		if not mode_of_payment or row.mode_of_payment == mode_of_payment:
			return True
	return False


def _ensure_terminal_enabled(terminal_name: str):
	if not terminal_name:
		return None

	terminal = frappe.db.get_value("SumUp Terminal", terminal_name, ["name", "enabled"], as_dict=True)
	if not terminal:
		frappe.throw(_("SumUp Terminal {0} does not exist.").format(terminal_name))
	if not terminal.enabled:
		frappe.throw(_("SumUp Terminal {0} is disabled.").format(terminal_name))
	return terminal


def validate_pos_profile_sumup_terminal(doc, method=None):
	if not _pos_profile_has_sumup_payment(doc):
		return

	terminal_name = (getattr(doc, "sumup_terminal", "") or "").strip()
	if not terminal_name:
		frappe.throw(_("SumUp Terminal is required when a payment method uses SumUp."))

	_ensure_terminal_enabled(terminal_name)


@frappe.whitelist()
def get_sumup_terminal_for_pos_profile(pos_profile: str, mode_of_payment: str | None = None):
	if not pos_profile:
		return {"terminal": None}

	doc = frappe.get_cached_doc("POS Profile", pos_profile)
	if not _pos_profile_has_sumup_payment(doc, mode_of_payment=mode_of_payment):
		return {"terminal": None}

	terminal_name = (getattr(doc, "sumup_terminal", "") or "").strip()
	if not terminal_name:
		frappe.throw(_("SumUp Terminal is required when a payment method uses SumUp."))

	_ensure_terminal_enabled(terminal_name)
	return {"terminal": terminal_name}
