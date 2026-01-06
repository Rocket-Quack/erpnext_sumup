/* global erpnext_sumup */
(() => {
	if (typeof frappe === "undefined") {
		return;
	}

	frappe.provide("erpnext_sumup.debug");

	const log = (details, label) => {
		if (!details) {
			return;
		}
		const prefix = label ? `SumUp Debug (${label})` : "SumUp Debug";
		if (console.groupCollapsed) {
			console.groupCollapsed(prefix);
			console.log(details);
			console.groupEnd();
			return;
		}
		console.log(prefix, details);
	};

	const bind_refund_listener = () => {
		if (window.__sumup_refund_debug_listener) {
			return;
		}
		window.__sumup_refund_debug_listener = true;
		if (frappe.realtime && frappe.realtime.on) {
			frappe.realtime.on("sumup_refund_debug", (data) => {
				log(data, "refund");
			});
		}
	};

	erpnext_sumup.debug.log = log;
	erpnext_sumup.debug.bind_refund_listener = bind_refund_listener;
})();
