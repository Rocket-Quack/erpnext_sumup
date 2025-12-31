# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	extract_merchant_code,
	extract_merchant_currency,
	normalize_api_key,
)
from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	fetch_merchant_profile as fetch_sumup_merchant_profile,
)


class SumUpSettings(Document):
	def validate(self):
		self._set_merchant_code_on_enable()
		self._validate_affiliate_settings()

	def _validate_affiliate_settings(self):
		if not self.enabled:
			return

		affiliate_key = normalize_api_key(self.get_password("affiliate_key"))
		if not affiliate_key:
			frappe.throw(_("Affiliate Key is missing in SumUp Settings."))

		affiliate_app_id = (self.affiliate_app_id or "").strip()
		if not affiliate_app_id:
			frappe.throw(_("Affiliate App ID is missing in SumUp Settings."))

	def _set_merchant_code_on_enable(self):
		if not self.enabled:
			return

		previous = self.get_doc_before_save()
		if previous and previous.enabled:
			return

		if (self.merchant_code or "").strip():
			return

		profile = fetch_sumup_merchant_profile(api_key=self.get_password("api_key"))
		merchant_code = extract_merchant_code(profile)
		if not merchant_code:
			frappe.throw(_("Merchant code not found in SumUp response."))

		self.merchant_code = merchant_code
		merchant_currency = extract_merchant_currency(profile)
		if merchant_currency:
			self.merchant_currency = merchant_currency

	@frappe.whitelist()
	def fetch_merchant_code(self, api_key=None, force=0):
		api_key = normalize_api_key(api_key) or self.get_password("api_key")
		existing_code = (self.merchant_code or "").strip()
		if existing_code and not cint(force):
			return {
				"merchant_code": existing_code,
				"merchant_currency": self.merchant_currency,
				"message": _("Merchant code already set. Clear it to fetch again."),
			}

		profile = fetch_sumup_merchant_profile(api_key=api_key)
		merchant_code = extract_merchant_code(profile)
		if not merchant_code:
			frappe.throw(_("Merchant code not found in SumUp response."))

		self.db_set("merchant_code", merchant_code)
		merchant_currency = extract_merchant_currency(profile)
		if merchant_currency:
			self.db_set("merchant_currency", merchant_currency)

		return {
			"merchant_code": merchant_code,
			"merchant_currency": merchant_currency,
			"message": _("Merchant code updated."),
		}

	@frappe.whitelist()
	def test_connection(self, api_key=None):
		api_key = normalize_api_key(api_key) or self.get_password("api_key")
		if not api_key:
			frappe.throw(_("SumUp API key is missing in SumUp Settings."))

		profile = fetch_sumup_merchant_profile(api_key=api_key)
		merchant_code = extract_merchant_code(profile)
		merchant_currency = extract_merchant_currency(profile)

		if merchant_currency:
			self.db_set("merchant_currency", merchant_currency)

		message = _("Connection successful.")
		if merchant_code:
			message = _("Connection successful. Merchant code: {0}").format(merchant_code)

		return {
			"merchant_code": merchant_code,
			"merchant_currency": merchant_currency,
			"message": message,
		}
