# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	fetch_merchant_code as fetch_sumup_merchant_code,
)
from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	normalize_api_key,
)


class SumUpSettings(Document):
	def validate(self):
		self._set_merchant_code_on_enable()

	def _set_merchant_code_on_enable(self):
		if not self.enabled:
			return

		previous = self.get_doc_before_save()
		if previous and previous.enabled:
			return

		if (self.merchant_code or "").strip():
			return

		self.merchant_code = fetch_sumup_merchant_code(api_key=self.get_password("api_key"))

	@frappe.whitelist()
	def fetch_merchant_code(self, api_key=None):
		api_key = normalize_api_key(api_key) or self.get_password("api_key")
		merchant_code = fetch_sumup_merchant_code(api_key=api_key)
		self.db_set("merchant_code", merchant_code)
		return {
			"merchant_code": merchant_code,
			"message": _("Merchant code updated."),
		}
