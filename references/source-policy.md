# Source Policy

Use sources in this order:

1. User-provided Amazon order CSV, Excel-exported CSV, invoice PDF paths, or local receipt files.
2. Amazon Business reports or API data when the user has a Business account and the required Analytics/API permissions.
3. Already logged-in browser pages for read-only inspection after the user completes login and MFA manually.

For product photos, read-only Amazon search pages and `m.media-amazon.com` image CDN URLs are acceptable when the user asks for Amazon original product images. Use the Amazon marketplace that matches the purchase/account region: for example United States `amazon.com`, Japan `amazon.co.jp`, United Kingdom `amazon.co.uk`, Germany `amazon.de`, and Australia `amazon.com.au`. Preserve ASIN, source page, matched title, and match score in the enriched CSV. Do not mix in non-Amazon retailer images when the user specifically asks for Amazon images.

Do not store passwords, cookies, MFA codes, payment details, card numbers, addresses, or session tokens in the skill.

Do not automate checkout, returns, refunds, cancellations, payment changes, address changes, gift-card redemption, or account security settings. Stop at a prepared report or draft instructions and ask the user to complete any sensitive account action manually.

If the source is a browser page rather than an export, preserve what was actually visible: page title, date/time, URL when safe, and the fields read. If the data cannot be verified, label it as partial instead of filling gaps from assumptions.
