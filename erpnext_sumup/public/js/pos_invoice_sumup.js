/* global erpnext_sumup */
(() => {
	if (typeof frappe === "undefined") {
		return;
	}
	if (window.__sumup_pos_invoice_loaded) {
		return;
	}
	window.__sumup_pos_invoice_loaded = true;

	frappe.provide("erpnext_sumup.pos");

	const sumup_debug = (typeof erpnext_sumup !== "undefined" && erpnext_sumup.debug) || {};
	const sumup_log_debug = sumup_debug.log || (() => {});
	const sumup_bind_refund_debug = sumup_debug.bind_refund_listener || (() => {});
	const sumup_confirm_return_refund = (frm) => {
		if (
			typeof erpnext_sumup !== "undefined" &&
			erpnext_sumup.pos &&
			typeof erpnext_sumup.pos.confirm_refund === "function"
		) {
			return erpnext_sumup.pos.confirm_refund(frm);
		}
		return Promise.resolve(true);
	};

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
		const status_defaults = {
			starting: __("Starting SumUp payment..."),
			waiting: __("Waiting for card confirmation..."),
			success: __("Payment confirmed."),
			error: __("SumUp payment failed."),
		};

		let status = "waiting";
		if (indicator === "success") {
			status = "success";
		} else if (indicator === "danger") {
			status = "error";
		} else if ((states || {}).start === "active") {
			status = "starting";
		}

		const label = __("SumUp Payment");
		const message_text = message || status_defaults[status] || "";

		const spinner_html =
			'<div class="sumup-status__spinner" role="img" aria-label="Loading"></div>';
		const success_icon = `
			<svg class="sumup-status__icon-svg" viewBox="0 0 64 64" aria-hidden="true">
				<circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" stroke-width="6" />
				<path d="M20 33 L28 41 L45 24" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>`;
		const error_icon = `
			<svg class="sumup-status__icon-svg" viewBox="0 0 64 64" aria-hidden="true">
				<circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" stroke-width="6" />
				<path d="M22 22 L42 42 M42 22 L22 42" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" />
			</svg>`;

		let icon_html = spinner_html;
		if (status === "success") {
			icon_html = success_icon;
		} else if (status === "error") {
			icon_html = error_icon;
		}

		const html = `
			<div class="sumup-status sumup-status--${status}">
				<div class="sumup-status__icon">${icon_html}</div>
				<div class="sumup-status__content">
					<div class="sumup-status__label">${frappe.utils.escape_html(label)}</div>
					<div class="sumup-status__message">${frappe.utils.escape_html(message_text)}</div>
				</div>
			</div>`;

		dialog.fields_dict.sumup_status_html.$wrapper.html(html);
	};

	const sumup_stop_polling = (dialog) => {
		if (dialog.__sumup_poll) {
			clearInterval(dialog.__sumup_poll);
			dialog.__sumup_poll = null;
		}
		dialog.__sumup_polling_locked = false;
	};

	const sumup_handle_save_fail = (frm, btn, on_error) => {
		if (frm && typeof frm.handle_save_fail === "function") {
			frm.handle_save_fail(btn, on_error);
			return;
		}
		if (btn) {
			$(btn).prop("disabled", false);
		}
		if (on_error) {
			on_error();
		}
	};

	const sumup_savesubmit_without_confirm = (frm, btn, callback, on_error) => {
		const me = frm;
		return new Promise((resolve) => {
			me.validate_form_action("Submit");

			frappe.validated = true;
			me.script_manager.trigger("before_submit").then(() => {
				if (!frappe.validated) {
					sumup_handle_save_fail(me, btn, on_error);
					return;
				}

				me.save(
					"Submit",
					(r) => {
						if (r.exc) {
							sumup_handle_save_fail(me, btn, on_error);
							return;
						}
						frappe.utils.play_sound("submit");
						callback && callback();
						me.script_manager
							.trigger("on_submit")
							.then(() => resolve(me))
							.then(() => {
								if (frappe.route_hooks.after_submit) {
									const route_callback = frappe.route_hooks.after_submit;
									delete frappe.route_hooks.after_submit;
									route_callback(me);
								}
							});
					},
					btn,
					() => sumup_handle_save_fail(me, btn, on_error)
				);
			});
		});
	};

	const sumup_submit_without_confirm = (frm, original_submit) => {
		if (!frm || typeof frm.savesubmit !== "function" || !original_submit) {
			return original_submit ? original_submit() : undefined;
		}

		const original_savesubmit = frm.savesubmit;
		frm.savesubmit = (btn, callback, on_error) =>
			sumup_savesubmit_without_confirm(frm, btn, callback, on_error);

		let result;
		try {
			result = original_submit();
		} catch (error) {
			frm.savesubmit = original_savesubmit;
			throw error;
		}

		if (result && result.then) {
			return result.finally(() => {
				frm.savesubmit = original_savesubmit;
			});
		}

		frm.savesubmit = original_savesubmit;
		return result;
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
				sumup_log_debug(result.debug_details, "status");
				if (
					result.transaction_id &&
					result.transaction_id !== frm.doc.sumup_transaction_id
				) {
					sumup_update_fields(frm, {
						sumup_transaction_id: result.transaction_id,
					});
				}
				const status = String(result.status || "").toUpperCase();

				if (status === "SUCCESSFUL") {
					sumup_stop_polling(dialog);
					const update_values = {
						sumup_status: "SUCCESSFUL",
						sumup_amount: result.amount || frm.doc.sumup_amount,
						sumup_currency: result.currency || frm.doc.sumup_currency,
					};
					if (result.transaction_id) {
						update_values.sumup_transaction_id = result.transaction_id;
					}
					sumup_update_fields(frm, update_values);
					sumup_render_steps(
						dialog,
						{ start: "done", wait: "done", done: "done" },
						__("Payment confirmed."),
						"success"
					);
					frm.__sumup_payment_in_progress = false;
					const result_submit = sumup_submit_without_confirm(frm, original_submit);
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
			sumup_log_debug(result.debug_details, "start");
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

		const isReturn = cint(frm.doc.is_return || 0);
		if (isReturn) {
			const confirmed = await sumup_confirm_return_refund(frm);
			if (!confirmed) {
				return;
			}
			return original_submit();
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

	const sumup_notify_refund_failed = (frm) => {
		if (!frm || !frm.doc) {
			return;
		}
		if (!cint(frm.doc.is_return || 0)) {
			return;
		}
		const status = String(frm.doc.sumup_refund_status || "").toUpperCase();
		if (status !== "FAILED") {
			return;
		}
		if (frm.__sumup_refund_failed_notified) {
			return;
		}
		frm.__sumup_refund_failed_notified = true;
		frappe.msgprint({
			title: __("SumUp Refund"),
			message: __("SumUp refund failed. You can retry the refund manually."),
			indicator: "red",
		});
	};

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
			sumup_patch_when_ready(frm);
			sumup_notify_refund_failed(frm);
		},
		after_payment_render(frm) {
			sumup_patch_when_ready(frm);
			sumup_notify_refund_failed(frm);
		},
	});

	sumup_run_ready(() => {
		sumup_patch_when_ready(window.cur_frm);
		sumup_attach_click_guard();
		sumup_bind_refund_debug();
	});
})();
