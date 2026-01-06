# Refund Flow (SumUp)

This guide explains how SumUp refunds work for POS return invoices, including prerequisites, validation, and retry.

## Overview

- Refunds are triggered automatically **after a return invoice is successfully submitted**.
- The refund uses the original SumUp transaction ID.
- If the refund fails, the return remains submitted and can be retried manually.

## Prerequisites

- SumUp Settings are enabled.
- The original POS Invoice was paid via SumUp and has:
  - `sumup_status = SUCCESSFUL`
  - `sumup_transaction_id` stored
- The return invoice amount is greater than zero.
- The return currency matches the original SumUp payment currency.

## Process

1. Open the original POS Invoice and click **Return** (or create a return in POS).
2. Adjust items/quantities and submit the return invoice.
3. A confirmation dialog appears, informing you that SumUp will refund the amount automatically.
4. After submit, the system triggers the SumUp refund in the background.

## Status Fields

On the return invoice:

- `sumup_refund_status`: `PENDING`, `SUCCESSFUL`, or `FAILED`
- `sumup_refund_amount`: refunded amount
- `sumup_transaction_id`: original transaction ID used for refund

On the original invoice:

- `sumup_refund_amount`: cumulative refunded amount

## Failure Handling

If the refund fails:

- The return invoice stays submitted.
- `sumup_refund_status` is set to `FAILED`.
- A user notification appears and a **Retry SumUp Refund** button is shown.

## Retry

Open the return invoice and click **Retry SumUp Refund**.

The retry is allowed only when:

- The return invoice is submitted
- `sumup_refund_status = FAILED`
- SumUp integration is enabled

## Notes

- Returns without SumUp payments are not affected.
- Refunds are not triggered if SumUp is disabled.
