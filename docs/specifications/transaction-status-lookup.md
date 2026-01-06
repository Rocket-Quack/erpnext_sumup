# Special Case: Transaction Status Lookup

This document explains how the POS transaction status is retrieved via the SumUp SDK.

## Context

- Location: `erpnext_sumup/erpnext_sumup/pos/pos_invoice.py`
- Function: `get_sumup_payment_status`
- Behavior: uses the SumUp SDK `transactions.get` method to fetch by `client_transaction_id`.

## SDK Requirement

The SumUp SDK exposes `transactions.get` starting with versions such as `sumup==0.0.20`. The implementation requires this SDK API and does not fall back to direct HTTP calls.

## Implications

- Older SDK versions without `transactions.get` are not supported.
- Error handling and response parsing follow the SDK behavior.

## When to Revisit

If the SDK changes the transactions API, update `get_sumup_payment_status` accordingly.
