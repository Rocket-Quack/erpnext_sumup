# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import get_sumup_client, get_sumup_settings
from erpnext_sumup.erpnext_sumup.pos.pos_profile import _ensure_terminal_enabled

SUMUP_FINAL_STATUSES = {"SUCCESSFUL", "FAILED", "CANCELLED"}
sumup_payment_logger = frappe.logger("sumup_payment", allow_site=True)
sumup_refund_logger = frappe.logger("sumup_refund", allow_site=True)


def _safe_debug_payload(value):
	if value is None:
		return None
	if isinstance(value, dict | list):
		return value
	return str(value)


def _extract_sumup_error_details(exc):
	details = {"message": str(exc)}
	status = getattr(exc, "status", None)
	if status is not None:
		details["status"] = status
	body = getattr(exc, "body", None)
	if body is not None:
		details["body"] = _safe_debug_payload(body)
	response = getattr(exc, "response", None)
	if response is not None:
		status_code = getattr(response, "status_code", None)
		if status_code is not None:
			details["response_status"] = status_code
		text = getattr(response, "text", None)
		if text:
			details["response_text"] = text
	return details


def _publish_sumup_refund_debug(doc, step, details=None):
	settings = get_sumup_settings()
	if not getattr(settings, "enable_debug_logging", 0):
		return
	payload = {"docname": doc.name, "step": step, "details": details or {}}
	try:
		user = getattr(frappe.session, "user", None) or doc.owner
		frappe.publish_realtime("sumup_refund_debug", payload, user=user)
	except Exception:
		pass


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


def _get_invoice_total(doc) -> float:
	disable_rounded = cint(frappe.db.get_default("disable_rounded_total") or 0)
	total = doc.grand_total if disable_rounded else (doc.rounded_total or doc.grand_total)
	return flt(total)


def _get_return_against(doc) -> str:
	return (getattr(doc, "return_against", "") or "").strip()


def _get_refund_amount(doc) -> float:
	return abs(_get_invoice_total(doc))


def _get_sumup_payment_breakdown(doc, sumup_modes):
	sumup_rows = []
	sumup_amount = 0
	other_amount = 0
	for row in doc.payments or []:
		amount = flt(getattr(row, "amount", 0))
		if amount <= 0:
			continue
		if row.mode_of_payment in sumup_modes:
			sumup_rows.append(row)
			sumup_amount += amount
		else:
			other_amount += amount
	return sumup_rows, sumup_amount, other_amount


def _get_minor_unit(currency: str) -> int:
	fraction_units = frappe.db.get_value("Currency", currency, "fraction_units", cache=True)
	if fraction_units:
		try:
			fraction_units = int(fraction_units)
			if fraction_units <= 0:
				return 0
			return max(0, len(str(abs(fraction_units))) - 1)
		except Exception:
			pass

	smallest = frappe.db.get_value(
		"Currency",
		currency,
		"smallest_currency_fraction_value",
		cache=True,
	)
	if smallest:
		try:
			decimal = Decimal(str(smallest)).normalize()
			return max(0, -decimal.as_tuple().exponent)
		except Exception:
			pass

	return 2


