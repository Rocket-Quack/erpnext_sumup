/* global erpnext_sumup */
(() => {
	if (typeof frappe === "undefined") {
		return;
	}

	const sumup_debug = (typeof erpnext_sumup !== "undefined" && erpnext_sumup.debug) || {};
	const sumup_log_debug = sumup_debug.log || (() => {});
	const sumup_bind_refund_debug = sumup_debug.bind_refund_listener || (() => {});

	const confirm_sumup_refund = (frm) => {
		if (
			typeof erpnext_sumup !== "undefined" &&
			erpnext_sumup.pos &&
			typeof erpnext_sumup.pos.confirm_refund === "function"
		) {
			return erpnext_sumup.pos.confirm_refund(frm);
		}
		return Promise.resolve(true);
	};

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
			sumup_bind_refund_debug();
			if (!cint(frm.doc.is_return || 0)) {
				return;
			}

			if (!frm.__sumup_refund_failed_notified) {
				const status = String(frm.doc.sumup_refund_status || "").toUpperCase();
				if (status === "FAILED") {
					frm.__sumup_refund_failed_notified = true;
					frappe.msgprint({
						title: __("SumUp Refund"),
						message: __("SumUp refund failed. You can retry the refund manually."),
						indicator: "red",
					});
				}
			}

			const status = String(frm.doc.sumup_refund_status || "").toUpperCase();
			if (status !== "FAILED") {
				return;
			}

			frm.add_custom_button(__("Retry SumUp Refund"), () => {
				frappe.confirm(__("Retry the SumUp refund for this return?"), () => {
					frappe.call({
						method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.retry_sumup_return_refund",
						args: { pos_invoice: frm.doc.name },
						freeze: true,
						freeze_message: __("Retrying SumUp refund..."),
						callback: (response) => {
							const result = response.message || {};
							frm.reload_doc();
							frappe.msgprint(result.message || __("SumUp refund retry completed."));
						},
					});
				});
			});
		},
		before_submit(frm) {
			if (!cint(frm.doc.is_return || 0)) {
				return true;
			}

			if (frm.__sumup_refund_confirmed) {
				return true;
			}

			return confirm_sumup_refund(frm);
		},
	});
})();
