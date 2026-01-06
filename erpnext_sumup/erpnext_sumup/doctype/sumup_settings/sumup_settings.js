// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

const update_settings_buttons = (frm) => {
	frm.clear_custom_buttons();

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
				const merchant_currency = response.message && response.message.merchant_currency;
				const message = response.message && response.message.message;

				if (merchant_currency) {
					frm.set_value("merchant_currency", merchant_currency);
				}

				frappe.msgprint(message || __("Connection successful."));
			},
		});
	});

	if (!frm.doc.enabled) {
		return;
	}

	frm.add_custom_button(__("Validate Merchant Code"), () => {
		frm.call({
			doc: frm.doc,
			method: "fetch_merchant_code",
			args: {
				api_key: frm.doc.api_key,
			},
			freeze: true,
			freeze_message: __("Validating merchant code..."),
			callback: (response) => {
				const merchant_currency = response.message && response.message.merchant_currency;
				const message = response.message && response.message.message;

				if (merchant_currency) {
					frm.set_value("merchant_currency", merchant_currency);
				}

				frappe.msgprint(message || __("Merchant code validated."));
			},
		});
	});
};

frappe.ui.form.on("SumUp Settings", {
	refresh(frm) {
		update_settings_buttons(frm);
	},
	enabled(frm) {
		update_settings_buttons(frm);
	},
});