def _to_minor_value(amount: float, minor_unit: int) -> int:
	scale = Decimal(10) ** minor_unit
	value = (Decimal(str(amount)) * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
	return int(value)


def _get_sumup_terminal_from_profile(pos_profile_doc):
	terminal_name = (getattr(pos_profile_doc, "sumup_terminal", "") or "").strip()
	_ensure_terminal_enabled(terminal_name)
	terminal = frappe.db.get_value(
		"SumUp Terminal",
		terminal_name,
		["name", "terminal_id"],
		as_dict=True,
	)
	if not terminal or not terminal.get("terminal_id"):
		frappe.throw(_("Terminal ID is missing for SumUp Terminal {0}.").format(terminal_name))
	return terminal


def _extract_client_transaction_id(response):
	data = getattr(response, "data", None)
	if data:
		value = getattr(data, "client_transaction_id", None)
		if value:
			return value
		if isinstance(data, dict):
			return data.get("client_transaction_id")

	if isinstance(response, dict):
		data = response.get("data") or {}
		if isinstance(data, dict):
			return data.get("client_transaction_id")

	return None


def _extract_transaction_status(transaction):
	if transaction is None:
		return None

	status = getattr(transaction, "status", None) or getattr(transaction, "simple_status", None)
	if status:
		return str(status).upper()

	if isinstance(transaction, dict):
		value = transaction.get("status") or transaction.get("simple_status")
		if value:
			return str(value).upper()
		for key in ("data", "transaction"):
			nested = transaction.get(key)
			value = _extract_transaction_status(nested)
			if value:
				return value
		items = transaction.get("items")
		if isinstance(items, list) and items:
			value = _extract_transaction_status(items[0])
			if value:
				return value

	return None


def _extract_transaction_amount_currency(transaction):
	amount = getattr(transaction, "amount", None)
	currency = getattr(transaction, "currency", None)
	if isinstance(transaction, dict):
		if amount is None:
			amount = transaction.get("amount")
		if not currency:
			currency = transaction.get("currency")
		if amount is None or not currency:
			for key in ("data", "transaction"):
				nested = transaction.get(key)
				if isinstance(nested, dict):
					if amount is None:
						amount = nested.get("amount", amount)
					if not currency:
						currency = nested.get("currency", currency)
			if (amount is None or not currency) and isinstance(transaction.get("items"), list):
				items = transaction.get("items")
				if items:
					nested_amount, nested_currency = _extract_transaction_amount_currency(items[0])
					if amount is None:
						amount = nested_amount
					if not currency:
						currency = nested_currency
	return amount, currency


def _extract_transaction_refunded_amount(transaction):
	if transaction is None:
		return None

	value = getattr(transaction, "refunded_amount", None)
	if value is not None:
		return value

	if isinstance(transaction, dict):
		if "refunded_amount" in transaction:
			return transaction.get("refunded_amount")
		for key in ("data", "transaction"):
			nested = transaction.get(key)
			value = _extract_transaction_refunded_amount(nested)
			if value is not None:
				return value
		items = transaction.get("items")
		if isinstance(items, list) and items:
			value = _extract_transaction_refunded_amount(items[0])
			if value is not None:
				return value

	return None


def _extract_transaction_id(transaction):
	if transaction is None:
		return None

	value = getattr(transaction, "id", None)
	if value:
		return str(value)

	if isinstance(transaction, dict):
		value = (
			transaction.get("id")
			or transaction.get("transaction_id")
			or transaction.get("transactionId")
			or transaction.get("transaction_code")
			or transaction.get("transactionCode")
		)
		if value:
			return str(value)
		for key in ("data", "transaction"):
			nested = transaction.get(key)
			value = _extract_transaction_id(nested)
			if value:
				return value
		items = transaction.get("items")
		if isinstance(items, list) and items:
			value = _extract_transaction_id(items[0])
			if value:
				return value

	return None


def _set_sumup_refund_state(doc, status, refund_amount, transaction_id):
	values = {
		"sumup_refund_status": status,
		"sumup_refund_amount": refund_amount,
		"sumup_transaction_id": transaction_id,
	}
	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		values,
		update_modified=False,
	)
	doc.sumup_refund_status = status
	doc.sumup_refund_amount = refund_amount
	doc.sumup_transaction_id = transaction_id


def _update_original_refund_amount(original, refund_amount):
	refunded_total = flt(getattr(original, "sumup_refund_amount", 0) or 0)
	frappe.db.set_value(
		"POS Invoice",
		original.name,
		"sumup_refund_amount",
		refunded_total + refund_amount,
		update_modified=False,
	)


def _refresh_original_refund_amount(original):
	try:
		get_sumup_payment_status(original.name)
		return frappe.get_doc("POS Invoice", original.name)
	except Exception:
		return None


