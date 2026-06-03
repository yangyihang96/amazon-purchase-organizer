---
name: amazon-purchase-organizer
description: Use when the user wants to organize Amazon purchase history, Amazon orders, invoices, receipts, order CSV exports, Amazon Business reports, purchased items, warranty/tax/reimbursement evidence, shipping costs, Prime membership value, or a GPT-image2-style image report for Amazon purchases.
---

# Amazon Purchase Organizer

Create a read-only Amazon purchase summary and local HTML report from user-provided order data. The report should feel like `storage-analyzer`: overview cards, monthly ordering, Top lists, and a Prime shipping-value judgment. PNG and GPT-image2 assets are optional secondary outputs.

## Hard Boundaries

- Do not save or request Amazon passwords, MFA codes, cookies, session tokens, card details, addresses, or gift-card codes.
- Do not automate checkout, returns, refunds, cancellations, gift-card redemption, payment changes, address changes, or account security settings.
- If Amazon login is needed, open the page and let the user complete login/MFA manually. Continue only after the user confirms the page is logged in.
- Prefer exported files and local evidence over browser scraping. If browser reading is necessary, keep it read-only and label unverified fields as partial.
- Preserve original file paths and row numbers so every report item can be traced back to the source.
- Do not create Excel files unless the user explicitly asks for Excel.

## Source Order

1. User-provided Amazon order CSV, invoice PDFs, screenshots, or local receipt folders.
2. Amazon Business reports/API data when the user has the required Analytics/API permissions.
3. Already logged-in Amazon pages for read-only inspection.

Read [references/source-policy.md](references/source-policy.md) before using a browser or discussing Amazon Business API access.

## Workflow

### Step 1 Gather Inputs

Ask for or locate order data. Good inputs include:

- Amazon order history CSV or Amazon Business report CSV.
- A folder containing invoice PDFs plus a CSV that references them.
- Existing local exports from prior runs.

For personal Amazon accounts, do not promise a stable official CSV export unless the user already has one. If no export exists, guide the user to manually download invoices/order details or use an already logged-in browser session for visible read-only fields.

### Step 2 Normalize, Analyze, and Output Image Assets

Run the organizer script from the skill directory:

```bash
python3 scripts/organize_orders.py /path/to/orders.csv \
  --json ~/Desktop/amazon-purchase-analysis.json \
  --html ~/Desktop/amazon-purchase-report.html \
  --png ~/Desktop/amazon-purchase-report.png \
  --image-prompt ~/Desktop/amazon-purchase-image-prompt.txt \
  --currency AUD \
  --year 2026 \
  --prime-cost 79 \
  --prime-plan auto \
  --prime-annual-cost 79 \
  --prime-monthly-cost 9.99 \
  --language zh \
  --non-member-shipping-per-order 9.99
```

The script accepts one or more CSV files. It maps common Amazon-style headers into:

- `order_date`, `order_id`, `title`, `quantity`, `amount`, `currency`
- `shipping_paid`, `shipping_savings`, `non_member_shipping`, `asin`, `seller`, `status`, `invoice_path`, `image`, `image_url`, `product_photo`, `thumbnail`, `source_file`, `source_line`

It infers categories and preserves visible order status, but does not grade orders. If an order row has a product image URL/path/data URI, show it in Amount Top and order details. If no image is available, generate a local product-style thumbnail so the visual report still has product imagery.

When the user asks for real product photos, Amazon original images, 商品图, 真实照片, 原图, or similar:

- Prefer Amazon image enrichment before report generation instead of using generated thumbnails.
- Use `--fetch-amazon-images` so the script performs read-only Amazon marketplace search, downloads `m.media-amazon.com` product images, and writes an enriched CSV.
- Pass `--amazon-enriched-csv` and `--amazon-image-dir` to keep the derived file and downloaded photos traceable.
- Preserve the enriched columns: `Product Image URL`, `Amazon ASIN`, `Amazon Image Source Page`, `Amazon Image Match Title`, `Amazon Image Match Score`.
- If the user specifically asks for Amazon images, do not substitute other retailers' photos. Low score matches can be included only with a clear caveat or left for manual review.

Example with Amazon AU original product photos:

