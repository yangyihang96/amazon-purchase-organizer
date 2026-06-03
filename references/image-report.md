# Local Web and Image Report Workflow

Default output is a local HTML information report, not Excel. PNG and GPT-image2 assets are secondary outputs.

Use this sequence:

1. Run `scripts/organize_orders.py` to produce:
   - `amazon-purchase-analysis.json`
   - `amazon-purchase-report.html`
   - `amazon-purchase-report.png`
   - `amazon-purchase-image-prompt.txt`
2. Open `amazon-purchase-report.html` locally. Its first screen should mirror the 3:2 PNG report: centered title, icon metric cards, Prime value card, monthly ranking bars, Amount Top with product photos or generated thumbnails, category totals, and safety footer.
3. For a GPT-image2-styled version, use `amazon-purchase-image-prompt.txt` with the built-in image generation tool.
   The prompt should include monthly totals sorted from newest to oldest.
   All visible report labels, category names, date connectors, Prime verdict text, and prompt text blocks should match the user's operating language (`--language zh` or `--language en`).
   Amount Top should show product photos when supplied, or generated local thumbnails when source data lacks product images.
   Prime value should show the hypothetical non-member shipping total, not paid shipping as the payback basis.
   If a monthly membership plan is detected, include the annual-plan savings or extra-cost comparison.
   Prime value visual should be green with 👍 when recovered, otherwise red with 😭.
4. If generated text accuracy matters, generate a no-text background with GPT-image2 and then run:

```bash
python3 scripts/build_image_report.py amazon-purchase-analysis.json amazon-purchase-report.png gpt-image2-background.png
```

This keeps the final visual AI-generated while preserving exact totals, dates, and Prime value numbers through deterministic text overlay.

Do not create Excel files unless the user explicitly asks for Excel.