def _get_sumup_refund_context(doc, *, strict_missing_transaction=False):
	return_against = _get_return_against(doc)
	if not return_against:
		return None

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	original_has_sumup = bool(
		getattr(original, "sumup_client_transaction_id", None) or getattr(original, "sumup_status", None)
	)
	if not transaction_id:
		if strict_missing_transaction and original_has_sumup:
			frappe.throw(_("SumUp transaction id is missing for the original invoice."))
		return None

	refund_amount = _get_refund_amount(doc)
	if refund_amount <= 0:
		return None

	original_status = (getattr(original, "sumup_status", "") or "").upper()
	if original_status and original_status != "SUCCESSFUL":
		frappe.throw(_("SumUp payment is not completed for the original invoice."))

	original_currency = (getattr(original, "sumup_currency", "") or "").strip() or (
		getattr(original, "currency", "") or ""
	).strip()
	if original_currency and getattr(doc, "currency", None) and doc.currency != original_currency:
		frappe.throw(
			_("SumUp refund currency {0} does not match original currency {1}.").format(
				doc.currency,
				original_currency,
			)
		)

	refunded_total = flt(getattr(original, "sumup_refund_amount", 0) or 0)
	paid_total = flt(getattr(original, "sumup_amount", 0) or 0)
	if paid_total and refunded_total + refund_amount > paid_total + 0.0001:
		frappe.throw(_("SumUp refund amount exceeds the original payment amount."))

	return {
		"original": original,
		"return_against": return_against,
		"transaction_id": transaction_id,
		"refund_amount": refund_amount,
		"refunded_total": refunded_total,
	}


def _attempt_sumup_return_refund(doc, context, *, raise_on_error):
	original = context["original"]
	return_against = context["return_against"]
	transaction_id = context["transaction_id"]
	refund_amount = context["refund_amount"]
	refunded_total = context["refunded_total"]

	client = get_sumup_client(require_enabled=False)
	try:
		from sumup.transactions.resource import RefundTransactionBody
	except Exception:
		RefundTransactionBody = None

	payload = (
		RefundTransactionBody(amount=refund_amount) if RefundTransactionBody else {"amount": refund_amount}
	)
	sumup_refund_logger.info(
		"SumUp refund call (doc=%s original=%s transaction_id=%s amount=%s)",
		doc.name,
		return_against,
		transaction_id,
		refund_amount,
	)
	_publish_sumup_refund_debug(
		doc,
		"call",
		{
			"transaction_id": transaction_id,
			"return_against": return_against,
			"amount": refund_amount,
		},
	)
	try:
		client.transactions.refund(transaction_id, payload)
	except Exception as exc:
		status_code = getattr(exc, "status", None)
		error_details = _extract_sumup_error_details(exc)
		is_conflict = status_code == 409 or str(exc).lower() == "conflict"
		if is_conflict:
			refreshed_original = _refresh_original_refund_amount(original)
			if refreshed_original:
				refreshed_total = flt(getattr(refreshed_original, "sumup_refund_amount", 0) or 0)
				if refreshed_total + 0.0001 >= refunded_total + refund_amount:
					_set_sumup_refund_state(doc, "SUCCESSFUL", refund_amount, transaction_id)
					_publish_sumup_refund_debug(
						doc,
						"success",
						{
							"reason": "conflict_already_refunded",
							"transaction_id": transaction_id,
							"amount": refund_amount,
						},
					)
					return True

		sumup_refund_logger.exception(
			"SumUp refund error (doc=%s original=%s transaction_id=%s)",
			doc.name,
			return_against,
			transaction_id,
		)
		_publish_sumup_refund_debug(
			doc,
			"error",
			{
				"reason": "api_error",
				"transaction_id": transaction_id,
				"error": error_details,
			},
		)
		_set_sumup_refund_state(doc, "FAILED", refund_amount, transaction_id)
		if raise_on_error:
			error_text = error_details.get("body") or error_details.get("message") or str(exc)
			frappe.throw(_("SumUp refund failed: {0}").format(error_text))
		return False

	_update_original_refund_amount(original, refund_amount)
	_set_sumup_refund_state(doc, "SUCCESSFUL", refund_amount, transaction_id)
	sumup_refund_logger.info(
		"SumUp refund success (doc=%s original=%s amount=%s)",
		doc.name,
		return_against,
		refund_amount,
	)
	_publish_sumup_refund_debug(
		doc,
		"success",
		{"transaction_id": transaction_id, "amount": refund_amount},
	)
	return True


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