```bash
python3 scripts/organize_orders.py /path/to/orders.csv \
  --fetch-amazon-images \
  --amazon-enriched-csv /path/to/orders_with_amazon_photos.csv \
  --amazon-image-dir /path/to/amazon_photos_amazon \
  --json ~/Desktop/amazon-purchase-analysis.json \
  --html ~/Desktop/amazon-purchase-report.html \
  --png ~/Desktop/amazon-purchase-report.png \
  --image-prompt ~/Desktop/amazon-purchase-image-prompt.txt \
  --currency AUD \
  --year 2026 \
  --language zh \
  --prime-plan auto \
  --prime-cost 79 \
  --prime-annual-cost 79 \
  --prime-monthly-cost 9.99 \
  --non-member-shipping-per-order 9.99
```

Prime value logic:

- Compare the Prime membership cost against the hypothetical shipping total the user would have paid without membership for the same purchased orders.
- Prefer explicit `non_member_shipping` / `without prime shipping` fields when available.
- If explicit non-member shipping is missing, `shipping_savings` / `shipping discount` / `Prime savings` can be used as avoided-shipping evidence.
- If neither field exists, use `--non-member-shipping-per-order` only as a clearly labeled assumption. Cancelled AUD 0.00 orders are excluded from this per-order assumption.
- Track `shipping_paid` separately. Paid shipping is useful context but does not prove membership value.
- Default Amazon Australia Prime comparison is AU$79/year; override with `--prime-cost` when the user's real plan differs. See [references/prime-pricing.md](references/prime-pricing.md).
- Auto-detect monthly vs annual membership from Prime membership charge rows when present. If browsing the account page read-only reveals the user's plan, pass it as `--prime-plan monthly` or `--prime-plan annual`.
- If monthly membership is detected, include the full-year monthly cost vs annual plan difference: whether annual billing would save money or cost more.
- Set `--language zh` or `--language en` from the user's current operating/conversation language. All visible report text must follow this language, including headings, category names, date-range connectors, Prime verdict, and image-prompt text blocks.
- Prime visual status is binary: recovered membership value uses green + 👍; not recovered or insufficient evidence uses red + 😭.

### Step 3 Generate the Local Web Report

Use the generated local HTML report as the primary user-facing artifact. The first screen should visually match the 3:2 PNG report image layout. It should show:

1. Total spend, order count, item count, and date range.
2. Prime value judgment: membership fee, hypothetical non-member shipping total, paid shipping, saved amount, monthly-vs-annual comparison when relevant, and green 👍 / red 😭 status.
3. Monthly totals sorted from newest to oldest.
4. Amount Top purchases with product photos or generated thumbnails, shortened display names, amounts, and categories.
5. Evidence and safety note.

The script still writes `amazon-purchase-report.png` and `amazon-purchase-image-prompt.txt`. The PNG must use the same composition as the HTML report. Use the PNG when the user needs a static share image. Use the prompt with GPT-image2 / the built-in image generation tool only when the user wants an AI-styled infographic.

For better financial accuracy, prefer this two-stage image flow:

1. Use GPT-image2 to create a no-text dashboard background from the prompt direction.
2. Render exact numbers over that background:

```bash
python3 scripts/build_image_report.py ~/Desktop/amazon-purchase-analysis.json ~/Desktop/amazon-purchase-report.png /path/to/gpt-image2-background.png
```

If no GPT-image2 background is available, `organize_orders.py` still creates a clean exact PNG locally.

Open the local HTML report for the user when appropriate:

```bash
open ~/Desktop/amazon-purchase-report.html
```

### Step 4 Explain the Result

In the conversation, give a short conclusion-first summary:

- Total recognized spend and record count.
- Prime value conclusion and shipping-data caveat.
- Whether product photos came from provided files, Amazon original image enrichment, or generated thumbnails. Mention any low-confidence Amazon image matches that need manual review.
- The first 2-3 useful follow-up checks, especially missing shipping-savings evidence.
- The local HTML report path and, if generated, the PNG report path.

Do not paste the whole report into chat.

## References

- [references/source-policy.md](references/source-policy.md): safe source and account-action boundaries.
- [references/report-schema.md](references/report-schema.md): analysis JSON shape used by the HTML template.
- [references/image-report.md](references/image-report.md): GPT-image2 and exact PNG image workflow.
- [references/prime-pricing.md](references/prime-pricing.md): Prime membership benchmark and override rules.
