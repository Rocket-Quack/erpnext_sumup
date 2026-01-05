(() => {
	if (typeof frappe === "undefined") {
		return;
	}

	const confirm_sumup_refund = (frm) =>
		new Promise((resolve) => {
			frappe.call({
				method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_return_refund_preview",
				args: { pos_invoice: frm.doc.name },
				callback: (response) => {
					const result = response.message || {};
					if (!result.needs_refund) {
						resolve(true);
						return;
					}

					const amount = frappe.format(result.amount || 0, {
						fieldtype: "Currency",
						options: frm.doc.currency,
					});
					const currency = result.currency || frm.doc.currency || "";
					const message = __(
						"This return will automatically refund {0} {1} via SumUp. Continue?",
						[amount, currency]
					);

					frappe.confirm(
						message,
						() => resolve(true),
						() => resolve(false)
					);
				},
			});
		});

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
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

			return confirm_sumup_refund(frm);
		},
	});
})();
