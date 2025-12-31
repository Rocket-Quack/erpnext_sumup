(() => {
	if (typeof frappe === "undefined") {
		return;
	}
	if (window.__sumup_pos_invoice_loaded) {
		return;
	}
	window.__sumup_pos_invoice_loaded = true;

	frappe.provide("erpnext_sumup.pos");

	const sumup_get_invoice_total = (doc) => {
		const disableRounded = cint(frappe.sys_defaults.disable_rounded_total || 0);
		const total = disableRounded ? doc.grand_total : doc.rounded_total || doc.grand_total;
		return flt(total);
	};

	const sumup_get_modes = (pos) => {
		const payments = (pos && pos.settings && pos.settings.payments) || [];
		return payments
			.filter((row) => cint(row.use_sumup_terminal))
			.map((row) => row.mode_of_payment);
	};

	const sumup_get_breakdown = (doc, sumup_modes) => {
		let sumup_rows = [];
		let sumup_amount = 0;
		let other_amount = 0;
		(doc.payments || []).forEach((row) => {
			const amount = flt(row.amount || 0);
			if (amount <= 0) {
				return;
			}
			if (sumup_modes.includes(row.mode_of_payment)) {
				sumup_rows.push(row);
				sumup_amount += amount;
			} else {
				other_amount += amount;
			}
		});
		return { sumup_rows, sumup_amount, other_amount };
	};

	const sumup_is_full_amount = (breakdown, total) => {
		if (!breakdown.sumup_amount) {
			return false;
		}
		if (breakdown.other_amount > 0) {
			return false;
		}
		if (breakdown.sumup_rows.length !== 1) {
			return false;
		}
		return Math.abs(breakdown.sumup_amount - total) < 0.0001;
	};

	const sumup_update_fields = (frm, values) => {
		Object.keys(values || {}).forEach((key) => {
			frm.set_value(key, values[key]);
		});
	};

	const sumup_clear_payment_rows = async (frm, pos, sumup_modes) => {
		if (!frm || !pos || !pos.payment) {
			return;
		}
		if (!sumup_modes || !sumup_modes.length) {
			return;
		}
		const rows = (frm.doc.payments || []).filter((row) =>
			sumup_modes.includes(row.mode_of_payment)
		);
		if (!rows.length) {
			return;
		}
		await Promise.all(
			rows.map((row) => frappe.model.set_value(row.doctype, row.name, "amount", 0))
		);
		pos.payment.update_totals_section(frm.doc);
		pos.payment.render_payment_mode_dom();
	};

	const sumup_save_if_dirty = async (frm) => {
		if (!frm || !frm.is_dirty || !frm.is_dirty()) {
			return true;
		}
		let save_failed = false;
		await frm.save(null, null, null, () => {
			save_failed = true;
		});
		return !save_failed;
	};

	const sumup_resolve_frm = (frm, pos) => {
		if (frm && frm.doc) {
			return frm;
		}
		if (pos && pos.payment && pos.payment.events && pos.payment.events.get_frm) {
			const resolved = pos.payment.events.get_frm();
			if (resolved && resolved.doc) {
				return resolved;
			}
		}
		return frm;
	};

	const sumup_patch_submit_handler = (frm) => {
		const pos = window.cur_pos;
		if (!pos || !pos.payment || !pos.payment.events) {
			return false;
		}

		if (!pos.payment.__sumup_original_submit_invoice) {
			pos.payment.__sumup_original_submit_invoice = pos.payment.events.submit_invoice;
			pos.payment.events.submit_invoice = () => {
				const current_frm = sumup_resolve_frm(pos.payment.__sumup_current_frm, pos);
				return sumup_handle_submit(
					current_frm,
					pos,
					pos.payment.__sumup_original_submit_invoice
				);
			};
		}

		const resolved_frm = sumup_resolve_frm(frm, pos);
		if (resolved_frm) {
			pos.payment.__sumup_current_frm = resolved_frm;
		}
		return true;
	};

	const sumup_patch_when_ready = (frm, attempt = 0) => {
		if (sumup_patch_submit_handler(frm)) {
			return;
		}

		if (attempt >= 5) {
			return;
		}

		setTimeout(() => sumup_patch_when_ready(frm, attempt + 1), 250);
	};

	const sumup_attach_click_guard = () => {
		if (sumup_attach_click_guard.__attached) {
			return;
		}
		sumup_attach_click_guard.__attached = true;

		document.addEventListener(
			"click",
			(event) => {
				const target = event.target;
				if (!target || !target.closest) {
					return;
				}
				if (!target.closest(".payment-container .submit-order-btn")) {
					return;
				}
				sumup_patch_submit_handler(window.cur_frm);
			},
			true
		);
	};

	const sumup_render_steps = (dialog, states, message, indicator) => {
		const steps = [
			{ id: "start", label: __("Starting SumUp payment...") },
			{ id: "wait", label: __("Waiting for card confirmation...") },
			{ id: "done", label: __("Payment confirmed.") },
		];
		const icons = {
			done: "[x]",
			active: "...",
			pending: "[ ]",
			error: "!",
		};

		const html = steps
			.map((step) => {
				const state = states[step.id] || "pending";
				const icon = icons[state] || icons.pending;
				return `<div class="sumup-step"><span>${icon}</span> ${frappe.utils.escape_html(
					step.label
				)}</div>`;
			})
			.join("");

		let message_html = "";
		if (message) {
			const safe_message = frappe.utils.escape_html(message);
			const cls = indicator ? `text-${indicator}` : "text-muted";
			message_html = `<div class="mt-3 ${cls}">${safe_message}</div>`;
		}

		dialog.fields_dict.sumup_status_html.$wrapper.html(`${html}${message_html}`);
	};

	const sumup_stop_polling = (dialog) => {
		if (dialog.__sumup_poll) {
			clearInterval(dialog.__sumup_poll);
			dialog.__sumup_poll = null;
		}
		dialog.__sumup_polling_locked = false;
	};

	const sumup_start_polling = (dialog, frm, original_submit) => {
		const poll = async () => {
			if (dialog.__sumup_polling_locked) {
				return;
			}
			dialog.__sumup_polling_locked = true;
			try {
				const res = await frappe.call({
					method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.get_sumup_payment_status",
					args: { pos_invoice: frm.doc.name },
				});
				const result = res.message || {};
				const status = String(result.status || "").toUpperCase();

				if (status === "SUCCESSFUL") {
					sumup_stop_polling(dialog);
					sumup_update_fields(frm, {
						sumup_status: "SUCCESSFUL",
						sumup_amount: result.amount || frm.doc.sumup_amount,
						sumup_currency: result.currency || frm.doc.sumup_currency,
					});
					sumup_render_steps(
						dialog,
						{ start: "done", wait: "done", done: "done" },
						__("Payment confirmed."),
						"success"
					);
					frm.__sumup_payment_in_progress = false;
					const result_submit = original_submit();
					if (result_submit && result_submit.then) {
						result_submit.finally(() => dialog.hide());
					} else {
						setTimeout(() => dialog.hide(), 300);
					}
					return;
				}

				if (status === "FAILED" || status === "CANCELLED") {
					sumup_stop_polling(dialog);
					sumup_update_fields(frm, { sumup_status: status });
					sumup_render_steps(
						dialog,
						{ start: "done", wait: "error", done: "pending" },
						__("SumUp payment failed."),
						"danger"
					);
					frm.__sumup_payment_in_progress = false;
					return;
				}

				sumup_render_steps(
					dialog,
					{ start: "done", wait: "active", done: "pending" },
					__("Waiting for card confirmation..."),
					"muted"
				);
			} catch (error) {
				sumup_stop_polling(dialog);
				sumup_render_steps(
					dialog,
					{ start: "done", wait: "error", done: "pending" },
					__("Unable to fetch SumUp payment status."),
					"danger"
				);
				frm.__sumup_payment_in_progress = false;
			} finally {
				dialog.__sumup_polling_locked = false;
			}
		};

		poll();
		dialog.__sumup_poll = setInterval(poll, 3000);
	};

	const sumup_show_dialog = async (frm, pos, original_submit) => {
		const dialog = new frappe.ui.Dialog({
			title: __("SumUp Payment"),
			fields: [
				{
					fieldname: "sumup_status_html",
					fieldtype: "HTML",
				},
			],
			primary_action_label: __("Cancel Payment"),
			primary_action: async () => {
				sumup_stop_polling(dialog);
				try {
					await frappe.call({
						method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.cancel_sumup_payment",
						args: { pos_invoice: frm.doc.name },
					});
				} catch (error) {
					frappe.msgprint({
						title: __("SumUp Payment"),
						message: __("Unable to cancel SumUp payment."),
						indicator: "red",
					});
				}
				sumup_update_fields(frm, {
					sumup_status: "CANCELLED",
					sumup_client_transaction_id: null,
					sumup_amount: 0,
					sumup_currency: null,
				});
				await sumup_clear_payment_rows(frm, pos, sumup_get_modes(pos));
				frm.__sumup_payment_in_progress = false;
				dialog.hide();
			},
		});

		sumup_render_steps(
			dialog,
			{ start: "active", wait: "pending", done: "pending" },
			__("Starting SumUp payment..."),
			"muted"
		);
		dialog.show();

		try {
			const res = await frappe.call({
				method: "erpnext_sumup.erpnext_sumup.pos.pos_invoice.start_sumup_payment",
				args: { pos_invoice: frm.doc.name },
			});
			const result = res.message || {};
			if (!result.client_transaction_id) {
				throw new Error(__("Unable to start SumUp payment."));
			}

			sumup_update_fields(frm, {
				sumup_status: "PENDING",
				sumup_client_transaction_id: result.client_transaction_id,
				sumup_amount: frm.doc.sumup_amount || sumup_get_invoice_total(frm.doc),
				sumup_currency: frm.doc.currency,
			});

			sumup_render_steps(
				dialog,
				{ start: "done", wait: "active", done: "pending" },
				__("Waiting for card confirmation..."),
				"muted"
			);
			sumup_start_polling(dialog, frm, original_submit);
		} catch (error) {
			sumup_stop_polling(dialog);
			sumup_render_steps(
				dialog,
				{ start: "error", wait: "pending", done: "pending" },
				__("Unable to start SumUp payment."),
				"danger"
			);
			frm.__sumup_payment_in_progress = false;
		}
		return dialog;
	};

	const sumup_handle_submit = async (frm, pos, original_submit) => {
		if (!pos) {
			return original_submit();
		}

		const resolved_frm = sumup_resolve_frm(frm, pos);
		if (!resolved_frm || !resolved_frm.doc) {
			return original_submit();
		}
		frm = resolved_frm;
		if (frm.__sumup_payment_in_progress) {
			return;
		}

		const sumup_modes = sumup_get_modes(pos);
		if (!sumup_modes.length) {
			return original_submit();
		}

		const breakdown = sumup_get_breakdown(frm.doc, sumup_modes);
		if (!breakdown.sumup_amount) {
			return original_submit();
		}

		const total = sumup_get_invoice_total(frm.doc);
		if (!sumup_is_full_amount(breakdown, total)) {
			frappe.show_alert({
				message: __("SumUp payment must cover the full invoice amount."),
				indicator: "red",
			});
			frappe.utils.play_sound("error");
			return;
		}

		const saved = await sumup_save_if_dirty(frm);
		if (!saved) {
			frappe.show_alert({
				message: __("There was an error saving the document."),
				indicator: "red",
			});
			frappe.utils.play_sound("error");
			return;
		}

		frm.__sumup_payment_in_progress = true;
		await sumup_show_dialog(frm, pos, original_submit);
	};

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
			sumup_patch_when_ready(frm);
		},
		after_payment_render(frm) {
			sumup_patch_when_ready(frm);
		},
	});

	const sumup_run_ready = (handler) => {
		if (typeof frappe.ready === "function") {
			frappe.ready(handler);
			return;
		}
		if (typeof $ === "function") {
			$(handler);
			return;
		}
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", handler);
			return;
		}
		handler();
	};

	sumup_run_ready(() => {
		sumup_patch_when_ready(window.cur_frm);
		sumup_attach_click_guard();
	});
})();
