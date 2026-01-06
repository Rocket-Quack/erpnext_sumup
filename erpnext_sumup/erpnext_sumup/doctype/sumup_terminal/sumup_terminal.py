# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	get_sumup_client,
	get_sumup_settings,
)


class SumUpTerminal(Document):
	pass


def _normalize_pairing_code(pairing_code: str | None) -> str:
	raw_code = (pairing_code or "").strip()
	if not raw_code:
		frappe.throw(_("API code is required."))

	normalized = re.sub(r"[\s-]+", "", raw_code).upper()
	if not re.fullmatch(r"[A-Z0-9]{8,9}", normalized):
		frappe.throw(_("API code must be 8-9 alphanumeric characters."))

	return normalized


def _normalize_terminal_name(terminal_name: str | None) -> str:
	name = (terminal_name or "").strip()
	if not name:
		frappe.throw(_("Terminal name is required."))
	return name


def _as_dict(value):
	if isinstance(value, dict):
		return value

	model_dump = getattr(value, "model_dump", None)
	if callable(model_dump):
		try:
			return model_dump()
		except TypeError:
			return model_dump(exclude_none=True)

	as_dict = getattr(value, "dict", None)
	if callable(as_dict):
		try:
			return as_dict()
		except TypeError:
			return as_dict(exclude_none=True)

	return {}


def _extract_reader_data(reader):
	reader_id = getattr(reader, "id", None)
	status = getattr(reader, "status", None)

	reader_data = _as_dict(reader)
	if not reader_id:
		reader_id = reader_data.get("id")
	if not status:
		status = reader_data.get("status")

	if reader_id is not None and not isinstance(reader_id, str):
		reader_id = str(reader_id)
	if status is not None and not isinstance(status, str):
		status = str(status)

	return reader_id, status


def _extract_reader_name(reader):
	name = getattr(reader, "name", None)
	if name:
		return str(name)

	reader_data = _as_dict(reader)
	if isinstance(reader_data, dict):
		value = reader_data.get("name")
		if value:
			return str(value)

	return None


def _parse_terminal_names(value):
	if not value:
		return []

	if isinstance(value, str):
		try:
			parsed = frappe.parse_json(value)
		except Exception:
			return [value]
		if isinstance(parsed, list):
			return parsed
		if parsed:
			return [parsed]
		return []

	if isinstance(value, list | tuple | set):
		return list(value)

	return [value]


def _normalize_connection_status(value) -> str:
	if not value:
		return "Unknown"

	normalized = re.sub(r"[\s-]+", "_", str(value).strip()).upper()
	if normalized == "PAIRED":
		return "Paired"
	if normalized == "PROCESSING":
		return "Processing"
	if normalized == "EXPIRED":
		return "Expired"

	return "Unknown"


def _normalize_online_status(value) -> str:
	if not value:
		return "Unknown"

	normalized = re.sub(r"[\s-]+", "_", str(value).strip()).upper()
	if normalized == "ONLINE":
		return "Online"
	if normalized == "OFFLINE":
		return "Offline"

	return "Unknown"


def _extract_status_payload(status_response):
	if status_response is None:
		return {}

	data = getattr(status_response, "data", None)
	payload = _as_dict(data) if data is not None else _as_dict(status_response)
	if not payload:
		if isinstance(status_response, dict):
			payload = status_response
		else:
			return {}

	if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
		return payload.get("data") or {}

	return payload if isinstance(payload, dict) else {}


def _normalize_activity_status(value) -> str:
	if not value:
		return "Unknown"

	normalized = re.sub(r"[\s-]+", "_", str(value).strip()).upper()
	status_map = {
		"IDLE": "Idle",
		"SELECTING_TIP": "Selecting Tip",
		"WAITING_FOR_CARD": "Waiting For Card",
		"WAITING_FOR_PIN": "Waiting For Pin",
		"WAITING_FOR_SIGNATURE": "Waiting For Signature",
		"UPDATING_FIRMWARE": "Updating Firmware",
	}

	return status_map.get(normalized, "Unknown")


def _extract_activity_status_value(payload: dict | None):
	if not payload:
		return None

	for key in ("screen_state", "screenState", "state"):
		value = payload.get(key)
		if value:
			return value

	return None


