/* global erpnext_sumup */
(() => {
	if (typeof frappe === "undefined") {
		return;
	}

	frappe.provide("erpnext_sumup.pos");

	const sumup_debug = (typeof erpnext_sumup !== "undefined" && erpnext_sumup.debug) || {};
	const sumup_log_debug = sumup_debug.log || (() => {});

	const get_confirm_key = (frm) => {
		if (!frm || !frm.doc) {
			return "";
		}
		const name = frm.doc.name || frm.doc.__tempname || "";
		const return_against = frm.doc.return_against || "";
		return `${name}::${return_against}`;
	};

	const confirm_refund = (frm) => {
		if (frm) {
			const key = get_confirm_key(frm);
			if (key && frm.__sumup_refund_confirmed_key === key) {
				return Promise.resolve(true);
			}
		}
		return new Promise((resolve) => {
			let resolved = false;
			const finalize = (value) => {
				if (resolved) {
					return;
				}
				resolved = true;
				resolve(value);
			};
			frappe.call({
				method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_return_refund_preview",
				args: { pos_invoice: frm.doc.name },
				callback: (response) => {
					const result = response.message || {};
					sumup_log_debug(result.debug_details, "return-preview");
					if (!result.needs_refund) {
						finalize(true);
						return;
					}

					const currency = result.currency || frm.doc.currency || "";
					const amount_value = flt(result.amount || 0);
					const amount = format_currency(amount_value, currency);
					const return_against = frm.doc.return_against || "";
					const escaped_return_against = frappe.utils.escape_html(
						return_against || __("Unknown")
					);
					const dialog = new frappe.ui.Dialog({
						title: __("SumUp Refund"),
						fields: [
							{
								fieldname: "sumup_refund_html",
								fieldtype: "HTML",
							},
						],
						primary_action_label: __("Yes, refund"),
						primary_action: () => {
							if (frm) {
								frm.__sumup_refund_confirmed_key = get_confirm_key(frm);
							}
							dialog.hide();
							finalize(true);
						},
					});
					dialog.set_secondary_action(() => {
						dialog.hide();
						finalize(false);
					});
					dialog.set_secondary_action_label(__("Cancel"));
					dialog.onhide = () => {
						if (!frm || frm.__sumup_refund_confirmed_key !== get_confirm_key(frm)) {
							finalize(false);
						}
					};
					dialog.show();
					const html = `
						<div class="sumup-refund-confirm">
							<div class="sumup-refund-confirm__label">${__("Refund Amount")}</div>
							<div class="sumup-refund-confirm__amount">
								${frappe.utils.escape_html(amount)}
							</div>
							<div class="sumup-refund-confirm__note">
								${__("This amount will be refunded via SumUp immediately.")}
							</div>
							<div class="sumup-refund-confirm__meta">
								${__("Return Against")}: ${escaped_return_against}
							</div>
						</div>`;
					dialog.fields_dict.sumup_refund_html.$wrapper.html(html);
				},
			});
		});
	};

	erpnext_sumup.pos.confirm_refund = confirm_refund;
})();
