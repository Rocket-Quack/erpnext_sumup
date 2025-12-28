import frappe
from frappe import _
from sumup import Sumup

class SumUpNotEnabledError(frappe.ValidationError):
	"""Raised when SumUp is disabled but a client is required."""
	pass

def get_sumup_settings():
	return frappe.get_single("SumUp Settings")

def get_sumup_client(*, require_enabled: bool = True) -> Sumup:
	settings = get_sumup_settings()

	if require_enabled and not settings.enabled:
		raise SumUpNotEnabledError(_("SumUp is disabled in settings."))

	api_key = settings.get_password("api_key")
	if not api_key:
		frappe.throw(_("SumUp API key is missing in SumUp Settings."))

	return Sumup(api_key=api_key)