def _format_sumup_error(exc) -> str:
	parts = [str(exc)]
	status = getattr(exc, "status", None)
	body = getattr(exc, "body", None)
	if status:
		parts.append(f"status {status}")
	if body:
		body_text = frappe.as_json(body) if isinstance(body, dict | list) else str(body)
		parts.append(f"body {body_text}")
	return "; ".join(part for part in parts if part)


def _extract_online_status_value(payload: dict | None):
	if not payload:
		return None

	for key in ("status", "device_status", "deviceStatus"):
		value = payload.get(key)
		if value:
			return value

	return None


def _extract_reader_items(list_response):
	if list_response is None:
		return []

	items = getattr(list_response, "items", None)
	if isinstance(items, list):
		return items

	data = _as_dict(list_response)
	if isinstance(data, dict):
		items = data.get("items")
		if isinstance(items, list):
			return items

	if isinstance(list_response, dict):
		items = list_response.get("items")
		if isinstance(items, list):
			return items

	return []


def _fetch_reader_status_index(client, merchant_code: str) -> dict[str, str]:
	response = client.readers.list(merchant_code)
	items = _extract_reader_items(response)
	index: dict[str, str] = {}

	for item in items:
		item_id = getattr(item, "id", None) or _as_dict(item).get("id")
		item_status = getattr(item, "status", None) or _as_dict(item).get("status")
		if item_id:
			index[str(item_id)] = item_status

	return index


def _get_status_context(*, throw_on_missing: bool = True):
	settings = get_sumup_settings()
	if not settings.enabled:
		if throw_on_missing:
			frappe.throw(_("SumUp is disabled in settings."))
		return None, None

	merchant_code = (settings.merchant_code or "").strip()
	if not merchant_code:
		if throw_on_missing:
			frappe.throw(_("Merchant code is missing in SumUp Settings."))
		return None, None

	return get_sumup_client(require_enabled=False), merchant_code


def _get_linked_pos_profiles(terminal_name: str | None) -> list[str]:
	if not terminal_name:
		return []

	try:
		meta = frappe.get_meta("POS Profile")
	except Exception:
		return []

	if not meta.has_field("sumup_terminal"):
		return []

	return frappe.get_all("POS Profile", filters={"sumup_terminal": terminal_name}, pluck="name")


def _fetch_terminal_status_payload(client, merchant_code: str, terminal_id: str) -> dict:
	status_response = client.readers.get_status(merchant_code, terminal_id)
	return _extract_status_payload(status_response)


def _update_terminal_statuses(client, merchant_code: str, terminal: dict, reader_index=None):
	terminal_id = terminal.get("terminal_id") or terminal.get("name")
	errors = []
	connection_status = "Unknown"
	online_status = "Unknown"
	activity_status = "Unknown"

	try:
		if reader_index is None:
			reader_index = _fetch_reader_status_index(client, merchant_code)
		connection_value = reader_index.get(str(terminal_id))
		connection_status = _normalize_connection_status(connection_value)
	except Exception as exc:
		errors.append({"field": "connection_status", "error": exc})

	try:
		payload = _fetch_terminal_status_payload(client, merchant_code, terminal_id)
		online_value = _extract_online_status_value(payload)
		activity_value = _extract_activity_status_value(payload)
		online_status = _normalize_online_status(online_value)
		activity_status = _normalize_activity_status(activity_value)
	except Exception as exc:
		errors.append({"field": "online_status", "error": exc})
		errors.append({"field": "activity_status", "error": exc})

	if (
		errors
		and connection_status == "Unknown"
		and activity_status == "Unknown"
		and online_status == "Unknown"
	):
		raise errors[0]["error"]

	frappe.db.set_value(
		"SumUp Terminal",
		terminal.get("name") or terminal_id,
		"connection_status",
		connection_status,
	)
	frappe.db.set_value(
		"SumUp Terminal",
		terminal.get("name") or terminal_id,
		"activity_status",
		activity_status,
	)
	frappe.db.set_value(
		"SumUp Terminal",
		terminal.get("name") or terminal_id,
		"online_status",
		online_status,
	)
	return connection_status, online_status, activity_status, errors


