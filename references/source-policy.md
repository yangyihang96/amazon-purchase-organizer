# Source Policy

Use sources in this order:

1. User-provided Amazon order CSV, Excel-exported CSV, invoice PDF paths, or local receipt files.
2. Amazon Business reports or API data when the user has a Business account and the required Analytics/API permissions.
3. Already logged-in browser pages for read-only inspection after the user completes login and MFA manually.

Do not store passwords, cookies, MFA codes, payment details, card numbers, addresses, or session tokens in the skill.

Do not automate checkout, returns, refunds, cancellations, payment changes, address changes, gift-card redemption, or account security settings. Stop at a prepared report or draft instructions and ask the user to complete any sensitive account action manually.

If the source is a browser page rather than an export, preserve what was actually visible: page title, date/time, URL when safe, and the fields read. If the data cannot be verified, label it as partial instead of filling gaps from assumptions.
