app_name = "erpnext_sumup"
app_title = "ERPNext SumUp"
app_publisher = "RocketQuackIT"
app_description = "SumUp Integration für ERPNext"
app_email = "contact@rocketquack.eu"
app_license = "gpl-3.0"

# Apps
# ------------------

required_apps = ["erpnext"]

fixtures = [
	{
		"doctype": "Workspace",
		"filters": [
			["name", "in", ["SumUp Integration"]],
		],
	},
	{
		"doctype": "Number Card",
		"filters": [
			["name", "in", ["SumUp Terminals"]],
		],
	},
]


# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erpnext_sumup",
# 		"logo": "/assets/erpnext_sumup/logo.png",
# 		"title": "ERPNext SumUp",
# 		"route": "/erpnext_sumup",
# 		"has_permission": "erpnext_sumup.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/erpnext_sumup/css/pos_invoice_sumup.css"
app_include_js = [
	"/assets/erpnext_sumup/js/sumup_debug.js",
	"/assets/erpnext_sumup/js/sumup_refund_confirm.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_sumup/css/erpnext_sumup.css"
# web_include_js = "/assets/erpnext_sumup/js/erpnext_sumup.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_sumup/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {"point-of-sale": "public/js/pos_invoice_sumup.js"}

# include js in doctype views
doctype_js = {"POS Invoice": "public/js/pos_invoice_sumup_return.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erpnext_sumup/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpnext_sumup.utils.jinja_methods",
# 	"filters": "erpnext_sumup.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpnext_sumup.install.before_install"
after_install = "erpnext_sumup.install.after_install"
after_migrate = "erpnext_sumup.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "erpnext_sumup.uninstall.before_uninstall"
# after_uninstall = "erpnext_sumup.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpnext_sumup.utils.before_app_install"
# after_app_install = "erpnext_sumup.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpnext_sumup.utils.before_app_uninstall"
# after_app_uninstall = "erpnext_sumup.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_sumup.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

doc_events = {
	"POS Profile": {
		"validate": "erpnext_sumup.erpnext_sumup.pos.pos_profile.validate_pos_profile_sumup_terminal",
	},
	"POS Invoice": {
		"validate": "erpnext_sumup.erpnext_sumup.pos.pos_invoice.validate_pos_invoice_sumup_currency",
		"before_submit": [
			"erpnext_sumup.erpnext_sumup.pos.pos_invoice.validate_pos_invoice_sumup_payment_status",
			"erpnext_sumup.erpnext_sumup.pos.pos_invoice.validate_sumup_return_refund",
			"erpnext_sumup.erpnext_sumup.pos.pos_invoice.process_sumup_return_refund_before_submit",
		],
	},
}
# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"erpnext_sumup.erpnext_sumup.doctype.sumup_terminal.sumup_terminal.refresh_terminal_statuses_hourly",
	],
}

# Testing
# -------

# before_tests = "erpnext_sumup.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_sumup.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnext_sumup.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnext_sumup.utils.before_request"]
# after_request = ["erpnext_sumup.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnext_sumup.utils.before_job"]
# after_job = ["erpnext_sumup.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnext_sumup.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