@frappe.whitelist()
def pair_terminal(
	*,
	pairing_code: str | None = None,
	terminal_name: str | None = None,
	merchant_code: str | None = None,
):
	code = _normalize_pairing_code(pairing_code)
	name = _normalize_terminal_name(terminal_name)

	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	override_code = (merchant_code or "").strip()
	if override_code:
		if not debug_enabled:
			frappe.throw(_("Merchant code override is only available when debugging is enabled."))
		merchant_code = override_code
	else:
		merchant_code = (settings.merchant_code or "").strip()
		if not merchant_code:
			frappe.throw(_("Merchant code is missing in SumUp Settings."))

	client = get_sumup_client(require_enabled=False)

	try:
		from sumup.readers.resource import CreateReaderBody
	except Exception:
		CreateReaderBody = None

	payload = (
		CreateReaderBody(pairing_code=code, name=name)
		if CreateReaderBody
		else {"pairing_code": code, "name": name}
	)

	try:
		reader = client.readers.create(merchant_code, payload)
	except Exception as exc:
		status = getattr(exc, "status", None)
		body = getattr(exc, "body", None)
		detail_parts = []
		if status:
			detail_parts.append(_("status {0}").format(status))
		if body:
			body_text = frappe.as_json(body) if isinstance(body, dict | list) else str(body)
			detail_parts.append(_("body {0}").format(body_text))

		detail_text = f" ({', '.join(detail_parts)})" if detail_parts else ""
		frappe.throw(_("SumUp API error: {0}{1}").format(exc, detail_text))

	reader_id, status = _extract_reader_data(reader)
	if not reader_id:
		frappe.throw(_("Reader ID not found in SumUp response."))

	return {
		"reader_id": reader_id,
		"status": status,
		"merchant_code": merchant_code if debug_enabled else None,
		"message": _("Terminal paired."),
	}


@frappe.whitelist()
def pair_terminal_and_create(
	*,
	pairing_code: str | None = None,
	terminal_name: str | None = None,
	merchant_code: str | None = None,
):
	code = _normalize_pairing_code(pairing_code)
	name = _normalize_terminal_name(terminal_name)

	result = pair_terminal(pairing_code=code, terminal_name=name, merchant_code=merchant_code)
	reader_id = result.get("reader_id")
	status = result.get("status")
	if not reader_id:
		frappe.throw(_("Reader ID not found in SumUp response."))

	existing = frappe.db.exists("SumUp Terminal", {"terminal_id": reader_id})
	if existing:
		return {
			"reader_id": reader_id,
			"status": status,
			"docname": existing,
			"existing": True,
			"message": _("Terminal already exists."),
		}

	doc = frappe.get_doc(
		{
			"doctype": "SumUp Terminal",
			"terminal_id": reader_id,
			"terminal_name": name,
			"enabled": 1,
		}
	)
	doc.insert()

	return {
		"reader_id": reader_id,
		"status": status,
		"docname": doc.name,
		"message": _("Terminal paired and saved."),
	}


@frappe.whitelist()
def refresh_terminal_status(*, terminal_name: str | None = None):
	if not terminal_name:
		frappe.throw(_("Terminal is required."))

	terminal = frappe.db.get_value(
		"SumUp Terminal",
		terminal_name,
		["name", "terminal_id"],
		as_dict=True,
	)
	if not terminal:
		frappe.throw(_("Terminal not found."))

	client, merchant_code = _get_status_context()
	connection_status, online_status, activity_status, errors = _update_terminal_statuses(
		client, merchant_code, terminal
	)

	result = {
		"terminal": terminal.get("name"),
		"connection_status": connection_status,
		"online_status": online_status,
		"activity_status": activity_status,
		"message": _("Status updated."),
	}
	if errors and bool(getattr(get_sumup_settings(), "enable_debug_logging", 0)):
		result["debug_details"] = [
			{"field": item["field"], "error": _format_sumup_error(item["error"])} for item in errors
		]

	return result


