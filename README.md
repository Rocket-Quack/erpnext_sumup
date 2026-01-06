<div align="center">
  <p>
    <img src="docs/assets/SUMUP_INTEGRATION_APP_LOGO.png" alt="ERPNext SumUp Integration Logo" width="164"/>
  </p>
    <h1>SumUp ERPNext Integration <br> (WORK IN PROGRESS)</h1>
</div>

This app integrates SumUp card terminals into ERPNext and allows card payments directly in the POS.

When a card payment is selected, the amount is sent to a SumUp terminal. After a successful payment, the result is sent back to ERPNext.

> **Trademark notice:**
> SumUp is a registered trademark of SumUp Payments Limited.
> This project is not affiliated with SumUp.

## Supported Versions

| ERPNext | Frappe | Support Status |
|---------|--------|----------------|
| v16 Beta | v16 Beta | Coming soon |
| v15 | v15 | Coming soon |

## Quick Setup (POS)

1. Install the app (see installation sections below).
2. Open **SumUp Settings**:
   - Enable SumUp.
   - Enter **API Key** and **Merchant Code**.
   - Click **Test Connection** to fetch the merchant currency.
3. Pair a terminal:
   - Go to **SumUp Terminal** list.
   - Click **Pair Terminal**.
   - Enter the pairing code shown on the terminal and a name.
4. Mark a payment method for SumUp:
   - Open **POS Payment Method**.
   - Enable **Use SumUp Terminal**.
5. Assign the terminal in the POS Profile:
   - Open **POS Profile**.
   - Set **SumUp Terminal**.
   - Ensure the SumUp payment method is listed in the profile.
6. Use in POS:
   - Select the SumUp payment method.
   - Submit the POS invoice to start the payment on the terminal.

Notes:
- SumUp payments must cover the full invoice total.
- The POS invoice currency must match the SumUp merchant currency.

## Recovery Mode (Optional)

If readers already exist in your SumUp account but are missing in ERPNext:

1. Open **SumUp Settings** and enable **Recovery Mode**.
2. Go to **SumUp Terminal** list view.
3. Click **Recovery Sync** to fetch and sync terminals.

## Installation (Frappe Cloud)

The app can be installed directly via Frappe Cloud:

1. Open the Frappe Cloud dashboard at <https://frappecloud.com/dashboard/#/sites>
2. Click **"New Site"** to create a new site
3. In the step **"Select apps to install"**:
   - Choose the desired Frappe/ERPNext version
   - Enable the app **`ERPNext SumUp`**
4. Complete the wizard to create the site

## Installation (Self-Hosted)

Once ERPNext is installed, add the app to your bench environment:

```bash
bench get-app https://github.com/Rocket-Quack/erpnext_sumup.git --branch version-15
```

Install requirements:

```bash
bench setup requirements
```

Install the app on a site:

```bash
bench --site yoursite.com install-app erpnext_sumup
```

Run migrations:

```bash
bench --site yoursite.com migrate
```

## Trademark Notice

**SumUp** is a registered trademark of **SumUp Payments Limited**.

This project is an independent and unofficial integration and is not affiliated with SumUp.
It is not operated, supported, or endorsed by SumUp.

The name SumUp is used only to describe technical compatibility with the respective services.

## Third-Party

This app uses the Python package `sumup` v0.0.20 (tag v0.0.20). See `THIRD_PARTY_NOTICE.md`.

## License

Copyright (C) 2025 RocketQuackIT

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

GNU GPL V3. See the LICENSE file for more information.
