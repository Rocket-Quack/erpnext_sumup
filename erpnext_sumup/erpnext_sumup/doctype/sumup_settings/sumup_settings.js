// Copyright (c) 2025, RocketQuackIT and contributors
// For license information, please see license.txt

const update_fetch_merchant_code_button = (frm) => {
	frm.clear_custom_buttons();

	if (!frm.doc.enabled) {
		return;
	}

	frm.add_custom_button(__("Fetch Merchant Code"), () => {
		frm.call({
			doc: frm.doc,
			method: "fetch_merchant_code",
			args: {
				api_key: frm.doc.api_key,
			},
			freeze: true,
			freeze_message: __("Fetching merchant code..."),
			callback: (response) => {
				const merchant_code = response.message && response.message.merchant_code;
				const message = response.message && response.message.message;

				if (merchant_code) {
					frm.set_value("merchant_code", merchant_code);
				}

				frappe.msgprint(message || __("Merchant code updated."));
			},
		});
	});
};

frappe.ui.form.on("SumUp Settings", {
	refresh(frm) {
		update_fetch_merchant_code_button(frm);
	},
	enabled(frm) {
		update_fetch_merchant_code_button(frm);
	},
});
