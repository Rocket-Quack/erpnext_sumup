import frappe
from frappe import _
from sumup import Sumup


class SumUpNotEnabledError(frappe.ValidationError):
	"""Raised when SumUp is disabled but a client is required."""

	pass


def get_sumup_settings():
	return frappe.get_single("SumUp Settings")


def normalize_api_key(api_key):
	if not api_key:
		return None

	stripped = api_key.strip()
	if not stripped or set(stripped) == {"*"}:
		return None

	return api_key


def get_sumup_client(*, require_enabled: bool = True) -> Sumup:
	settings = get_sumup_settings()

	if require_enabled and not settings.enabled:
		raise SumUpNotEnabledError(_("SumUp is disabled in settings."))

	api_key = settings.get_password("api_key")
	if not api_key:
		frappe.throw(_("SumUp API key is missing in SumUp Settings."))

	return Sumup(api_key=api_key)


def fetch_merchant_profile(*, api_key=None):
	api_key = normalize_api_key(api_key)
	if not api_key:
		api_key = get_sumup_settings().get_password("api_key")

	if not api_key:
		frappe.throw(_("SumUp API key is missing in SumUp Settings."))

	client = Sumup(api_key=api_key)

	merchant_resource = getattr(client, "merchant", None)
	if merchant_resource is not None:
		method = getattr(merchant_resource, "get", None)
		if callable(method):
			try:
				return method()
			except Exception as exc:
				frappe.throw(_("SumUp API error: {0}").format(exc))

		method = getattr(merchant_resource, "get_merchant_profile", None)
		if callable(method):
			try:
				return method()
			except Exception as exc:
				frappe.throw(_("SumUp API error: {0}").format(exc))

	for method_name in ("get_merchant_profile", "get_profile"):
		method = getattr(client, method_name, None)
		if not callable(method):
			continue
		try:
			return method()
		except TypeError:
			continue
		except Exception as exc:
			frappe.throw(_("SumUp API error: {0}").format(exc))

	frappe.throw(_("SumUp client does not expose a merchant profile endpoint."))


def extract_merchant_code(profile):
	if profile is None:
		return None

	merchant_code = getattr(profile, "merchant_code", None)
	if merchant_code:
		return merchant_code

	merchant_profile = getattr(profile, "merchant_profile", None)
	if merchant_profile:
		if isinstance(merchant_profile, dict):
			merchant_code = merchant_profile.get("merchant_code")
			if merchant_code:
				return merchant_code
		else:
			merchant_code = getattr(merchant_profile, "merchant_code", None)
			if merchant_code:
				return merchant_code

	if hasattr(profile, "model_dump"):
		return extract_merchant_code(profile.model_dump())

	if not isinstance(profile, dict):
		return None

	merchant_code = profile.get("merchant_code")
	if merchant_code:
		return merchant_code

	merchant_profile = profile.get("merchant_profile")
	if isinstance(merchant_profile, dict):
		return merchant_profile.get("merchant_code")

	return None


def fetch_merchant_code(*, api_key=None):
	profile = fetch_merchant_profile(api_key=api_key)
	merchant_code = extract_merchant_code(profile)
	if not merchant_code:
		frappe.throw(_("Merchant code not found in SumUp response."))

	return merchant_code
