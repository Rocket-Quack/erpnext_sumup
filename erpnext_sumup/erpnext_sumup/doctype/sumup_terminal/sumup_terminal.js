// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

frappe.ui.form.on("SumUp Terminal", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Refresh Status"), () => {
			frappe.call({
				method: "erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.refresh_terminal_status",
				args: {
					terminal_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Updating terminal status..."),
				callback: (response) => {
					const result = response.message || {};
					if (result.connection_status) {
						frm.set_value("connection_status", result.connection_status);
					}
					if (result.online_status) {
						frm.set_value("online_status", result.online_status);
					}
					if (result.activity_status) {
						frm.set_value("activity_status", result.activity_status);
					}
					frappe.msgprint(result.message || __("Status updated."));
				},
			});
		});
	},
});