def validate_pos_invoice_sumup_payment_status(doc, method=None):
	if not doc or not getattr(doc, "pos_profile", None):
		return

	if getattr(doc, "is_return", 0):
		return

	if not getattr(doc, "payments", None):
		return

	pos_profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	sumup_modes = _get_sumup_payment_modes(pos_profile)
	if not _invoice_uses_sumup_payment(doc.payments, sumup_modes):
		return

	sumup_rows, sumup_amount, other_amount = _get_sumup_payment_breakdown(doc, sumup_modes)
	if not sumup_amount:
		return

	if len(sumup_rows) > 1:
		frappe.throw(_("Only one SumUp payment method can be used."))

	total = _get_invoice_total(doc)
	if other_amount > 0 or sumup_amount != total:
		frappe.throw(_("SumUp payment must cover the full invoice amount."))

	status = (getattr(doc, "sumup_status", "") or "").upper()
	if status != "SUCCESSFUL":
		frappe.throw(_("SumUp payment is not completed. Please finish payment before submitting."))

	if not getattr(doc, "sumup_client_transaction_id", None):
		frappe.throw(_("SumUp payment is missing a transaction id."))

	if getattr(doc, "sumup_currency", None) and doc.sumup_currency != doc.currency:
		frappe.throw(
			_("SumUp payment currency {0} does not match invoice currency {1}.").format(
				doc.sumup_currency,
				doc.currency,
			)
		)

	if getattr(doc, "sumup_amount", None) and flt(doc.sumup_amount) != total:
		frappe.throw(
			_("SumUp payment amount {0} does not match invoice total {1}.").format(
				flt(doc.sumup_amount),
				flt(total),
			)
		)


