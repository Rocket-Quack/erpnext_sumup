# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import get_sumup_client, get_sumup_settings
from erpnext_sumup.erpnext_sumup.pos.pos_profile import _ensure_terminal_enabled

SUMUP_FINAL_STATUSES = {"SUCCESSFUL", "FAILED", "CANCELLED"}


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

	return None


def _extract_transaction_amount_currency(transaction):
	amount = getattr(transaction, "amount", None)
	currency = getattr(transaction, "currency", None)
	if isinstance(transaction, dict):
		if amount is None:
			amount = transaction.get("amount")
		if not currency:
			currency = transaction.get("currency")
	return amount, currency


def _extract_transaction_id(transaction):
	if transaction is None:
		return None

	value = getattr(transaction, "id", None)
	if value:
		return str(value)

	if isinstance(transaction, dict):
		value = transaction.get("id") or transaction.get("transaction_id") or transaction.get("transactionId")
		if value:
			return str(value)

	return None


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
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	merchant_code = (getattr(settings, "merchant_code", "") or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))

	terminal = _get_sumup_terminal_from_profile(pos_profile)
	reader_id = terminal.get("terminal_id")

	currency = (getattr(doc, "currency", "") or "").strip()
	minor_unit = _get_minor_unit(currency)
	value = _to_minor_value(total, minor_unit)

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

	try:
		response = client.readers.create_checkout(merchant_code, reader_id, payload)
	except Exception as exc:
		frappe.throw(_("SumUp API error: {0}").format(exc))

	client_transaction_id = _extract_client_transaction_id(response)
	if not client_transaction_id:
		frappe.throw(_("Client transaction id not found in SumUp response."))

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

	return {
		"status": "PENDING",
		"client_transaction_id": client_transaction_id,
		"message": _("SumUp payment started."),
	}


@frappe.whitelist()
def get_sumup_payment_status(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	transaction_id = getattr(doc, "sumup_client_transaction_id", None)
	if not transaction_id:
		frappe.throw(_("SumUp payment is missing a transaction id."))

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	merchant_code = (getattr(settings, "merchant_code", "") or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))

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
	try:
		transaction = client.transactions.get(merchant_code, params=params)
	except Exception as exc:
		status_code = getattr(exc, "status", None)
		if status_code == 404:
			return {
				"status": "PENDING",
				"amount": None,
				"currency": None,
			}
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
			frappe.throw(_("SumUp API error: {0}").format(raw_exc))

		if response.status_code == 404:
			return {
				"status": "PENDING",
				"amount": None,
				"currency": None,
			}
		if response.status_code != 200:
			detail = f" {response.text}" if response.text else ""
			frappe.throw(_("SumUp API error: {0}{1}").format(response.status_code, detail))

		try:
			transaction = response.json()
		except Exception as raw_exc:
			frappe.throw(_("SumUp API error: {0}").format(raw_exc))

	status = _extract_transaction_status(transaction) or "UNKNOWN"
	amount, currency = _extract_transaction_amount_currency(transaction)
	transaction_id = _extract_transaction_id(transaction)

	update_values = {}
	if amount is not None:
		update_values["sumup_amount"] = amount
	if currency:
		update_values["sumup_currency"] = currency
	if transaction_id:
		update_values["sumup_transaction_id"] = transaction_id
	if status in SUMUP_FINAL_STATUSES:
		update_values["sumup_status"] = status

	if update_values:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			update_values,
			update_modified=False,
		)

	return {
		"status": status,
		"amount": amount,
		"currency": currency,
	}


@frappe.whitelist()
def get_sumup_return_refund_preview(pos_invoice: str):
	doc = frappe.get_doc("POS Invoice", pos_invoice)
	if not getattr(doc, "is_return", 0):
		return {"needs_refund": False}

	settings = get_sumup_settings()
	if not settings.enabled:
		return {"needs_refund": False}

	return_against = (getattr(doc, "return_against", "") or "").strip()
	if not return_against:
		return {"needs_refund": False}

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	if not transaction_id:
		return {"needs_refund": False}

	refund_amount = abs(_get_invoice_total(doc))
	if refund_amount <= 0:
		return {"needs_refund": False}

	currency = (getattr(doc, "currency", "") or "").strip()
	return {
		"needs_refund": True,
		"amount": refund_amount,
		"currency": currency,
	}


def validate_sumup_return_refund(doc, method=None):
	if not doc or not getattr(doc, "is_return", 0):
		return

	settings = get_sumup_settings()
	if not settings.enabled:
		return

	return_against = (getattr(doc, "return_against", "") or "").strip()
	if not return_against:
		return

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	if not transaction_id:
		return

	original_status = (getattr(original, "sumup_status", "") or "").upper()
	if original_status and original_status != "SUCCESSFUL":
		frappe.throw(_("SumUp payment is not completed for the original invoice."))

	refund_amount = abs(_get_invoice_total(doc))
	if refund_amount <= 0:
		return

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

	return