@frappe.whitelist()
def refresh_terminal_statuses(*, terminal_names=None, throw_on_missing: bool = True):
	settings = get_sumup_settings()
	debug_enabled = bool(getattr(settings, "enable_debug_logging", 0))
	client, merchant_code = _get_status_context(throw_on_missing=throw_on_missing)
	if not client:
		return {
			"updated": [],
			"failed": [],
			"debug_enabled": debug_enabled,
			"message": _("SumUp is disabled or missing credentials."),
		}

	names = _parse_terminal_names(terminal_names)
	filters = {"name": ["in", names]} if names else {"enabled": 1}
	terminals = frappe.get_all(
		"SumUp Terminal",
		filters=filters,
		fields=["name", "terminal_id"],
	)

	if not terminals:
		return {
			"updated": [],
			"failed": [],
			"message": _("No terminals found."),
		}

	updated = []
	failed = []
	debug_details = []
	reader_index = None

	try:
		reader_index = _fetch_reader_status_index(client, merchant_code)
	except Exception as exc:
		if debug_enabled:
			debug_details.append({"name": "readers.list", "error": _format_sumup_error(exc)})

	for terminal in terminals:
		try:
			connection_status, online_status, activity_status, errors = _update_terminal_statuses(
				client, merchant_code, terminal, reader_index=reader_index
			)
			updated.append(
				{
					"name": terminal.get("name"),
					"connection_status": connection_status,
					"online_status": online_status,
					"activity_status": activity_status,
				}
			)
			if errors and debug_enabled:
				debug_details.append(
					{
						"name": terminal.get("name"),
						"errors": [
							{
								"field": item["field"],
								"error": _format_sumup_error(item["error"]),
							}
							for item in errors
						],
					}
				)
		except Exception as exc:
			error_text = _format_sumup_error(exc) if debug_enabled else str(exc)
			failed.append({"name": terminal.get("name"), "error": error_text})
			if debug_enabled:
				debug_details.append({"name": terminal.get("name"), "error": error_text})
			if not throw_on_missing:
				frappe.log_error(
					message=str(exc),
					title=_("SumUp terminal status update failed"),
				)

	message = _("Updated {0} terminal(s).").format(len(updated))
	if failed:
		message = _("Updated {0} terminal(s), {1} failed.").format(len(updated), len(failed))

	return {
		"updated": updated,
		"failed": failed,
		"debug_details": debug_details,
		"debug_enabled": debug_enabled,
		"message": message,
	}


def refresh_terminal_statuses_hourly():
	refresh_terminal_statuses(throw_on_missing=False)


@frappe.whitelist()
def recover_terminals_from_sumup():
	settings = get_sumup_settings()
	if not settings.enabled:
		frappe.throw(_("SumUp is disabled in settings."))

	if not getattr(settings, "enable_recovery_mode", 0):
		frappe.throw(_("Recovery mode is disabled in SumUp Settings."))

	merchant_code = (settings.merchant_code or "").strip()
	if not merchant_code:
		frappe.throw(_("Merchant code is missing in SumUp Settings."))

	client = get_sumup_client(require_enabled=False)
	try:
		response = client.readers.list(merchant_code)
	except Exception as exc:
		frappe.throw(_("SumUp API error: {0}").format(exc))

	items = _extract_reader_items(response)
	if not items:
		return {
			"created": [],
			"updated": [],
			"skipped": [],
			"failed": [],
			"message": _("No readers found in SumUp."),
		}

	entries = []
	failed = []
	for item in items:
		reader_id, reader_status = _extract_reader_data(item)
		if not reader_id:
			failed.append({"terminal_id": None, "error": _("Reader ID missing in SumUp response.")})
			continue
		reader_name = _extract_reader_name(item) or reader_id
		entries.append({"terminal_id": str(reader_id), "terminal_name": reader_name})

	if not entries:
		return {
			"created": [],
			"updated": [],
			"skipped": [],
			"failed": failed,
			"message": _("No valid readers found in SumUp response."),
		}

	existing = frappe.get_all(
		"SumUp Terminal",
		filters={"terminal_id": ["in", [entry["terminal_id"] for entry in entries]]},
		fields=["name", "terminal_id", "terminal_name"],
	)
	existing_index = {row["terminal_id"]: row for row in existing}

	created = []
	updated = []
	skipped = []

	for entry in entries:
		try:
			existing_row = existing_index.get(entry["terminal_id"])
			if existing_row:
				updates = {}
				terminal_name = (existing_row.get("terminal_name") or "").strip()
				if entry["terminal_name"] and entry["terminal_name"] != terminal_name:
					updates["terminal_name"] = entry["terminal_name"]
				if updates:
					frappe.db.set_value("SumUp Terminal", existing_row["name"], updates)
					updated.append({"name": existing_row["name"], "terminal_id": entry["terminal_id"]})
				else:
					skipped.append({"name": existing_row["name"], "terminal_id": entry["terminal_id"]})
				continue

			doc = frappe.get_doc(
				{
					"doctype": "SumUp Terminal",
					"terminal_id": entry["terminal_id"],
					"terminal_name": entry["terminal_name"],
					"enabled": 1,
				}
			)
			doc.insert()
			created.append({"name": doc.name, "terminal_id": entry["terminal_id"]})
		except Exception as exc:
			failed.append({"terminal_id": entry["terminal_id"], "error": _format_sumup_error(exc)})

	message = _("Recovered {0} terminal(s), updated {1}, skipped {2}, failed {3}.").format(
		len(created),
		len(updated),
		len(skipped),
		len(failed),
	)

	return {
		"created": created,
		"updated": updated,
		"skipped": skipped,
		"failed": failed,
		"message": message,
	}