@frappe.whitelist()
def start_sumup_payment(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	if doc.docstatus != 0:
		frappe.throw(_("POS Invoice must be in Draft state."))

	if not getattr(doc, "pos_profile", None):
		frappe.throw(_("POS Profile is required."))

	pos_profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	sumup_modes = _get_sumup_payment_modes(pos_profile)
	if not sumup_modes:
		frappe.throw(_("SumUp payment is not configured for this POS Profile."))

	sumup_rows, sumup_amount, other_amount = _get_sumup_payment_breakdown(doc, sumup_modes)
	if not sumup_amount:
		frappe.throw(_("No SumUp payment selected."))
	if len(sumup_rows) > 1:
		frappe.throw(_("Only one SumUp payment method can be used."))

	total = _get_invoice_total(doc)
	if other_amount > 0 or sumup_amount != total:
		frappe.throw(_("SumUp payment must cover the full invoice amount."))

	current_status = (getattr(doc, "sumup_status", "") or "").upper()
	if current_status == "SUCCESSFUL":
		frappe.throw(_("SumUp payment already completed."))
	if current_status == "PENDING" and getattr(doc, "sumup_client_transaction_id", None):
		return {
			"status": "PENDING",
			"client_transaction_id": doc.sumup_client_transaction_id,
			"message": _("SumUp payment already in progress."),
		}

	settings = get_sumup_settings()
	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	if not settings.enabled:
		if debug_enabled:
			sumup_payment_logger.info("SumUp payment blocked: settings disabled (doc=%s)", doc.name)
		frappe.throw(_("SumUp is disabled in settings."))

	merchant_code = (getattr(settings, "merchant_code", "") or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))

	terminal = _get_sumup_terminal_from_profile(pos_profile)
	reader_id = terminal.get("terminal_id")

	currency = (getattr(doc, "currency", "") or "").strip()
	minor_unit = _get_minor_unit(currency)
	value = _to_minor_value(total, minor_unit)
	debug_details = None
	if debug_enabled:
		debug_details = {
			"merchant_code": merchant_code,
			"reader_id": reader_id,
			"amount": total,
			"currency": currency,
			"minor_unit": minor_unit,
		}

	client = get_sumup_client(require_enabled=False)
	try:
		from sumup.readers.resource import CreateReaderCheckoutBody
	except Exception:
		CreateReaderCheckoutBody = None

	payload_data = {
		"total_amount": {
			"currency": currency,
			"minor_unit": minor_unit,
			"value": value,
		}
	}
	payload = CreateReaderCheckoutBody(**payload_data) if CreateReaderCheckoutBody else payload_data

	if debug_enabled:
		sumup_payment_logger.info(
			"SumUp checkout request (doc=%s merchant_code=%s reader_id=%s amount=%s currency=%s minor_unit=%s)",
			doc.name,
			merchant_code,
			reader_id,
			total,
			currency,
			minor_unit,
		)
	try:
		response = client.readers.create_checkout(merchant_code, reader_id, payload)
	except Exception as exc:
		if debug_enabled:
			sumup_payment_logger.exception(
				"SumUp checkout error (doc=%s merchant_code=%s reader_id=%s)",
				doc.name,
				merchant_code,
				reader_id,
			)
		frappe.throw(_("SumUp API error: {0}").format(exc))

	client_transaction_id = _extract_client_transaction_id(response)
	if not client_transaction_id:
		if debug_enabled:
			sumup_payment_logger.info("SumUp checkout missing client_transaction_id (doc=%s)", doc.name)
		frappe.throw(_("Client transaction id not found in SumUp response."))

	if debug_enabled:
		sumup_payment_logger.info(
			"SumUp checkout response (doc=%s client_transaction_id=%s)",
			doc.name,
			client_transaction_id,
		)
		debug_details["client_transaction_id"] = client_transaction_id
	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		{
			"sumup_status": "PENDING",
			"sumup_client_transaction_id": client_transaction_id,
			"sumup_amount": total,
			"sumup_currency": currency,
		},
		update_modified=False,
	)

	result = {
		"status": "PENDING",
		"client_transaction_id": client_transaction_id,
		"message": _("SumUp payment started."),
	}
	if debug_enabled and debug_details:
		result["debug_details"] = debug_details
	return result


