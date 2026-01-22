// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

const open_pairing_dialog = (listview) => {
	const fields = [
		{
			fieldname: "pairing_code",
			fieldtype: "Data",
			label: __("API Code"),
			reqd: 1,
			description: __(
				"Shown on the terminal under Connections > API > Connect (8-9 letters/numbers)."
			),
		},
		{
			fieldname: "terminal_name",
			fieldtype: "Data",
			label: __("Terminal Name"),
			reqd: 1,
		},
	];

	if (listview && listview.sumup_debug_enabled) {
		fields.push({
			fieldname: "merchant_code",
			fieldtype: "Data",
			label: __("Merchant Code Override"),
			description: __("Optional: use a different merchant code for this pairing only."),
		});
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Pair SumUp Terminal"),
		fields,
		primary_action_label: __("Pair"),
		primary_action: (values) => {
			const args = {
				pairing_code: values.pairing_code,
				terminal_name: values.terminal_name,
			};

			if (values.merchant_code) {
				args.merchant_code = values.merchant_code;
			}

			frappe.call({
				method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.pair_terminal_and_create",
				args,
				freeze: true,
				freeze_message: __("Pairing terminal..."),
				callback: (response) => {
					const result = response.message || {};

					if (result.docname) {
						listview.refresh();
						frappe.set_route("Form", "SumUp Terminal", result.docname);
					}

					let message = result.message || __("Terminal paired.");
					if (result.merchant_code) {
						message += `<br><br><strong>${__(
							"Merchant Code Used"
						)}</strong>: ${frappe.utils.escape_html(result.merchant_code)}`;
					}

					frappe.msgprint(message);
					dialog.hide();
				},
			});
		},
	});

	dialog.show();
};

const CONNECTION_STATUS_COLORS = {
	Paired: "green",
	Processing: "orange",
	Expired: "red",
	Unknown: "gray",
};

const get_connection_status_label = (value) => {
	if (!value) {
		return "Unknown";
	}

	const normalized = String(value)
		.trim()
		.toUpperCase()
		.replace(/[\s-]+/g, "_");
	if (normalized === "PAIRED") {
		return "Paired";
	}
	if (normalized === "PROCESSING") {
		return "Processing";
	}
	if (normalized === "EXPIRED") {
		return "Expired";
	}

	return "Unknown";
};

const ACTIVITY_STATUS_COLORS = {
	Idle: "green",
	"Selecting Tip": "orange",
	"Waiting For Card": "orange",
	"Waiting For Pin": "orange",
	"Waiting For Signature": "orange",
	"Updating Firmware": "yellow",
	Unknown: "gray",
};

const get_activity_status_label = (value) => {
	if (!value) {
		return "Unknown";
	}

	const normalized = String(value)
		.trim()
		.toUpperCase()
		.replace(/[\s-]+/g, "_");
	const status_map = {
		IDLE: "Idle",
		SELECTING_TIP: "Selecting Tip",
		WAITING_FOR_CARD: "Waiting For Card",
		WAITING_FOR_PIN: "Waiting For Pin",
		WAITING_FOR_SIGNATURE: "Waiting For Signature",
		UPDATING_FIRMWARE: "Updating Firmware",
	};

	return status_map[normalized] || "Unknown";
};

const get_selected_terminal_names = (listview) =>
	listview.get_checked_items().map((item) => item.name);

const refresh_terminal_statuses = (listview, terminal_names) => {
	const args = {};
	if (terminal_names && terminal_names.length) {
		args.terminal_names = terminal_names;
	}

	frappe.call({
		method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.refresh_terminal_statuses",
		args,
		freeze: true,
		freeze_message: __("Updating terminal status..."),
		callback: (response) => {
			const result = response.message || {};
			listview.refresh();
			show_status_message(result);
		},
	});
};

const get_status_indicator = (doc) => {
	const status = get_connection_status_label(doc.connection_status);
	const color = CONNECTION_STATUS_COLORS[status] || "gray";
	return [__(status), color, `connection_status,=,${status}`];
};

