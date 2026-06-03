# Amazon Purchase Organizer / Amazon 购买整理报告生成器

中文：一个只读的 Amazon 购买记录整理 skill。它从用户提供的订单 CSV 生成本地网页报告、精确 PNG 报告和 GPT-image2 图片提示词，重点展示总花费、月度排序、金额 Top、类别 Top、商品图片，以及 Prime 会员是否值回会员费。

English: A read-only Amazon purchase organizer skill. It turns user-provided Amazon order CSV files into a local web report, an exact PNG report, and a GPT-image2 prompt, with total spend, monthly ranking, Amount Top, category totals, product images, and a Prime membership value check.

## What It Does / 功能

- 中文：生成类似 `storage-analyzer report` 的本地网页和图片报告。
- English: Generates a local web and image report in a `storage-analyzer report` style.
- 中文：按月份倒序整理购买金额、订单数和物品数。
- English: Sorts monthly spend, orders, and items from newest to oldest.
- 中文：展示金额 Top 商品，并支持商品图片 URL、本地图片路径或自动生成缩略图。
- English: Shows Amount Top items with product image URLs, local image paths, or generated thumbnails.
- 中文：用假设“没有 Prime 会支付的运费总和”对比会员费，判断是否值回。
- English: Compares Prime membership cost against hypothetical non-member shipping for the same orders.
- 中文：自动识别年付/月付 Prime 会员记录；月付时显示改成年付会省或多花多少。
- English: Detects annual/monthly Prime membership rows; monthly plans show whether annual billing would save or cost more.
- 中文：可根据用户操作语言输出中文或英文表头、类别、结论和图片提示词。
- English: Localizes labels, categories, conclusions, and image prompts in Chinese or English.

## Safety / 安全边界

中文：本项目只处理用户主动提供的订单文件。不要提交真实订单 CSV、发票、截图、地址、支付信息或生成出的私人报告到公开仓库。登录 Amazon、MFA、付款、退货、取消订单、改地址、改账户安全设置都必须人工完成。

English: This project only processes order files that the user provides. Do not commit real order CSVs, invoices, screenshots, addresses, payment details, or private generated reports to a public repository. Amazon login, MFA, payment, returns, cancellations, address changes, and account security changes must remain manual.

## Install / 安装

```bash
python3 -m pip install -r requirements.txt
```

To install as a Codex skill, copy this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R amazon-purchase-organizer ~/.codex/skills/
```

中文：如果你已经在 Codex skill 目录里开发，可以直接保留这个目录结构使用。

English: If you are developing directly inside the Codex skills directory, keep this folder structure as-is.

## CSV Input / CSV 输入

The script accepts one or more CSV files. Common headers are mapped automatically:

```csv
Order Date,Order ID,Title,Quantity,Amount,Currency,Shipping Paid,Shipping Savings,Non-Member Shipping,Product Image URL,Status
2026-01-17,111-0000000-0000001,LEGO Art Hokusai The Great Wave Building Set,1,155.20,AUD,0.00,9.99,9.99,https://example.com/lego.jpg,Delivered
```

中文：字段名可以不完全一样，脚本会识别常见 Amazon 风格表头，例如 `order date`、`item total`、`shipping savings`、`without prime shipping`、`product image url`。

English: Header names do not need to match exactly. The script recognizes common Amazon-style headers such as `order date`, `item total`, `shipping savings`, `without prime shipping`, and `product image url`.

## Quick Start / 快速开始

Run the included synthetic sample:

```bash
mkdir -p examples/output
python3 scripts/organize_orders.py examples/sample_orders.csv \
  --json examples/output/amazon-purchase-analysis-sample.json \
  --html examples/output/amazon-purchase-report-sample.html \
  --png examples/output/amazon-purchase-report-sample.png \
  --image-prompt examples/output/amazon-purchase-image-prompt-sample.txt \
  --currency AUD \
  --year 2026 \
  --language zh \
  --prime-plan auto \
  --prime-cost 79 \
  --prime-annual-cost 79 \
  --prime-monthly-cost 9.99 \
  --non-member-shipping-per-order 9.99
```

中文：打开 `examples/output/amazon-purchase-report-sample.html` 查看本地网页报告。PNG 与网页使用同一套数据和布局口径。

English: Open `examples/output/amazon-purchase-report-sample.html` to view the local web report. The PNG uses the same data and layout logic as the web report.

## GPT-image2 Workflow / GPT-image2 图片流程

中文：推荐先让 GPT-image2 生成“无文字背景图”，再用脚本叠加精确数字和文字，避免 AI 图片把金额、日期或表头写错。

English: The recommended flow is to generate a no-text background with GPT-image2, then overlay exact numbers and labels with the script so the image does not distort amounts, dates, or headings.

```bash
python3 scripts/build_image_report.py \
  examples/output/amazon-purchase-analysis-sample.json \
  examples/output/amazon-purchase-report-sample.png \
  /path/to/gpt-image2-background.png
```

## Prime Value Logic / Prime 价值口径

中文：主判断公式是：

```text
已省下 = 假设无会员运费总和 - Prime 会员费
```

English: The main comparison is:

```text
Saved = Hypothetical non-member shipping - Prime membership cost
```

中文：如果 CSV 里有 `Non-Member Shipping` 或 `Without Prime Shipping` 字段，优先使用。没有这些字段时，使用 `Shipping Savings` 或 `Prime Shipping Savings`。再没有时，才使用 `--non-member-shipping-per-order` 作为明确标注的假设。

English: `Non-Member Shipping` or `Without Prime Shipping` fields are preferred. If absent, `Shipping Savings` or `Prime Shipping Savings` are used. If neither exists, `--non-member-shipping-per-order` is used only as a clearly labeled assumption.

## Repository Privacy / 仓库隐私

中文：`.gitignore` 已经忽略常见输出目录和私人订单文件名，但公开发布前仍应检查 `git status`，确认没有真实订单数据。

English: `.gitignore` excludes common output folders and private order filenames, but always check `git status` before publishing to make sure no real order data is included.

## Test / 测试

```bash
python3 scripts/test_organize_orders.py
```

## License / 许可证

MIT License.