@frappe.whitelist()
def remove_terminals(*, terminal_names=None):
	names = _parse_terminal_names(terminal_names)
	if not names:
		frappe.throw(_("Select terminals to remove."))

	client, merchant_code = _get_status_context()
	terminals = frappe.get_all(
		"SumUp Terminal",
		filters={"name": ["in", names]},
		fields=["name", "terminal_id"],
	)

	if not terminals:
		frappe.throw(_("No terminals found."))

	debug_enabled = bool(getattr(get_sumup_settings(), "enable_debug_logging", 0))
	removed = []
	failed = []
	debug_details = []

	for terminal in terminals:
		try:
			linked_profiles = _get_linked_pos_profiles(terminal.get("name"))
			if linked_profiles:
				frappe.throw(
					_("Cannot remove terminal {0} because it is linked to POS Profile(s): {1}.").format(
						terminal.get("name"), ", ".join(linked_profiles)
					)
				)

			client.readers.delete(merchant_code, terminal.get("terminal_id"))
			frappe.delete_doc("SumUp Terminal", terminal.get("name"))
			removed.append({"name": terminal.get("name")})
		except Exception as exc:
			error_text = _format_sumup_error(exc) if debug_enabled else str(exc)
			failed.append({"name": terminal.get("name"), "error": error_text})
			if debug_enabled:
				debug_details.append({"name": terminal.get("name"), "error": error_text})

	message = _("Removed {0} terminal(s).").format(len(removed))
	if failed:
		message = _("Removed {0} terminal(s), {1} failed.").format(len(removed), len(failed))

	return {
		"removed": removed,
		"failed": failed,
		"debug_details": debug_details,
		"debug_enabled": debug_enabled,
		"message": message,
	}


@frappe.whitelist()
def force_remove_terminals(*, terminal_names=None):
	names = _parse_terminal_names(terminal_names)
	if not names:
		frappe.throw(_("Select terminals to remove."))

	terminals = frappe.get_all(
		"SumUp Terminal",
		filters={"name": ["in", names]},
		fields=["name", "terminal_id"],
	)

	if not terminals:
		frappe.throw(_("No terminals found."))

	debug_enabled = bool(getattr(get_sumup_settings(), "enable_debug_logging", 0))
	removed = []
	failed = []
	debug_details = []

	for terminal in terminals:
		try:
			linked_profiles = _get_linked_pos_profiles(terminal.get("name"))
			if linked_profiles:
				frappe.throw(
					_("Cannot remove terminal {0} because it is linked to POS Profile(s): {1}.").format(
						terminal.get("name"), ", ".join(linked_profiles)
					)
				)

			frappe.delete_doc("SumUp Terminal", terminal.get("name"))
			removed.append({"name": terminal.get("name")})
		except Exception as exc:
			error_text = _format_sumup_error(exc) if debug_enabled else str(exc)
			failed.append({"name": terminal.get("name"), "error": error_text})
			if debug_enabled:
				debug_details.append({"name": terminal.get("name"), "error": error_text})

	message = _("Removed {0} terminal(s) locally.").format(len(removed))
	if failed:
		message = _("Removed {0} terminal(s) locally, {1} failed.").format(
			len(removed),
			len(failed),
		)

	return {
		"removed": removed,
		"failed": failed,
		"debug_details": debug_details,
		"debug_enabled": debug_enabled,
		"message": message,
	}