const ONLINE_STATUS_COLORS = {
	Online: "green",
	Offline: "red",
	Unknown: "gray",
};

const get_online_status_label = (value) => {
	if (!value) {
		return "Unknown";
	}

	const normalized = String(value)
		.trim()
		.toUpperCase()
		.replace(/[\s-]+/g, "_");
	if (normalized === "ONLINE") {
		return "Online";
	}
	if (normalized === "OFFLINE") {
		return "Offline";
	}

	return "Unknown";
};

const format_online_status = (value) => {
	const status = get_online_status_label(value);
	const color = ONLINE_STATUS_COLORS[status] || "gray";
	const label = __(status);
	const escaped_label = frappe.utils.escape_html(label);

	return `<span class="filterable indicator-pill ${color} ellipsis"
		data-filter="online_status,=,${status}"
		title="${escaped_label}">${escaped_label}</span>`;
};

const format_activity_status = (value) => {
	const status = get_activity_status_label(value);
	const color = ACTIVITY_STATUS_COLORS[status] || "gray";
	const label = __(status);
	const escaped_label = frappe.utils.escape_html(label);

	return `<span class="filterable indicator-pill ${color} ellipsis"
		data-filter="activity_status,=,${status}"
		title="${escaped_label}">${escaped_label}</span>`;
};

const show_status_message = (result) => {
	const message = result.message || __("Status updated.");
	const debugEnabled = result.debug_enabled;
	let details = result.debug_details || [];
	if (!details.length && debugEnabled && result.failed && result.failed.length) {
		details = result.failed.map((item) => ({
			name: item.name,
			error: item.error,
		}));
	}

	if (!details.length) {
		frappe.msgprint(message);
		return;
	}

	const detail_html = details
		.map((item) => {
			const name = frappe.utils.escape_html(item.name || "");
			if (item.errors && item.errors.length) {
				const error_list = item.errors
					.map((error_item) => {
						const field = frappe.utils.escape_html(error_item.field || "");
						const error = frappe.utils.escape_html(error_item.error || "");
						return `<div>${field}: ${error}</div>`;
					})
					.join("");
				return `<div><strong>${name}</strong><div>${error_list}</div></div>`;
			}

			const error = frappe.utils.escape_html(item.error || "");
			return `<div><strong>${name}</strong>: ${error}</div>`;
		})
		.join("");

	frappe.msgprint({
		title: __("Status Update"),
		message: `${frappe.utils.escape_html(message)}<br><br>${detail_html}`,
		indicator: result.failed && result.failed.length ? "orange" : "green",
	});
};

const show_recovery_message = (result) => {
	const message = result.message || __("Recovery completed.");
	const failed = result.failed || [];

	if (!failed.length) {
		frappe.msgprint(message);
		return;
	}

	const detail_html = failed
		.map((item) => {
			const terminalId = frappe.utils.escape_html(item.terminal_id || "");
			const error = frappe.utils.escape_html(item.error || "");
			const label = terminalId ? terminalId : __("Unknown Reader");
			return `<div><strong>${label}</strong>: ${error}</div>`;
		})
		.join("");

	frappe.msgprint({
		title: __("Recovery Sync"),
		message: `${frappe.utils.escape_html(message)}<br><br>${detail_html}`,
		indicator: "orange",
	});
};

const ensure_sumup_enabled = (listview) => {
	if (listview && typeof listview.sumup_enabled === "boolean") {
		if (!listview.sumup_enabled) {
			frappe.msgprint(__("SumUp is disabled in settings."));
		}
		return Promise.resolve(listview.sumup_enabled);
	}

	return frappe.db.get_value("SumUp Settings", "SumUp Settings", "enabled").then((response) => {
		const enabled = !!cint(response.message && response.message.enabled);
		if (listview) {
			listview.sumup_enabled = enabled;
		}
		if (!enabled) {
			frappe.msgprint(__("SumUp is disabled in settings."));
		}
		return enabled;
	});
};

