# Copyright (c) 2025, RocketQuackIT and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	create_custom_fields_for_erpnext()


def after_migrate():
	create_custom_fields_for_erpnext()


def create_custom_fields_for_erpnext():
	custom_fields = {
		"POS Profile": [
			dict(
				fieldname="sumup_terminal",
				label="SumUp Terminal",
				fieldtype="Link",
				options="SumUp Terminal",
				insert_after="payments",
				reqd=0,
			),
		],
		"POS Payment Method": [
			dict(
				fieldname="use_sumup_terminal",
				label="Use SumUp Terminal",
				fieldtype="Check",
				default=0,
				insert_after="mode_of_payment",
				in_list_view=1,
			),
		],
		"POS Invoice": [
			dict(
				fieldname="sumup_section_break",
				label="SumUp",
				fieldtype="Section Break",
				insert_after="payments",
			),
			dict(
				fieldname="sumup_status",
				label="SumUp Status",
				fieldtype="Select",
				options="\nPENDING\nSUCCESSFUL\nFAILED\nCANCELLED",
				insert_after="sumup_section_break",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_client_transaction_id",
				label="SumUp Client Transaction ID",
				fieldtype="Data",
				insert_after="sumup_status",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_transaction_id",
				label="SumUp Transaction ID",
				fieldtype="Data",
				insert_after="sumup_client_transaction_id",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_amount",
				label="SumUp Amount",
				fieldtype="Currency",
				options="currency",
				insert_after="sumup_transaction_id",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_currency",
				label="SumUp Currency",
				fieldtype="Data",
				insert_after="sumup_amount",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_refund_status",
				label="SumUp Refund Status",
				fieldtype="Select",
				options="\nPENDING\nSUCCESSFUL\nFAILED",
				insert_after="sumup_currency",
				read_only=1,
				hidden=0,
			),
			dict(
				fieldname="sumup_refund_amount",
				label="SumUp Refund Amount",
				fieldtype="Currency",
				options="currency",
				insert_after="sumup_refund_status",
				read_only=1,
				hidden=0,
			),
		],
	}

	create_custom_fields(custom_fields, ignore_validate=True)
