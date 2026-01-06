# Recovery Mode (SumUp Terminals)

Recovery Mode syncs SumUp readers into local `SumUp Terminal` records. It is useful when terminals already exist in the SumUp merchant account but are missing in ERPNext.

## Prerequisites

- SumUp Settings are enabled and configured with API Key and Merchant Code.
- You have permission to access **SumUp Settings** and **SumUp Terminal**.

## Enable Recovery Mode

1. Open **SumUp Settings**.
2. Enable **Recovery Mode**.
3. Save.

## Run the Recovery Sync

1. Go to **SumUp Terminal** list view.
2. Click **Recovery Sync**.
3. Confirm the dialog.

The sync will:

- Fetch all readers from SumUp for the configured merchant.
- Create missing terminals (enabled by default).
- Update existing terminals when the reader name changes.
- Match records by `terminal_id` (SumUp reader ID).

## What It Does Not Do

- It does not delete local terminals that are missing in SumUp.
- It does not change connection/online/activity status fields.
- It does not disable existing terminals.

## Output

After completion, a message shows how many terminals were created, updated, skipped, or failed.