@frappe.whitelist()
def get_sumup_payment_status(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	transaction_id = getattr(doc, "sumup_client_transaction_id", None)
	if not transaction_id:
		frappe.throw(_("SumUp payment is missing a transaction id."))
	client_transaction_id = transaction_id

	settings = get_sumup_settings()
	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	if not settings.enabled:
		if debug_enabled:
			sumup_payment_logger.info("SumUp status blocked: settings disabled (doc=%s)", doc.name)
		frappe.throw(_("SumUp is disabled in settings."))

	merchant_code = (getattr(settings, "merchant_code", "") or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))
	debug_details = None
	if debug_enabled:
		debug_details = {
			"merchant_code": merchant_code,
			"client_transaction_id": client_transaction_id,
		}

	client = get_sumup_client(require_enabled=False)
	try:
		from sumup.transactions.resource import GetTransactionV21Params
	except Exception:
		GetTransactionV21Params = None

	if not GetTransactionV21Params:
		frappe.throw(_("SumUp SDK does not support transaction lookup. Please update the sumup package."))

	params = GetTransactionV21Params(client_transaction_id=transaction_id)
	params_dict = {"client_transaction_id": transaction_id}
	if hasattr(params, "model_dump"):
		params_dict = params.model_dump(by_alias=True, exclude_none=True)
	elif hasattr(params, "dict"):
		params_dict = params.dict(by_alias=True, exclude_none=True)
	if debug_enabled:
		sumup_payment_logger.info(
			"SumUp status request (doc=%s merchant_code=%s client_transaction_id=%s)",
			doc.name,
			merchant_code,
			client_transaction_id,
		)
	try:
		transaction = client.transactions.get(merchant_code, params=params)
	except Exception as exc:
		status_code = getattr(exc, "status", None)
		if status_code == 404:
			if debug_enabled and debug_details is not None:
				debug_details["status_code"] = 404
			if debug_enabled:
				sumup_payment_logger.info(
					"SumUp status 404 -> pending (doc=%s client_transaction_id=%s)",
					doc.name,
					client_transaction_id,
				)
			result = {
				"status": "PENDING",
				"amount": None,
				"currency": None,
			}
			if debug_enabled and debug_details:
				result["debug_details"] = debug_details
			return result
		is_validation_error = False
		try:
			import pydantic
		except Exception:
			pydantic = None

		if pydantic and isinstance(exc, pydantic.ValidationError):
			is_validation_error = True
		elif exc.__class__.__name__ == "ValidationError":
			is_validation_error = True

		if not is_validation_error:
			if debug_enabled:
				sumup_payment_logger.exception(
					"SumUp status error (doc=%s client_transaction_id=%s)",
					doc.name,
					client_transaction_id,
				)
			frappe.throw(_("SumUp API error: {0}").format(exc))

		http_client = getattr(client, "_client", None)
		if http_client is None:
			frappe.throw(_("SumUp API error: client transport not available."))

		try:
			response = http_client.get(
				f"/v2.1/merchants/{merchant_code}/transactions",
				params=params_dict,
			)
		except Exception as raw_exc:
			if debug_enabled:
				sumup_payment_logger.exception(
					"SumUp status fallback error (doc=%s client_transaction_id=%s)",
					doc.name,
					client_transaction_id,
				)
			frappe.throw(_("SumUp API error: {0}").format(raw_exc))

		if response.status_code == 404:
			if debug_enabled and debug_details is not None:
				debug_details["status_code"] = 404
			if debug_enabled:
				sumup_payment_logger.info(
					"SumUp status fallback 404 -> pending (doc=%s client_transaction_id=%s)",
					doc.name,
					client_transaction_id,
				)
			result = {
				"status": "PENDING",
				"amount": None,
				"currency": None,
			}
			if debug_enabled and debug_details:
				result["debug_details"] = debug_details
			return result
		if response.status_code != 200:
			detail = f" {response.text}" if response.text else ""
			frappe.throw(_("SumUp API error: {0}{1}").format(response.status_code, detail))

		try:
			transaction = response.json()
		except Exception as raw_exc:
			if debug_enabled:
				sumup_payment_logger.exception(
					"SumUp status parse error (doc=%s client_transaction_id=%s)",
					doc.name,
					client_transaction_id,
				)
			frappe.throw(_("SumUp API error: {0}").format(raw_exc))

	status = _extract_transaction_status(transaction) or "UNKNOWN"
	amount, currency = _extract_transaction_amount_currency(transaction)
	transaction_id = _extract_transaction_id(transaction)
	refunded_amount = _extract_transaction_refunded_amount(transaction)

	update_values = {}
	if amount is not None:
		update_values["sumup_amount"] = amount
	if currency:
		update_values["sumup_currency"] = currency
	if transaction_id:
		update_values["sumup_transaction_id"] = transaction_id
	if refunded_amount is not None:
		update_values["sumup_refund_amount"] = refunded_amount
	if status in SUMUP_FINAL_STATUSES:
		update_values["sumup_status"] = status

	if update_values:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			update_values,
			update_modified=False,
		)
	if debug_enabled:
		sumup_payment_logger.info(
			"SumUp status response (doc=%s client_transaction_id=%s status=%s amount=%s currency=%s transaction_id=%s)",
			doc.name,
			client_transaction_id,
			status,
			amount,
			currency,
			transaction_id,
		)

	result = {
		"status": status,
		"amount": amount,
		"currency": currency,
		"transaction_id": transaction_id,
		"refunded_amount": refunded_amount,
	}
	if debug_enabled and debug_details:
		debug_details.update(
			{
				"status": status,
				"amount": amount,
				"currency": currency,
				"transaction_id": transaction_id,
				"refunded_amount": refunded_amount,
			}
		)
		result["debug_details"] = debug_details
	return result


