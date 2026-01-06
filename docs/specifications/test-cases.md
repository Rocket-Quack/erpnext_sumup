# Test Cases (ERPNext SumUp)

This document lists functional and technical test cases for the SumUp integration.

## Scope

- SumUp Settings validation and connection checks
- SumUp Terminal management and status updates
- POS Profile and POS Invoice validation
- POS payment flow (start, poll, submit, cancel)
- Recovery Mode sync

## Test Data (Baseline)

- SumUp API key and merchant code for a test account
- One paired SumUp reader in the SumUp account
- ERPNext POS Profile with at least one payment method
- One POS Invoice in Draft status

## Functional Test Cases

### Settings

- TC-SET-001: Enable SumUp without API Key -> validation error
- TC-SET-002: Enable SumUp without Merchant Code -> validation error
- TC-SET-003: Test Connection sets Merchant Currency when API is valid
- TC-SET-004: Enable Debugging allows Merchant Code Override during pairing
- TC-SET-005: Enable Recovery Mode shows Recovery Sync button in SumUp Terminal list

### Terminal Pairing and Management

- TC-TERM-001: Pair terminal with valid pairing code -> new SumUp Terminal created
- TC-TERM-002: Pair terminal with invalid code format -> validation error
- TC-TERM-003: Pair terminal with existing reader -> terminal already exists message
- TC-TERM-004: Refresh status updates connection, online, activity fields
- TC-TERM-005: Remove terminal blocked when linked to POS Profile

### POS Profile

- TC-PRO-001: SumUp payment method set, no terminal -> validation error
- TC-PRO-002: SumUp payment method set, terminal disabled -> validation error
- TC-PRO-003: SumUp payment method set, active terminal -> validation passes

### POS Invoice - Validation

- TC-INV-001: SumUp payment not configured in POS Profile -> error on start
- TC-INV-002: SumUp payment selected, amount is zero -> error on start
- TC-INV-003: Multiple SumUp payment rows -> error on start and submit
- TC-INV-004: SumUp amount not equal to total -> error on start and submit
- TC-INV-005: POS currency does not match merchant currency -> validation error
- TC-INV-006: Submit without SUCCESSFUL status -> submit blocked
- TC-INV-007: Submit without transaction id -> submit blocked

### POS Payment Flow (UI + Backend)

- TC-FLOW-001: Start payment sets PENDING and client transaction id
- TC-FLOW-002: Polling returns SUCCESSFUL -> sumup_status updated, submit allowed
- TC-FLOW-003: Polling returns FAILED -> dialog shows error, submit blocked
- TC-FLOW-004: Cancel payment -> sumup fields reset, payment rows cleared
- TC-FLOW-005: Retry after FAILED -> new checkout created with new transaction id

### Recovery Mode

- TC-REC-001: Recovery Sync imports new readers as SumUp Terminal records
- TC-REC-002: Recovery Sync updates terminal_name when reader name changes
- TC-REC-003: Recovery Sync skips existing terminals with matching name
- TC-REC-004: Recovery Sync blocked when Recovery Mode is disabled

## Technical / Edge Cases

- TC-EDGE-001: Currency with 0 minor units -> amount conversion uses minor_unit=0
- TC-EDGE-002: disable_rounded_total affects amount sent to SumUp
- TC-EDGE-003: SumUp API returns unknown status -> treated as UNKNOWN, no final update
- TC-EDGE-004: SumUp SDK validation error on transaction parsing -> raw response fallback path used
- TC-EDGE-005: SumUp API 404 on transaction lookup -> treated as PENDING
