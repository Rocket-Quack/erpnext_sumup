// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

const update_test_connection_button = (frm) => {
	frm.clear_custom_buttons();

	if (!frm.doc.enabled) {
		return;
	}

	frm.add_custom_button(__("Test Connection"), () => {
		frm.call({
			doc: frm.doc,
			method: "test_connection",
			args: {
				api_key: frm.doc.api_key,
			},
			freeze: true,
			freeze_message: __("Testing connection..."),
			callback: (response) => {
				const merchant_code = response.message && response.message.merchant_code;
				const message = response.message && response.message.message;

				if (merchant_code) {
					frm.set_value("merchant_code", merchant_code);
				}

				frappe.msgprint(message || __("Connection successful."));
			},
		});
	});
};

frappe.ui.form.on("SumUp Settings", {
	refresh(frm) {
		update_test_connection_button(frm);
	},
	enabled(frm) {
		update_test_connection_button(frm);
	},
});