@frappe.whitelist()
def get_sumup_return_refund_preview(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	if not getattr(doc, "is_return", 0):
		return {"needs_refund": False}

	settings = get_sumup_settings()
	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	if not settings.enabled:
		if debug_enabled:
			return {"needs_refund": False, "debug_details": {"reason": "settings_disabled"}}
		return {"needs_refund": False}

	return_against = _get_return_against(doc)
	if not return_against:
		if debug_enabled:
			return {"needs_refund": False, "debug_details": {"reason": "return_against_missing"}}
		return {"needs_refund": False}

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	if not transaction_id:
		if debug_enabled:
			return {
				"needs_refund": False,
				"debug_details": {
					"reason": "transaction_id_missing",
					"return_against": return_against,
				},
			}
		return {"needs_refund": False}

	refund_amount = _get_refund_amount(doc)
	if refund_amount <= 0:
		if debug_enabled:
			return {
				"needs_refund": False,
				"debug_details": {
					"reason": "refund_amount_zero",
					"return_against": return_against,
					"transaction_id": transaction_id,
					"amount": refund_amount,
				},
			}
		return {"needs_refund": False}

	currency = (getattr(doc, "currency", "") or "").strip()
	result = {
		"needs_refund": True,
		"amount": refund_amount,
		"currency": currency,
	}
	if debug_enabled:
		result["debug_details"] = {
			"reason": "ok",
			"return_against": return_against,
			"transaction_id": transaction_id,
			"amount": refund_amount,
			"currency": currency,
		}
	return result


def validate_sumup_return_refund(doc, method=None):
	if not doc or not getattr(doc, "is_return", 0):
		return

	settings = get_sumup_settings()
	if not settings.enabled:
		return

	_get_sumup_refund_context(doc)
	return


def process_sumup_return_refund_before_submit(doc, method=None):
	if not doc or not getattr(doc, "is_return", 0):
		return

	if (getattr(doc, "sumup_refund_status", "") or "").upper() == "SUCCESSFUL":
		return

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	context = _get_sumup_refund_context(doc, strict_missing_transaction=True)
	if not context:
		return

	_attempt_sumup_return_refund(doc, context, raise_on_error=True)


@frappe.whitelist()
def retry_sumup_return_refund(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	if not doc or not getattr(doc, "is_return", 0):
		frappe.throw(_("Refund retries are only available for return invoices."))

	if doc.docstatus != 1:
		frappe.throw(_("Refund retries are only available for submitted returns."))

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	status = (getattr(doc, "sumup_refund_status", "") or "").upper()
	if status != "FAILED":
		frappe.throw(_("Refund can only be retried when status is FAILED."))

	context = _get_sumup_refund_context(doc, strict_missing_transaction=True)
	if not context:
		frappe.throw(_("SumUp refund cannot be processed for this return."))

	_set_sumup_refund_state(
		doc,
		"PENDING",
		context["refund_amount"],
		context["transaction_id"],
	)
	_attempt_sumup_return_refund(doc, context, raise_on_error=False)

	final_status = frappe.db.get_value("POS Invoice", doc.name, "sumup_refund_status")
	message = _("SumUp refund retry completed with status: {0}.").format(final_status or "UNKNOWN")
	return {"status": final_status, "message": message}


@frappe.whitelist()
def cancel_sumup_payment(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	if not getattr(doc, "pos_profile", None):
		frappe.throw(_("POS Profile is required."))

	pos_profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	terminal = _get_sumup_terminal_from_profile(pos_profile)
	reader_id = terminal.get("terminal_id")

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	merchant_code = (getattr(settings, "merchant_code", "") or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))

	client = get_sumup_client(require_enabled=False)
	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	debug_error = None
	try:
		client.readers.terminate_checkout(merchant_code, reader_id)
	except Exception as exc:
		debug_error = str(exc)

	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		{
			"sumup_status": "CANCELLED",
			"sumup_client_transaction_id": None,
			"sumup_amount": 0,
			"sumup_currency": None,
		},
		update_modified=False,
	)

	result = {
		"status": "CANCELLED",
		"message": _("SumUp payment cancelled."),
	}
	if debug_error and debug_enabled:
		result["error"] = debug_error
	return result
