# Report Schema

`scripts/organize_orders.py` emits analysis JSON with this shape:

```json
{
  "title": "Amazon Purchase Organizer",
  "generated_at": "2026-06-03T12:00:00",
  "language": "zh",
  "labels": {
    "report_title": "Amazon 购买整理报告",
    "amount_top": "金额 Top"
  },
  "sources": ["/path/orders.csv"],
  "summary": {
    "overview": "one-sentence insight",
    "order_count": 12,
    "item_count": 18,
    "date_range": "2026-01-01 至 2026-06-01",
    "total_spend": "AUD 123.45",
    "notes": ["internal data coverage note"],
    "long_term": ["preservation rule"]
  },
  "top_purchases": [
    {
      "title": "full product title from source",
      "display_title": "shortened title for Amount Top visuals",
      "category_key": "Office",
      "category": "办公",
      "product_image": "data:image/svg+xml;base64,...",
      "product_image_source": "generated",
      "product_image_alt": "Notebook 商品图片",
      "amount": "AUD 42.00"
    }
  ],
  "monthly_totals": [
    {
      "month": "2026-06",
      "amount": "AUD 42.00",
      "order_count": 2,
      "item_count": 3
    }
  ],
  "category_totals": [
    {
      "category_key": "Office",
      "category": "办公",
      "amount": "AUD 42.00"
    }
  ],
  "prime_value": {
    "year": 2026,
    "basis": "shipping_savings",
    "basis_display": "运费节省字段",
    "non_member_shipping_basis": "shipping_savings",
    "membership_plan": "monthly",
    "membership_plan_source": "detected_order_records",
    "membership_paid_months": 2,
    "annual_membership_cost": "AUD 79.00",
    "monthly_membership_cost": "AUD 9.99",
    "monthly_annualized_cost": "AUD 119.88",
    "annual_plan_difference": "AUD 40.88",
    "annual_plan_verdict": "年费可省 AUD 40.88",
    "membership_cost": "AUD 79.00",
    "hypothetical_non_member_shipping": "AUD 42.00",
    "non_member_shipping_per_order_assumption": "",
    "shipping_savings_identified": "AUD 42.00",
    "shipping_paid_identified": "AUD 0.00",
    "orders_with_hypothetical_shipping": 6,
    "orders_with_shipping_savings": 6,
    "orders_with_shipping_paid": 0,
    "net_value": "AUD -37.00",
    "status": "not_yet_recovered",
    "visual": {
      "tone": "red",
      "emoji": "😭",
      "label": "未值回会员费"
    },
    "verdict": "one-sentence judgment"
  },
  "image_prompt": "prompt to use with GPT-image2/image generation",
  "orders": []
}
```

Prime value comparison:

- Main comparison is `hypothetical_non_member_shipping - membership_cost`.
- `non_member_shipping_basis` is `non_member_shipping`, `shipping_savings`, `estimated_per_order`, or `none`.
- `shipping_paid_identified` is context only and is not treated as hypothetical non-member shipping.

Prime value status:

- `recovered`: hypothetical non-member shipping exceeds membership cost.
- `not_yet_recovered`: hypothetical non-member shipping is below membership cost.
- `insufficient_hypothetical_data`: no non-member shipping assumption or usable avoided-shipping evidence was recognized.
- `membership_plan`: `monthly` or `annual`, auto-detected from Prime membership charge rows when available.
- `annual_plan_verdict`: populated for monthly plans to show whether annual billing would save money or cost more.

Prime value visual:

- `recovered`: `visual.tone = green`, `visual.emoji = 👍`.
- Any other status: `visual.tone = red`, `visual.emoji = 😭`.

Localization:

- `category_key` is the stable internal English category key.
- `category` is the user-visible localized category label.
- `product_image` is a provided image URL/path/data URI when available, otherwise a generated local thumbnail data URI.
- `product_image_source` is `provided` or `generated`.
- `product_image_alt` is localized for the report language.
- `date_range` uses `至` for Chinese and `to` for English.
- All visible labels in HTML, PNG, and GPT-image2 prompt text should follow `language`.
