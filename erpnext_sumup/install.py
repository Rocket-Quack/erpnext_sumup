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
	}

	create_custom_fields(custom_fields, ignore_validate=True)
