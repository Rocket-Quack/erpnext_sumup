# Copyright (c) 2025, RocketQuackIT and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from erpnext_sumup.erpnext_sumup.integrations.sumup_client import (
	extract_merchant_code,
	extract_merchant_currency,
	normalize_api_key,
)


class TestSumUpSettings(FrappeTestCase):
	def test_normalize_api_key(self):
		self.assertIsNone(normalize_api_key(None))
		self.assertIsNone(normalize_api_key(""))
		self.assertIsNone(normalize_api_key("   "))
		self.assertIsNone(normalize_api_key("*****"))
		self.assertEqual(normalize_api_key("sk_live_test"), "sk_live_test")

	def test_extract_merchant_code_from_dict(self):
		self.assertEqual(extract_merchant_code({"merchant_code": "mc_1"}), "mc_1")
		self.assertEqual(
			extract_merchant_code({"merchant_profile": {"merchant_code": "mc_2"}}),
			"mc_2",
		)

	def test_extract_merchant_code_from_objects(self):
		class Profile:
			def __init__(self, merchant_code):
				self.merchant_code = merchant_code

		class NestedProfile:
			def __init__(self, merchant_code):
				self.merchant_profile = Profile(merchant_code)

		class DumpProfile:
			def model_dump(self):
				return {"merchant_profile": {"merchant_code": "mc_3"}}

		self.assertEqual(extract_merchant_code(Profile("mc_1")), "mc_1")
		self.assertEqual(extract_merchant_code(NestedProfile("mc_2")), "mc_2")
		self.assertEqual(extract_merchant_code(DumpProfile()), "mc_3")

	def test_extract_merchant_code_missing(self):
		self.assertIsNone(extract_merchant_code({}))
		self.assertIsNone(extract_merchant_code(object()))

	def test_extract_merchant_currency_from_dict(self):
		self.assertEqual(extract_merchant_currency({"currency": "EUR"}), "EUR")
		self.assertEqual(extract_merchant_currency({"currency_code": "USD"}), "USD")
		self.assertEqual(
			extract_merchant_currency({"merchant_profile": {"currency": "GBP"}}),
			"GBP",
		)

	def test_extract_merchant_currency_from_objects(self):
		class Profile:
			def __init__(self, currency):
				self.currency = currency

		class NestedProfile:
			def __init__(self, currency_code):
				self.merchant_profile = Profile(currency_code)

		class DumpProfile:
			def model_dump(self):
				return {"merchant_profile": {"default_currency": "CHF"}}

		self.assertEqual(extract_merchant_currency(Profile("EUR")), "EUR")
		self.assertEqual(extract_merchant_currency(NestedProfile("SEK")), "SEK")
		self.assertEqual(extract_merchant_currency(DumpProfile()), "CHF")

	def test_extract_merchant_currency_missing(self):
		self.assertIsNone(extract_merchant_currency({}))
		self.assertIsNone(extract_merchant_currency(object()))