def trigger_sumup_return_refund(doc, method=None):
	if not doc or not getattr(doc, "is_return", 0):
		return

	if (getattr(doc, "sumup_refund_status", "") or "").upper() == "SUCCESSFUL":
		return

	settings = get_sumup_settings()
	if not settings.enabled:
		return

	return_against = (getattr(doc, "return_against", "") or "").strip()
	if not return_against:
		return

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	if not transaction_id:
		return

	refund_amount = abs(_get_invoice_total(doc))
	if refund_amount <= 0:
		return

	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		{
			"sumup_transaction_id": transaction_id,
			"sumup_refund_amount": refund_amount,
			"sumup_refund_status": "PENDING",
		},
		update_modified=False,
	)

	def _run_refund():
		_execute_sumup_return_refund(doc.name)

	frappe.db.after_commit(_run_refund)


def _execute_sumup_return_refund(return_doc_name: str):
	doc = frappe.get_doc("POS Invoice", return_doc_name)
	if not doc or not getattr(doc, "is_return", 0):
		return

	if (getattr(doc, "sumup_refund_status", "") or "").upper() == "SUCCESSFUL":
		return

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			{
				"sumup_refund_status": "FAILED",
				"sumup_refund_amount": flt(getattr(doc, "sumup_refund_amount", 0) or 0),
				"sumup_transaction_id": getattr(doc, "sumup_transaction_id", None),
			},
			update_modified=False,
		)
		frappe.log_error(
			message=_("SumUp is disabled in settings."),
			title=_("SumUp refund failed"),
		)
		return

	return_against = (getattr(doc, "return_against", "") or "").strip()
	if not return_against:
		return

	original = frappe.get_doc("POS Invoice", return_against)
	transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip()
	if not transaction_id:
		return

	refund_amount = flt(getattr(doc, "sumup_refund_amount", 0) or 0)
	if refund_amount <= 0:
		refund_amount = abs(_get_invoice_total(doc))
	if refund_amount <= 0:
		return

	original_status = (getattr(original, "sumup_status", "") or "").upper()
	if original_status and original_status != "SUCCESSFUL":
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			{
				"sumup_refund_status": "FAILED",
				"sumup_refund_amount": refund_amount,
				"sumup_transaction_id": transaction_id,
			},
			update_modified=False,
		)
		frappe.log_error(
			message=_("SumUp payment is not completed for the original invoice."),
			title=_("SumUp refund failed"),
		)
		return

	original_currency = (getattr(original, "sumup_currency", "") or "").strip() or (
		getattr(original, "currency", "") or ""
	).strip()
	if original_currency and getattr(doc, "currency", None) and doc.currency != original_currency:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			{
				"sumup_refund_status": "FAILED",
				"sumup_refund_amount": refund_amount,
				"sumup_transaction_id": transaction_id,
			},
			update_modified=False,
		)
		frappe.log_error(
			message=_("SumUp refund currency {0} does not match original currency {1}.").format(
				doc.currency, original_currency
			),
			title=_("SumUp refund failed"),
		)
		return

	refunded_total = flt(getattr(original, "sumup_refund_amount", 0) or 0)
	paid_total = flt(getattr(original, "sumup_amount", 0) or 0)
	if paid_total and refunded_total + refund_amount > paid_total + 0.0001:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			{
				"sumup_refund_status": "FAILED",
				"sumup_refund_amount": refund_amount,
				"sumup_transaction_id": transaction_id,
			},
			update_modified=False,
		)
		frappe.log_error(
			message=_("SumUp refund amount exceeds the original payment amount."),
			title=_("SumUp refund failed"),
		)
		return

	client = get_sumup_client(require_enabled=False)
	try:
		from sumup.transactions.resource import RefundTransactionBody
	except Exception:
		RefundTransactionBody = None

	payload = (
		RefundTransactionBody(amount=refund_amount) if RefundTransactionBody else {"amount": refund_amount}
	)
	try:
		client.transactions.refund(transaction_id, payload)
	except Exception as exc:
		frappe.db.set_value(
			"POS Invoice",
			doc.name,
			{
				"sumup_refund_status": "FAILED",
				"sumup_refund_amount": refund_amount,
				"sumup_transaction_id": transaction_id,
			},
			update_modified=False,
		)
		frappe.log_error(
			message=_("SumUp API error: {0}").format(exc),
			title=_("SumUp refund failed"),
		)
		return

	frappe.db.set_value(
		"POS Invoice",
		original.name,
		"sumup_refund_amount",
		refunded_total + refund_amount,
		update_modified=False,
	)

	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		{
			"sumup_refund_status": "SUCCESSFUL",
			"sumup_refund_amount": refund_amount,
			"sumup_transaction_id": transaction_id,
		},
		update_modified=False,
	)


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

	validate_sumup_return_refund(doc)

	refund_amount = abs(_get_invoice_total(doc))
	if refund_amount <= 0:
		frappe.throw(_("Refund amount must be greater than zero."))

	return_against = (getattr(doc, "return_against", "") or "").strip()
	transaction_id = None
	if return_against:
		original = frappe.get_doc("POS Invoice", return_against)
		transaction_id = (getattr(original, "sumup_transaction_id", "") or "").strip() or None

	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		{
			"sumup_refund_status": "PENDING",
			"sumup_refund_amount": refund_amount,
			"sumup_transaction_id": transaction_id,
		},
		update_modified=False,
	)

	_execute_sumup_return_refund(doc.name)

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