const run_recovery_sync = (listview) => {
	frappe.confirm(__("Fetch readers from SumUp and sync local terminals?"), () => {
		frappe.call({
			method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.recover_terminals_from_sumup",
			freeze: true,
			freeze_message: __("Syncing terminals..."),
			callback: (response) => {
				const result = response.message || {};
				listview.refresh();
				show_recovery_message(result);
			},
		});
	});
};

const remove_selected_terminals = (listview) => {
	const terminal_names = get_selected_terminal_names(listview);
	if (!terminal_names.length) {
		frappe.msgprint(__("Select at least one terminal."));
		return;
	}

	ensure_sumup_enabled(listview).then((enabled) => {
		if (!enabled) {
			return;
		}

		frappe.confirm(
			__("Remove {0} terminal(s) from SumUp and delete locally?", [terminal_names.length]),
			() => {
				frappe.call({
					method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.remove_terminals",
					args: {
						terminal_names,
					},
					freeze: true,
					freeze_message: __("Removing terminals..."),
					callback: (response) => {
						const result = response.message || {};
						listview.refresh();
						show_status_message(result);
					},
				});
			}
		);
	});
};

const force_remove_selected_terminals = (listview) => {
	const terminal_names = get_selected_terminal_names(listview);
	if (!terminal_names.length) {
		frappe.msgprint(__("Select at least one terminal."));
		return;
	}

	frappe.confirm(
		__("Remove {0} terminal(s) locally only? This does not remove the terminal in SumUp.", [
			terminal_names.length,
		]),
		() => {
			frappe.call({
				method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.force_remove_terminals",
				args: {
					terminal_names,
				},
				freeze: true,
				freeze_message: __("Removing terminals locally..."),
				callback: (response) => {
					const result = response.message || {};
					listview.refresh();
					show_status_message(result);
				},
			});
		}
	);
};

frappe.listview_settings["SumUp Terminal"] = {
	add_fields: ["connection_status", "online_status", "activity_status"],
	onload(listview) {
		listview.sumup_debug_enabled = false;
		listview.sumup_enabled = undefined;
		const refresh_action = () => {
			const terminal_names = get_selected_terminal_names(listview);
			refresh_terminal_statuses(listview, terminal_names.length ? terminal_names : null);
		};

		const action = () => {
			open_pairing_dialog(listview);
		};

		listview.settings.primary_action = action;
		listview.set_primary_action = () => {
			if (listview.can_create && !frappe.boot.read_only) {
				listview.page.set_primary_action(__("Pair Terminal"), action, "add");
				listview.page.set_secondary_action(__("Refresh Status"), refresh_action);
			} else {
				listview.page.clear_primary_action();
				listview.page.clear_secondary_action();
			}
		};

		listview.set_primary_action();

		listview.page.clear_actions_menu();
		listview.page.add_actions_menu_item(__("Remove from SumUp"), () => {
			remove_selected_terminals(listview);
		});
		listview.page.add_inner_button(__("Remove from SumUp"), () => {
			remove_selected_terminals(listview);
		});

		frappe.db
			.get_value("SumUp Settings", "SumUp Settings", "enable_debug_logging")
			.then((response) => {
				const enabled = cint(response.message && response.message.enable_debug_logging);
				listview.sumup_debug_enabled = !!enabled;
				if (!enabled) {
					return;
				}

				listview.page.add_inner_button(__("Force Remove (Local Only)"), () => {
					force_remove_selected_terminals(listview);
				});
			});

		frappe.db
			.get_value("SumUp Settings", "SumUp Settings", "enable_recovery_mode")
			.then((response) => {
				const enabled = cint(response.message && response.message.enable_recovery_mode);
				if (!enabled) {
					return;
				}

				listview.page.add_inner_button(__("Recovery Sync"), () => {
					run_recovery_sync(listview);
				});
			});
	},
	get_indicator: get_status_indicator,
	formatters: {
		online_status: format_online_status,
		activity_status: format_activity_status,
	},
};
