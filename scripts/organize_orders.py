#!/usr/bin/env python3
"""Normalize Amazon order exports and build a storage-analyzer-style report."""

from __future__ import annotations

import argparse
import base64
import csv
import html as html_module
import json
import mimetypes
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

import build_report
import build_image_report


FIELD_ALIASES = {
    "order_date": ["order date", "purchase date", "date", "ordered on", "order placed"],
    "order_id": ["order id", "order number", "amazon order id", "order"],
    "title": ["title", "item title", "item name", "product name", "description", "name"],
    "quantity": ["quantity", "qty", "item quantity", "units"],
    "amount": [
        "item total",
        "item subtotal",
        "total charged",
        "order total",
        "total",
        "price",
        "amount",
        "net total",
    ],
    "asin": ["asin", "asin/isbn", "isbn", "sku"],
    "seller": ["seller", "seller name", "supplier", "vendor"],
    "status": ["order status", "status", "shipment status", "delivery status"],
    "invoice_path": ["invoice path", "invoice", "receipt path", "pdf path", "source invoice"],
    "image": [
        "image",
        "image url",
        "image_url",
        "product image",
        "product image url",
        "product photo",
        "photo",
        "photo url",
        "thumbnail",
        "thumbnail url",
        "thumbnail path",
        "image path",
        "picture",
    ],
    "shipping_paid": [
        "shipping charge",
        "shipping",
        "shipping cost",
        "shipping paid",
        "shipping and handling",
        "shipping handling",
        "delivery fee",
        "delivery charge",
        "postage",
    ],
    "shipping_savings": [
        "shipping savings",
        "shipping saving",
        "shipping discount",
        "delivery savings",
        "delivery discount",
        "prime savings",
        "prime shipping savings",
        "promotion applied to shipping",
    ],
    "non_member_shipping": [
        "non member shipping",
        "non-member shipping",
        "non prime shipping",
        "non-prime shipping",
        "without prime shipping",
        "shipping without prime",
        "estimated non member shipping",
        "estimated non-member shipping",
        "estimated shipping without prime",
        "shipping if no prime",
        "non member delivery fee",
        "non-prime delivery fee",
        "standard delivery estimate",
    ],
}

CATEGORY_KEYWORDS = [
    ("Gift Cards & Digital", ["gift card", "giftcard", "digital", "kindle", "audible", "subscription"]),
    ("Hobbies & Toys", ["lego", "puzzle", "model kit", "craft", "hobby", "toy", "game", "art set"]),
    ("Personal Care", ["condom", "durex", "cotton bud", "applicator", "outer ears", "make-up", "makeup", "toothbrush", "soap"]),
    ("Health & Fitness", ["bcaa", "amino", "protein", "workout", "scivation", "xtend", "vitamin", "supplement", "mask", "first aid", "bandage", "nexcare", "steri-strip", "skin closure", "immune"]),
    ("Office", ["notebook", "paper", "pen", "pencil", "desk", "chair", "folder", "label", "printer", "ink", "stationery"]),
    ("Electronics", ["usb", "cable", "charger", "adapter", "laptop", "phone", "monitor", "keyboard", "mouse", "ssd", "drive", "battery", "camera"]),
    ("Household Essentials", ["tissue", "quilton", "toilet paper", "paper towel", "cleaning wipe", "detergent"]),
    ("Home", ["kitchen", "lamp", "light", "bedding", "towel", "vacuum", "cleaner", "storage", "shelf", "mattress"]),
    ("Tools", ["tool", "drill", "screw", "wrench", "meter", "bit", "tape measure", "glue"]),
    ("Books", ["book", "paperback", "hardcover", "textbook"]),
    ("Grocery", ["coffee", "tea", "snack", "food", "rice", "water", "milk", "sauce"]),
    ("Clothing", ["shirt", "shoe", "sock", "jacket", "pants", "dress", "hat", "glove"]),
    ("Automotive", ["car", "auto", "tyre", "tire", "wiper", "engine", "motor oil"]),
    ("Pet", ["dog", "cat", "pet", "litter", "leash"]),
]

CATEGORY_LABELS = {
    "zh": {
        "Gift Cards & Digital": "礼品卡与数字内容",
        "Hobbies & Toys": "兴趣玩具",
        "Personal Care": "个人护理",
        "Health & Fitness": "健康健身",
        "Office": "办公",
        "Electronics": "电子产品",
        "Household Essentials": "日用品",
        "Home": "家居",
        "Tools": "工具",
        "Books": "图书",
        "Grocery": "食品杂货",
        "Clothing": "服饰",
        "Automotive": "汽车用品",
        "Pet": "宠物",
        "General Purchases": "其他消费",
    },
    "en": {
        "Gift Cards & Digital": "Gift Cards & Digital",
        "Hobbies & Toys": "Hobbies & Toys",
        "Personal Care": "Personal Care",
        "Health & Fitness": "Health & Fitness",
        "Office": "Office",
        "Electronics": "Electronics",
        "Household Essentials": "Household Essentials",
        "Home": "Home",
        "Tools": "Tools",
        "Books": "Books",
        "Grocery": "Grocery",
        "Clothing": "Clothing",
        "Automotive": "Automotive",
        "Pet": "Pet",
        "General Purchases": "General Purchases",
    },
}

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"]

AMAZON_AU_BASE_URL = "https://www.amazon.com.au"
AMAZON_IMAGE_COLUMNS = [
    "Product Image URL",
    "Amazon ASIN",
    "Amazon Image Source Page",
    "Amazon Image Match Title",
    "Amazon Image Match Score",
]
AMAZON_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-AU,en;q=0.9",
}
AMAZON_IMAGE_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "for",
    "with",
    "of",
    "to",
    "in",
    "on",
    "by",
    "from",
    "made",
    "pack",
    "packs",
    "count",
    "fit",
    "inch",
    "inches",
    "kg",
    "mg",
    "gram",
    "grams",
}

LABELS = {
    "zh": {
        "report_title": "Amazon 购买整理报告",
        "generated_at": "生成时间",
        "sources": "来源",
        "files": "个文件",
        "read_only_badge": "只读整理 · 不登录 · 不付款 · 不退货",
        "total_spend": "总花费",
        "order_count": "订单数",
        "item_count": "物品数",
        "date_range": "日期范围",
        "core_metrics": "核心指标",
        "prime_value": "Prime 价值判断",
        "year": "年份",
        "membership_cost": "会员费",
        "membership_plan": "会员方案",
        "annual_plan_comparison": "年费对比",
        "shipping_savings": "已识别免运费节省",
        "hypothetical_shipping": "假设无会员运费",
        "shipping_paid": "运费",
        "net_value": "已省下",
        "basis": "口径",
        "orders_with_shipping_savings": "有节省记录订单",
        "orders_with_hypothetical_shipping": "有假设运费订单",
        "orders_with_shipping_paid": "有已付运费订单",
        "amount_top": "金额 Top",
        "amount_top5": "金额 Top5",
        "monthly_ranking": "月度排序",
        "category_top": "类别 Top",
        "category_amount_top": "类别金额 Top",
        "order_details": "订单明细",
        "long_term_rules": "长期整理规则",
        "date": "日期",
        "item": "物品",
        "amount": "金额",
        "category": "类别",
        "month": "月份",
        "orders": "订单",
        "items": "物品",
        "status": "状态",
        "shipping_paid_short": "已付运费",
        "shipping_savings_short": "免运费节省",
        "no_monthly_data": "暂无月度数据",
        "no_category_data": "暂无类别数据",
        "no_amount_data": "暂无金额数据",
        "no_orders_data": "暂无订单数据",
        "untitled": "未命名",
        "unrecognized": "未识别",
        "unknown_month": "未识别月份",
        "uncategorized": "其他消费",
        "safety_footer": "只读整理 · 不登录 · 不付款 · 不退货 · 原始 CSV/PDF 仍是追溯依据",
        "html_footer": "amazon-purchase-organizer · 原始订单文件优先 · 敏感账户动作必须人工确认",
    },
    "en": {
        "report_title": "Amazon Purchase Report",
        "generated_at": "Generated",
        "sources": "Sources",
        "files": "files",
        "read_only_badge": "Read-only · No login · No payment · No returns",
        "total_spend": "Total Spend",
        "order_count": "Orders",
        "item_count": "Items",
        "date_range": "Date Range",
        "core_metrics": "Core Metrics",
        "prime_value": "Prime Value",
        "year": "Year",
        "membership_cost": "Membership Cost",
        "membership_plan": "Membership Plan",
        "annual_plan_comparison": "Annual Plan Comparison",
        "shipping_savings": "Shipping Savings Found",
        "hypothetical_shipping": "Hypothetical Non-Member Shipping",
        "shipping_paid": "Shipping",
        "net_value": "Saved",
        "basis": "Basis",
        "orders_with_shipping_savings": "Orders With Savings",
        "orders_with_hypothetical_shipping": "Orders With Hypothetical Shipping",
        "orders_with_shipping_paid": "Orders With Paid Shipping",
        "amount_top": "Amount Top",
        "amount_top5": "Amount Top 5",
        "monthly_ranking": "Monthly Ranking",
        "category_top": "Category Top",
        "category_amount_top": "Category Amount Top",
        "order_details": "Order Details",
        "long_term_rules": "Long-Term Rules",
        "date": "Date",
        "item": "Item",
        "amount": "Amount",
        "category": "Category",
        "month": "Month",
        "orders": "Orders",
        "items": "Items",
        "status": "Status",
        "shipping_paid_short": "Paid Shipping",
        "shipping_savings_short": "Shipping Savings",
        "no_monthly_data": "No monthly data",
        "no_category_data": "No category data",
        "no_amount_data": "No amount data",
        "no_orders_data": "No order data",
        "untitled": "Untitled",
        "unrecognized": "Unrecognized",
        "unknown_month": "Unknown month",
        "uncategorized": "General Purchases",
        "safety_footer": "Read-only · No login · No payment · No returns · Original CSV/PDF remains the source of truth",
        "html_footer": "amazon-purchase-organizer · Original order files first · Sensitive account actions require manual confirmation",
    },
}


def resolve_language(language: str | None = "auto") -> str:
    raw = (language or "auto").strip().lower().replace("_", "-")
    if raw in {"zh", "zh-cn", "zh-hans", "cn", "chinese", "中文"}:
        return "zh"
    if raw in {"en", "en-us", "en-au", "en-gb", "english"}:
        return "en"
    env_language = os.environ.get("AMAZON_REPORT_LANGUAGE", "")
    if raw == "auto" and env_language:
        return resolve_language(env_language)
    if raw == "auto":
        for key in ["LC_ALL", "LC_MESSAGES", "LANG"]:
            locale = os.environ.get(key, "").strip().lower().replace("_", "-")
            if locale.startswith("zh"):
                return "zh"
            if locale.startswith("en"):
                return "en"
    return "zh"


def report_labels(language: str | None) -> dict:
    resolved = resolve_language(language)
    labels = dict(LABELS["zh"])
    labels.update(LABELS.get(resolved, {}))
    return labels


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def normalize_row(row: dict) -> dict:
    return {normalize_header(k): (v or "").strip() for k, v in row.items()}


def pick(row: dict, field: str) -> str:
    for alias in FIELD_ALIASES[field]:
        value = row.get(normalize_header(alias), "")
        if value:
            return value
    return ""


def parse_quantity(value: str) -> int:
    if not value:
        return 1
    match = re.search(r"-?\d+", value.replace(",", ""))
    if not match:
        return 1
    return max(1, int(match.group(0)))


def parse_money(value: str, default_currency: str = "AUD") -> tuple[Decimal | None, str]:
    raw = (value or "").strip()
    if not raw:
        return None, default_currency
    currency = default_currency
    upper = raw.upper()
    if "AUD" in upper or "A$" in upper or "AU$" in upper:
        currency = "AUD"
    elif "USD" in upper or "US$" in upper:
        currency = "USD"
    elif "GBP" in upper or "£" in raw:
        currency = "GBP"
    elif "EUR" in upper or "€" in raw:
        currency = "EUR"
    negative = "(" in raw and ")" in raw
    cleaned = re.sub(r"[^0-9.\-]", "", raw.replace(",", ""))
    if cleaned in {"", "-", "."}:
        return None, currency
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None, currency
    if negative:
        amount = -amount
    return amount, currency


def canonical_date(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return raw


def date_sort_key(value: str) -> str:
    canon = canonical_date(value)
    return canon if re.match(r"^\d{4}-\d{2}-\d{2}$", canon) else "9999-12-31"


def format_date_range(dates: list[str], language: str) -> str:
    labels = report_labels(language)
    if not dates:
        return labels["unrecognized"]
    connector = " to " if language == "en" else " 至 "
    return f"{min(dates)}{connector}{max(dates)}"


def infer_category(title: str) -> str:
    lower = (title or "").lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword_matches(lower, keyword) for keyword in keywords):
            return category
    return "General Purchases"


def localized_category(category_key: str, language: str) -> str:
    resolved = resolve_language(language)
    labels = CATEGORY_LABELS.get(resolved, CATEGORY_LABELS["zh"])
    return labels.get(category_key, report_labels(resolved)["uncategorized"])


def localized_basis(basis: str, language: str) -> str:
    if language == "en":
        return {
            "non_member_shipping": "Non-member shipping field",
            "shipping_savings": "Shipping savings field",
            "estimated_per_order": "Per-order shipping assumption",
            "none": "No usable non-member shipping evidence",
        }.get(basis, basis or "No usable non-member shipping evidence")
    return {
        "non_member_shipping": "无会员运费字段",
        "shipping_savings": "运费节省字段",
        "estimated_per_order": "每单运费假设",
        "none": "无可用无会员运费证据",
    }.get(basis, basis or "无可用无会员运费证据")


def normalize_product_image(raw: str, source_path: str, title: str, category_key: str, language: str) -> dict:
    value = (raw or "").strip()
    if value:
        if value.startswith("data:") or re.match(r"^https?://", value, re.IGNORECASE):
            return {
                "product_image": value,
                "product_image_source": "provided",
                "product_image_alt": product_image_alt(title, language),
            }
        candidate = value if os.path.isabs(value) else os.path.join(os.path.dirname(os.path.abspath(source_path)), value)
        if os.path.exists(candidate):
            return {
                "product_image": file_to_data_uri(candidate),
                "product_image_source": "provided",
                "product_image_path": os.path.abspath(candidate),
                "product_image_alt": product_image_alt(title, language),
            }
        return {
            "product_image": value,
            "product_image_source": "provided",
            "product_image_alt": product_image_alt(title, language),
        }
    return {
        "product_image": generated_product_thumbnail(title, category_key, language),
        "product_image_source": "generated",
        "product_image_alt": product_image_alt(title, language),
    }


def file_to_data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def product_image_alt(title: str, language: str) -> str:
    name = shorten_title(title, max_chars=38, language=language)
    return f"{name} product photo" if language == "en" else f"{name} 商品图片"


def generated_product_thumbnail(title: str, category_key: str, language: str) -> str:
    label = thumbnail_label(title, category_key)
    shape = thumbnail_shape(category_key)
    safe_label = html_module.escape(label)
    bg = {
        "Health & Fitness": "#eef5f1",
        "Hobbies & Toys": "#eef4ff",
        "Office": "#eef3ff",
        "Home": "#f2f5f7",
        "Personal Care": "#f7f0f6",
        "Pet": "#f0f5ed",
        "Household Essentials": "#f2f4f8",
    }.get(category_key, "#eef3ff")
    accent = {
        "Health & Fitness": "#9ca3af",
        "Hobbies & Toys": "#1d5ecb",
        "Office": "#1d5ecb",
        "Home": "#2d65b3",
        "Personal Care": "#b64b7a",
        "Pet": "#16794c",
        "Household Essentials": "#687786",
    }.get(category_key, "#1d5ecb")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="128" viewBox="0 0 160 128">
<rect width="160" height="128" rx="18" fill="{bg}"/>
{shape}
<text x="80" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="{accent}">{safe_label}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def thumbnail_label(title: str, category_key: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    if words:
        return " ".join(words[:2]).upper()[:18]
    return category_key.split("&", 1)[0].strip().upper()[:18] or "ITEM"


def thumbnail_shape(category_key: str) -> str:
    if category_key == "Health & Fitness":
        return """<ellipse cx="80" cy="27" rx="31" ry="9" fill="#d1d5db"/>
<rect x="49" y="27" width="62" height="70" rx="13" fill="#f8fafc" stroke="#9ca3af" stroke-width="3"/>
<rect x="55" y="50" width="50" height="30" rx="5" fill="#111827"/>
<text x="80" y="70" text-anchor="middle" font-family="Arial" font-size="13" font-weight="800" fill="#f8fafc">XTEND</text>"""
    if category_key == "Hobbies & Toys":
        return """<rect x="34" y="25" width="92" height="67" rx="6" fill="#111827"/>
<rect x="42" y="32" width="76" height="50" fill="#f8fafc"/>
<path d="M48 68 C62 45,78 85,94 52 S113 70,119 48" fill="none" stroke="#1d5ecb" stroke-width="5"/>
<rect x="39" y="86" width="86" height="10" fill="#1f2937"/>"""
    if category_key == "Office":
        return """<rect x="38" y="34" width="84" height="48" rx="7" fill="#1d5ecb"/>
<rect x="47" y="43" width="66" height="30" rx="3" fill="#eaf2ff"/>
<path d="M72 84 H88 L94 99 H66 Z" fill="#1d5ecb"/>"""
    if category_key == "Home":
        return """<path d="M40 42 H120 L108 92 H52 Z" fill="#dbeafe" stroke="#2d65b3" stroke-width="4"/>
<path d="M49 58 H111 M45 75 H115" stroke="#2d65b3" stroke-width="5" stroke-linecap="round"/>
<path d="M59 42 V94 M80 42 V96 M101 42 V94" stroke="#2d65b3" stroke-width="4"/>"""
    if category_key == "Personal Care":
        return """<rect x="48" y="31" width="64" height="75" rx="12" fill="#fff7ed" stroke="#b64b7a" stroke-width="4"/>
<path d="M58 54 H102 M58 76 H102" stroke="#b64b7a" stroke-width="5" stroke-linecap="round"/>
<circle cx="80" cy="38" r="8" fill="#b64b7a"/>"""
    if category_key == "Pet":
        return """<rect x="38" y="40" width="84" height="58" rx="12" fill="#dcfce7" stroke="#16794c" stroke-width="4"/>
<path d="M55 70 C64 53,72 53,80 70 C88 53,96 53,105 70" fill="none" stroke="#16794c" stroke-width="5"/>
<circle cx="62" cy="55" r="6" fill="#16794c"/><circle cx="98" cy="55" r="6" fill="#16794c"/>"""
    return """<rect x="43" y="35" width="74" height="65" rx="10" fill="#eaf2ff" stroke="#2d65b3" stroke-width="4"/>
<path d="M43 56 H117 M62 35 V100 M98 35 V100" stroke="#2d65b3" stroke-width="4"/>"""


def keyword_matches(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword.lower()).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def fetch_text_url(url: str, headers: dict | None = None) -> str:
    request = Request(url, headers=headers or AMAZON_SEARCH_HEADERS)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def fetch_binary_url(url: str, headers: dict | None = None) -> bytes:
    request = Request(url, headers=headers or AMAZON_SEARCH_HEADERS)
    with urlopen(request, timeout=30) as response:
        return response.read()


def amazon_search_url(title: str, marketplace: str = AMAZON_AU_BASE_URL) -> str:
    return f"{marketplace.rstrip('/')}/s?k={quote_plus(title or '')}"


def amazon_product_url(asin: str, marketplace: str = AMAZON_AU_BASE_URL) -> str:
    return f"{marketplace.rstrip('/')}/dp/{asin}"


def extract_html_attr(tag: str, attr: str) -> str:
    match = re.search(rf"""{attr}\s*=\s*["']([^"']*)["']""", tag, re.IGNORECASE)
    return html_module.unescape(match.group(1)) if match else ""


def amazon_image_candidates_from_html(html: str, marketplace: str = AMAZON_AU_BASE_URL) -> list[dict]:
    candidates = []
    for match in re.finditer(r"""<div[^>]+data-asin=["']([A-Z0-9]{10})["'][\s\S]*?(?=<div[^>]+data-asin=|</body>)""", html or "", re.IGNORECASE):
        asin = match.group(1)
        block = match.group(0)
        image_tag = ""
        for image_match in re.finditer(r"<img\b[^>]*>", block, re.IGNORECASE):
            tag = image_match.group(0)
            classes = extract_html_attr(tag, "class")
            if "s-image" in classes:
                image_tag = tag
                break
        if not image_tag:
            continue
        image_url = extract_html_attr(image_tag, "src") or extract_html_attr(image_tag, "data-src")
        if not image_url:
            continue
        link = ""
        link_match = re.search(r"""href=["']([^"']*/dp/""" + re.escape(asin) + r"""[^"']*)["']""", block, re.IGNORECASE)
        if link_match:
            link = urljoin(marketplace, html_module.unescape(link_match.group(1)))
        candidates.append(
            {
                "asin": asin,
                "title": extract_html_attr(image_tag, "alt"),
                "image_url": image_url,
                "source_page": amazon_product_url(asin, marketplace),
                "result_url": link or amazon_product_url(asin, marketplace),
            }
        )
    return candidates


def amazon_match_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", (value or "").lower())
    return [token for token in tokens if len(token) > 1 and token not in AMAZON_IMAGE_STOPWORDS]


def amazon_title_match_score(query_title: str, result_title: str) -> float:
    query_tokens = amazon_match_tokens(query_title)
    result_tokens = set(amazon_match_tokens(result_title))
    if not query_tokens or not result_tokens:
        return 0.0
    matches = sum(1 for token in query_tokens if token in result_tokens)
    return matches / len(query_tokens)


def find_amazon_image_match(
    title: str,
    marketplace: str = AMAZON_AU_BASE_URL,
    fetch_text=fetch_text_url,
) -> dict | None:
    page = fetch_text(amazon_search_url(title, marketplace), AMAZON_SEARCH_HEADERS)
    if "captcha" in page.lower() and "enter the characters" in page.lower():
        return None
    candidates = amazon_image_candidates_from_html(page, marketplace)
    for candidate in candidates:
        candidate["match_score"] = amazon_title_match_score(title, candidate.get("title", ""))
    candidates.sort(key=lambda candidate: candidate.get("match_score", 0), reverse=True)
    return candidates[0] if candidates else None


def amazon_full_size_image_url(image_url: str) -> str:
    return re.sub(r"\._[^.]+_\.(jpg|jpeg|png|webp)$", r".\1", image_url or "", flags=re.IGNORECASE)


def safe_image_filename(title: str, index: int, extension: str) -> str:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())[:7]
    slug = "-".join(words) or "amazon-product"
    return f"{index:02d}-{slug}{extension}"


def image_extension_from_url(url: str) -> str:
    extension = os.path.splitext((url or "").split("?", 1)[0])[1].lower()
    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        return extension
    return ".jpg"


def row_has_image(row: dict) -> bool:
    normalized = normalize_row(row)
    return bool(pick(normalized, "image"))


def download_amazon_image(match: dict, image_dir: str, title: str, index: int, fetch_binary=fetch_binary_url) -> str:
    os.makedirs(image_dir, exist_ok=True)
    raw_image_url = match.get("image_url", "")
    image_url = amazon_full_size_image_url(raw_image_url) or raw_image_url
    output_path = os.path.abspath(os.path.join(image_dir, safe_image_filename(title, index, image_extension_from_url(image_url))))
    try:
        data = fetch_binary(image_url, AMAZON_SEARCH_HEADERS)
    except Exception:
        if image_url == raw_image_url:
            raise
        image_url = raw_image_url
        data = fetch_binary(image_url, AMAZON_SEARCH_HEADERS)
    if not data:
        raise ValueError(f"Amazon image download returned no data for {match.get('asin', '')}")
    with open(output_path, "wb") as handle:
        handle.write(data)
    return output_path


def enrich_csv_with_amazon_images(
    input_path: str,
    output_path: str,
    image_dir: str,
    marketplace: str = AMAZON_AU_BASE_URL,
    min_match_score: float = 0.30,
    fetch_text=fetch_text_url,
    fetch_binary=fetch_binary_url,
) -> str:
    with open(input_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for column in AMAZON_IMAGE_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)

    cache: dict[str, dict | None] = {}
    for index, row in enumerate(rows, start=1):
        title = row.get("Title") or pick(normalize_row(row), "title")
        if not title or row_has_image(row):
            continue
        if title not in cache:
            try:
                cache[title] = find_amazon_image_match(title, marketplace, fetch_text)
            except Exception as exc:
                cache[title] = None
                row["Amazon Image Match Title"] = f"Amazon image search failed: {exc}"
        match = cache[title]
        if not match:
            continue
        score = float(match.get("match_score", 0))
        row["Amazon ASIN"] = match.get("asin", "")
        row["Amazon Image Source Page"] = match.get("source_page", "")
        row["Amazon Image Match Title"] = match.get("title", "")
        row["Amazon Image Match Score"] = f"{score:.2f}"
        if score < min_match_score:
            continue
        try:
            row["Product Image URL"] = download_amazon_image(match, image_dir, title, index, fetch_binary)
        except Exception as exc:
            row["Product Image URL"] = ""
            row["Amazon Image Match Title"] = f"{row['Amazon Image Match Title']} [image download failed: {exc}]"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def read_csv(path: str, default_currency: str = "AUD", language: str = "zh") -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=2):
            normalized = normalize_row(row)
            amount, currency = parse_money(pick(normalized, "amount"), default_currency)
            shipping_paid, shipping_paid_currency = parse_money(pick(normalized, "shipping_paid"), currency)
            shipping_savings, shipping_savings_currency = parse_money(pick(normalized, "shipping_savings"), currency)
            non_member_shipping, non_member_shipping_currency = parse_money(pick(normalized, "non_member_shipping"), currency)
            title = pick(normalized, "title")
            category_key = infer_category(title)
            image_info = normalize_product_image(pick(normalized, "image"), path, title, category_key, language)
            record = {
                "source_file": os.path.abspath(path),
                "source_line": index,
                "order_date": canonical_date(pick(normalized, "order_date")),
                "order_id": pick(normalized, "order_id"),
                "title": title,
                "quantity": parse_quantity(pick(normalized, "quantity")),
                "amount": format_money(amount, currency) if amount is not None else "",
                "amount_value": amount,
                "currency": currency,
                "shipping_paid": format_money(shipping_paid, shipping_paid_currency) if shipping_paid is not None else "",
                "shipping_paid_value": shipping_paid,
                "shipping_paid_currency": shipping_paid_currency,
                "shipping_savings": format_money(shipping_savings, shipping_savings_currency) if shipping_savings is not None else "",
                "shipping_savings_value": shipping_savings,
                "shipping_savings_currency": shipping_savings_currency,
                "non_member_shipping": format_money(non_member_shipping, non_member_shipping_currency) if non_member_shipping is not None else "",
                "non_member_shipping_value": non_member_shipping,
                "non_member_shipping_currency": non_member_shipping_currency,
                "asin": pick(normalized, "asin"),
                "seller": pick(normalized, "seller"),
                "status": pick(normalized, "status"),
                "invoice_path": pick(normalized, "invoice_path"),
                "category_key": category_key,
                "category": category_key,
                **image_info,
            }
            records.append(record)
    return records


def format_money(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return ""
    return f"{currency} {amount.quantize(Decimal('0.01'))}"


def display_record(record: dict, language: str = "zh") -> dict:
    clean = dict(record)
    clean.pop("amount_value", None)
    clean.pop("shipping_paid_value", None)
    clean.pop("shipping_savings_value", None)
    clean.pop("non_member_shipping_value", None)
    category_key = clean.get("category_key") or clean.get("category") or "General Purchases"
    clean["category_key"] = category_key
    clean["category"] = localized_category(category_key, language)
    return clean


def shorten_title(title: str, max_chars: int = 52, language: str = "zh") -> str:
    text = " ".join((title or "").replace("–", "-").replace("—", "-").split())
    if not text:
        return report_labels(language)["untitled"]
    for delimiter in [",", "，", ";", "；", "|"]:
        if delimiter in text:
            text = text.split(delimiter, 1)[0].strip()
            break
    if len(text) > max_chars:
        cut = text[: max_chars + 1]
        text = cut.rsplit(" ", 1)[0] if " " in cut else text[:max_chars]
    text = re.sub(r"\s+(and|or|for|with|of|to|in|the|a|an)$", "", text, flags=re.IGNORECASE)
    return text.strip(" -,:;，；") or report_labels(language)["untitled"]


def display_top_record(record: dict, language: str = "zh") -> dict:
    clean = display_record(record, language)
    clean["display_title"] = shorten_title(clean.get("title", ""), language=language)
    return clean


def build_analysis(
    paths: list[str],
    default_currency: str = "AUD",
    report_year: int | None = None,
    prime_cost: str | Decimal = "79",
    language: str = "auto",
    non_member_shipping_per_order: str | Decimal | None = "",
    prime_plan: str = "auto",
    prime_annual_cost: str | Decimal = "79",
    prime_monthly_cost: str | Decimal = "9.99",
    prime_paid_months: str | int | None = "",
) -> dict:
    if report_year is None:
        report_year = datetime.now().year
    language_code = resolve_language(language)
    labels = report_labels(language_code)
    all_records = []
    for path in paths:
        all_records.extend(read_csv(path, default_currency, language_code))

    order_ids = {record["order_id"] for record in all_records if record.get("order_id")}
    missing_order_id_count = sum(1 for record in all_records if not record.get("order_id"))
    order_count = len(order_ids) + missing_order_id_count
    item_count = sum(record.get("quantity", 1) for record in all_records)

    currency_totals: dict[str, Decimal] = defaultdict(Decimal)
    category_totals: dict[str, Decimal] = defaultdict(Decimal)
    for record in all_records:
        amount = record.get("amount_value")
        if amount is None:
            continue
        currency_totals[record["currency"]] += amount
        category_totals[record.get("category_key") or record["category"]] += amount

    dates = [record["order_date"] for record in all_records if re.match(r"^\d{4}-\d{2}-\d{2}$", record.get("order_date", ""))]
    date_range = format_date_range(dates, language_code)

    top_purchases = sorted(
        [record for record in all_records if record.get("amount_value") is not None],
        key=lambda record: abs(record["amount_value"]),
        reverse=True,
    )[:5]
    top_categories = sorted(category_totals.items(), key=lambda item: abs(item[1]), reverse=True)[:8]

    analysis = {
        "title": "Amazon Purchase Organizer",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "language": language_code,
        "labels": labels,
        "sources": [os.path.abspath(path) for path in paths],
        "summary": {
            "overview": build_overview(order_count, item_count, currency_totals, language_code),
            "order_count": order_count,
            "item_count": item_count,
            "date_range": date_range,
            "total_spend": format_totals(currency_totals, language_code),
            "notes": build_notes(all_records, language_code),
            "long_term": build_long_term(language_code),
        },
        "orders": [display_record(record, language_code) for record in all_records],
        "top_purchases": [display_top_record(record, language_code) for record in top_purchases],
        "monthly_totals": build_monthly_totals(all_records, language_code),
        "category_totals": [
            {
                "category_key": category,
                "category": localized_category(category, language_code),
                "amount": format_money(total, guess_single_currency(currency_totals)),
            }
            for category, total in top_categories
        ],
        "prime_value": build_prime_value(
            all_records,
            report_year,
            prime_cost,
            default_currency,
            language_code,
            non_member_shipping_per_order,
            prime_plan,
            prime_annual_cost,
            prime_monthly_cost,
            prime_paid_months,
        ),
    }
    analysis["image_prompt"] = build_image_prompt(analysis)
    return analysis


def build_prime_value(
    records: list[dict],
    report_year: int,
    prime_cost: str | Decimal,
    default_currency: str,
    language: str = "zh",
    non_member_shipping_per_order: str | Decimal | None = "",
    prime_plan: str = "auto",
    prime_annual_cost: str | Decimal = "79",
    prime_monthly_cost: str | Decimal = "9.99",
    prime_paid_months: str | int | None = "",
) -> dict:
    membership = build_membership_plan(
        records,
        report_year,
        default_currency,
        prime_cost,
        prime_plan,
        prime_annual_cost,
        prime_monthly_cost,
        prime_paid_months,
        language,
    )
    membership_amount = membership["membership_amount"]
    membership_currency = membership["currency"]
    estimate_amount, estimate_currency = parse_money(str(non_member_shipping_per_order or ""), membership_currency)
    if estimate_amount is not None and estimate_amount <= 0:
        estimate_amount = None

    year_records = [record for record in records if record_year(record.get("order_date")) == report_year]
    groups = order_groups(year_records)
    hypothetical_total = Decimal("0")
    savings_total = Decimal("0")
    paid_total = Decimal("0")
    orders_with_hypothetical = 0
    orders_with_savings = 0
    orders_with_paid = 0
    used_non_member_field = False
    used_shipping_savings = False
    used_estimate = False

    for group in groups:
        savings = collapse_shipping_values(record.get("shipping_savings_value") for record in group)
        paid = collapse_shipping_values(record.get("shipping_paid_value") for record in group)
        explicit_non_member = collapse_shipping_values(record.get("non_member_shipping_value") for record in group)

        if savings is not None:
            savings_total += abs(savings)
            if savings != 0:
                orders_with_savings += 1
        if paid is not None:
            paid_total += abs(paid)
            if paid != 0:
                orders_with_paid += 1

        hypothetical = None
        if explicit_non_member is not None:
            hypothetical = abs(explicit_non_member)
            used_non_member_field = True
        elif savings is not None:
            hypothetical = abs(savings)
            used_shipping_savings = True
        elif estimate_amount is not None and purchased_order_group(group):
            hypothetical = abs(estimate_amount)
            used_estimate = True

        if hypothetical is not None:
            hypothetical_total += hypothetical
            if hypothetical != 0:
                orders_with_hypothetical += 1

    if used_non_member_field:
        non_member_basis = "non_member_shipping"
    elif used_shipping_savings:
        non_member_basis = "shipping_savings"
    elif used_estimate:
        non_member_basis = "estimated_per_order"
    else:
        non_member_basis = "none"

    if hypothetical_total > 0:
        net = hypothetical_total - membership_amount
        if net >= 0:
            status = "recovered"
            verdict = localized_hypothetical_verdict(language, "recovered", report_year, hypothetical_total, membership_amount, net, membership_currency, non_member_basis, estimate_amount, estimate_currency)
        else:
            status = "not_yet_recovered"
            verdict = localized_hypothetical_verdict(language, "not_recovered", report_year, hypothetical_total, membership_amount, net, membership_currency, non_member_basis, estimate_amount, estimate_currency)
    else:
        net = -membership_amount
        status = "insufficient_hypothetical_data"
        verdict = localized_hypothetical_verdict(language, "insufficient", report_year, paid_total, membership_amount, net, membership_currency, non_member_basis, estimate_amount, estimate_currency)

    return {
        "year": report_year,
        "basis": non_member_basis,
        "basis_display": localized_basis(non_member_basis, language),
        "non_member_shipping_basis": non_member_basis,
        "membership_plan": membership["plan"],
        "membership_plan_display": localized_membership_plan(membership["plan"], language),
        "membership_plan_source": membership["source"],
        "membership_paid_months": membership["paid_months"],
        "annual_membership_cost": format_money(membership["annual_amount"], membership_currency),
        "monthly_membership_cost": format_money(membership["monthly_amount"], membership_currency),
        "monthly_annualized_cost": format_money(membership["monthly_annualized_amount"], membership_currency) if membership["monthly_annualized_amount"] is not None else "",
        "annual_plan_difference": format_money(membership["annual_plan_difference"], membership_currency) if membership["annual_plan_difference"] is not None else "",
        "annual_plan_verdict": membership["annual_plan_verdict"],
        "membership_cost": format_money(membership_amount, membership_currency),
        "hypothetical_non_member_shipping": format_money(hypothetical_total, membership_currency),
        "non_member_shipping_per_order_assumption": format_money(estimate_amount, estimate_currency) if estimate_amount is not None else "",
        "shipping_savings_identified": format_money(savings_total, membership_currency),
        "shipping_paid_identified": format_money(paid_total, membership_currency),
        "orders_with_hypothetical_shipping": orders_with_hypothetical,
        "orders_with_shipping_savings": orders_with_savings,
        "orders_with_shipping_paid": orders_with_paid,
        "net_value": format_money(net, membership_currency),
        "status": status,
        "visual": prime_visual(status, language),
        "verdict": verdict,
        "pricing_source_note": localized_pricing_source(language),
    }


def prime_visual(status: str, language: str = "zh") -> dict:
    if status == "recovered":
        return {
            "tone": "green",
            "emoji": "👍",
            "label": "Membership recovered" if language == "en" else "已值回会员费",
        }
    return {
        "tone": "red",
        "emoji": "😭",
        "label": "Not recovered" if language == "en" else "未值回会员费",
    }


def build_membership_plan(
    records: list[dict],
    report_year: int,
    default_currency: str,
    prime_cost: str | Decimal,
    prime_plan: str,
    prime_annual_cost: str | Decimal,
    prime_monthly_cost: str | Decimal,
    prime_paid_months: str | int | None,
    language: str,
) -> dict:
    annual_amount, annual_currency = parse_money(str(prime_annual_cost), default_currency)
    monthly_amount, monthly_currency = parse_money(str(prime_monthly_cost), annual_currency)
    fallback_amount, fallback_currency = parse_money(str(prime_cost), annual_currency)
    annual_amount = annual_amount if annual_amount is not None else Decimal("79")
    monthly_amount = monthly_amount if monthly_amount is not None else Decimal("9.99")
    fallback_amount = fallback_amount if fallback_amount is not None else annual_amount
    currency = fallback_currency or annual_currency or monthly_currency or default_currency

    membership_records = [
        record for record in records
        if record_year(record.get("order_date")) == report_year and is_prime_membership_record(record)
    ]
    membership_amounts = [abs(record["amount_value"]) for record in membership_records if record.get("amount_value") is not None and record["amount_value"] != 0]
    normalized_plan = (prime_plan or "auto").strip().lower()

    source = "fallback_prime_cost"
    plan = "annual"
    paid_months = 0
    membership_amount = fallback_amount

    if membership_amounts:
        source = "detected_order_records"
        annual_like = [amount for amount in membership_amounts if amount >= annual_amount * Decimal("0.75")]
        if annual_like:
            plan = "annual"
            membership_amount = sum(annual_like, Decimal("0"))
            paid_months = 12
        else:
            plan = "monthly"
            membership_amount = sum(membership_amounts, Decimal("0"))
            paid_months = len(membership_amounts)
            monthly_amount = (membership_amount / Decimal(paid_months)).quantize(Decimal("0.01")) if paid_months else monthly_amount
    elif normalized_plan == "monthly":
        source = "manual_plan"
        plan = "monthly"
        paid_months = parse_paid_months(prime_paid_months) or 12
        membership_amount = monthly_amount * Decimal(paid_months)
    elif normalized_plan == "annual":
        source = "manual_plan"
        plan = "annual"
        paid_months = 12
        membership_amount = fallback_amount if str(prime_cost).strip() else annual_amount

    monthly_annualized_amount = None
    annual_plan_difference = None
    annual_plan_verdict = ""
    if plan == "monthly":
        monthly_annualized_amount = monthly_amount * Decimal("12")
        annual_plan_difference = monthly_annualized_amount - annual_amount
        annual_plan_verdict = localized_annual_plan_verdict(language, annual_plan_difference, currency)

    return {
        "plan": plan,
        "source": source,
        "paid_months": paid_months,
        "membership_amount": membership_amount,
        "annual_amount": annual_amount,
        "monthly_amount": monthly_amount,
        "monthly_annualized_amount": monthly_annualized_amount,
        "annual_plan_difference": annual_plan_difference,
        "annual_plan_verdict": annual_plan_verdict,
        "currency": currency,
    }


def parse_paid_months(value: str | int | None) -> int | None:
    if value in {None, ""}:
        return None
    try:
        months = int(value)
    except (TypeError, ValueError):
        return None
    return min(12, max(1, months))


def is_prime_membership_record(record: dict) -> bool:
    title = (record.get("title") or "").lower()
    return "prime" in title and ("membership" in title or "subscription" in title or title.strip() == "amazon prime")


def localized_annual_plan_verdict(language: str, difference: Decimal, currency: str) -> str:
    if difference > 0:
        if language == "en":
            return f"Annual plan would save {format_money(difference, currency)} versus paying monthly for a full year."
        return f"年费可省 {format_money(difference, currency)}"
    if difference < 0:
        if language == "en":
            return f"Annual plan would cost {format_money(abs(difference), currency)} more than monthly for a full year."
        return f"年费会多花 {format_money(abs(difference), currency)}"
    return "年费和月付全年相同" if language != "en" else "Annual and full-year monthly cost the same."


def localized_membership_plan(plan: str, language: str) -> str:
    if language == "en":
        return "Monthly" if plan == "monthly" else "Annual"
    return "月付" if plan == "monthly" else "年付"


def order_groups(records: list[dict]) -> list[list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for index, record in enumerate(records):
        key = record.get("order_id") or f"{record.get('source_file', '')}:{record.get('source_line', index)}"
        buckets.setdefault(key, []).append(record)
    return list(buckets.values())


def collapse_shipping_values(values) -> Decimal | None:
    amounts = [abs(value) for value in values if value is not None]
    if not amounts:
        return None
    unique = {amount.quantize(Decimal("0.01")) for amount in amounts}
    if len(unique) == 1:
        return amounts[0]
    return sum(amounts, Decimal("0"))


def purchased_order_group(group: list[dict]) -> bool:
    if all(is_prime_membership_record(record) for record in group):
        return False
    amounts = [record.get("amount_value") for record in group if record.get("amount_value") is not None]
    if not amounts:
        return True
    if sum(amounts, Decimal("0")) > 0:
        return True
    return not any((record.get("status") or "").strip().lower() == "cancelled" for record in group)


def localized_hypothetical_verdict(
    language: str,
    kind: str,
    year: int,
    hypothetical_total: Decimal,
    membership_amount: Decimal,
    net: Decimal,
    currency: str,
    basis: str,
    estimate_amount: Decimal | None,
    estimate_currency: str,
) -> str:
    estimate_text = format_money(estimate_amount, estimate_currency) if estimate_amount is not None else ""
    if language == "en":
        if kind == "insufficient":
            return f"{year} has no non-member shipping assumption or usable Prime shipping-savings evidence; paid shipping is actual spend context only and cannot judge membership value."
        prefix = (
            f"Using an assumed non-member shipping cost of {estimate_text} per order, {year} hypothetical non-member shipping totals {format_money(hypothetical_total, currency)}"
            if basis == "estimated_per_order" and estimate_text
            else f"{year} hypothetical non-member shipping totals {format_money(hypothetical_total, currency)}"
        )
        if kind == "recovered":
            return f"{prefix}; it covers the membership cost, with estimated net value of {format_money(net, currency)}."
        return f"{prefix}; it is short of the membership cost by {format_money(abs(net), currency)}."
    if kind == "insufficient":
        return f"{year} 年没有无会员运费假设或可用的 Prime 运费节省字段；已付运费只能作为实际支出记录，不能判断会员是否划算。"
    prefix = (
        f"按每单 {estimate_text} 假设，{year} 年无会员运费总和为 {format_money(hypothetical_total, currency)}"
        if basis == "estimated_per_order" and estimate_text
        else f"{year} 年假设无会员运费总和为 {format_money(hypothetical_total, currency)}"
    )
    if kind == "recovered":
        return f"{prefix}，已覆盖会员费，净值约 {format_money(net, currency)}。"
    return f"{prefix}，距离会员费还差 {format_money(abs(net), currency)}。"


def localized_pricing_source(language: str) -> str:
    if language == "en":
        return "Default comparison uses Amazon Australia Prime annual cost of AUD 79; override with --prime-cost."
    return "默认按 Amazon Australia 官方 Prime 年付 AU$79 计算；可用 --prime-cost 覆盖。"


def record_year(value: str) -> int | None:
    if not value or not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return None
    return int(value[:4])


def record_month(value: str, language: str = "zh") -> str:
    if value and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value[:7]
    return report_labels(language)["unknown_month"]


def month_sort_key(month: str) -> str:
    return month if re.match(r"^\d{4}-\d{2}$", month or "") else "0000-00"


def build_monthly_totals(records: list[dict], language: str = "zh") -> list[dict]:
    buckets: dict[str, dict] = {}
    for record in records:
        month = record_month(record.get("order_date", ""), language)
        bucket = buckets.setdefault(month, {
            "totals": defaultdict(Decimal),
            "order_ids": set(),
            "missing_order_id_count": 0,
            "item_count": 0,
        })
        amount = record.get("amount_value")
        if amount is not None:
            bucket["totals"][record.get("currency", "AUD")] += amount
        if record.get("order_id"):
            bucket["order_ids"].add(record["order_id"])
        else:
            bucket["missing_order_id_count"] += 1
        bucket["item_count"] += record.get("quantity", 1)

    rows = []
    for month in sorted(buckets.keys(), key=month_sort_key, reverse=True):
        bucket = buckets[month]
        rows.append({
            "month": month,
            "amount": format_totals(bucket["totals"], language),
            "order_count": len(bucket["order_ids"]) + bucket["missing_order_id_count"],
            "item_count": bucket["item_count"],
        })
    return rows


def guess_single_currency(currency_totals: dict[str, Decimal]) -> str:
    if len(currency_totals) == 1:
        return next(iter(currency_totals.keys()))
    return "MIXED"


def format_totals(currency_totals: dict[str, Decimal], language: str = "zh") -> str:
    if not currency_totals:
        return report_labels(language)["unrecognized"]
    return " + ".join(format_money(total, currency) for currency, total in sorted(currency_totals.items()))


def build_overview(order_count: int, item_count: int, totals: dict[str, Decimal], language: str = "zh") -> str:
    total_text = format_totals(totals, language)
    if language == "en":
        return f"Organized {order_count} orders and {item_count} items, with total spend of {total_text}."
    return f"已整理 {order_count} 个订单、{item_count} 件物品，总花费 {total_text}。"


def build_notes(records: list[dict], language: str = "zh") -> list[str]:
    if not records:
        if language == "en":
            return ["No order records to organize yet; export or provide an Amazon order CSV first."]
        return ["没有可整理的订单记录；先导出或提供 Amazon 订单 CSV。"]
    if language == "en":
        notes = ["Read-only organization; original CSV/PDF files or order detail pages remain the traceable source."]
        if any(record.get("status", "").lower() == "cancelled" for record in records):
            notes.append("Cancelled orders are handled according to visible list amounts, usually AUD 0.00.")
        if any(record.get("shipping_paid_value") is not None for record in records):
            notes.append("Paid shipping is tracked separately; it is not the same as Prime shipping savings.")
        if not any(record.get("shipping_savings_value") for record in records):
            notes.append("No Prime/free-shipping savings field was recognized; more evidence is needed to judge payback.")
        return notes
    notes = ["订单列表只读整理，原始 CSV/PDF 或订单详情页仍是追溯依据。"]
    if any(record.get("status", "").lower() == "cancelled" for record in records):
        notes.append("取消订单按列表可见金额处理，通常为 AUD 0.00。")
    if any(record.get("shipping_paid_value") is not None for record in records):
        notes.append("已付运费单独统计；它不能等同于 Prime 免运费节省。")
    if not any(record.get("shipping_savings_value") for record in records):
        notes.append("未识别到 Prime/免运费节省字段，会员是否回本需要更多运费节省证据。")
    return notes


def build_long_term(language: str = "zh") -> list[str]:
    if language == "en":
        return [
            "Keep original CSV/PDF files; the report is for reading, originals are for traceability.",
            "For tax, reimbursement, or warranty use, keep invoice PDFs or order-detail screenshots, not only product titles.",
            "Amazon login, MFA, payment, return, cancellation, and address changes must stay manual.",
        ]
    return [
        "固定保存原始 CSV/PDF，不要只保留整理后的报告；报告用于阅读，原始文件用于追溯。",
        "税务、报销、保修用途要保留 invoice PDF 或订单详情页截图，不能只靠商品标题。",
        "亚马逊登录、MFA、付款、退货、取消、改地址等动作必须由用户自己完成。",
    ]


def build_image_prompt(analysis: dict) -> str:
    summary = analysis.get("summary", {})
    prime = analysis.get("prime_value", {})
    labels = analysis.get("labels") or report_labels(analysis.get("language"))
    language = analysis.get("language", "zh")
    visual = prime.get("visual") or prime_visual(prime.get("status", ""), language)
    top = analysis.get("top_purchases", [])[:3]
    monthly = analysis.get("monthly_totals", [])[:6]
    categories = analysis.get("category_totals", [])[:4]

    top_lines = "\n".join(
        f"- {item.get('display_title') or item.get('title', labels['untitled'])}: {item.get('amount', '')} ({item.get('category', labels['uncategorized'])})"
        for item in top
    ) or f"- {labels['no_amount_data']}"
    category_lines = "\n".join(
        f"- {item.get('category', labels['uncategorized'])}: {item.get('amount', '')}"
        for item in categories
    ) or f"- {labels['no_category_data']}"
    monthly_lines = "\n".join(
        monthly_prompt_line(item, labels, language)
        for item in monthly
    ) or f"- {labels['no_monthly_data']}"
    annual_plan_line = ""
    if prime.get("annual_plan_verdict"):
        annual_plan_line = f"- {labels['annual_plan_comparison']}: {prime.get('annual_plan_verdict')}\n"

    visual_language = "Chinese" if language == "zh" else "English"

    return f"""Use case: infographic-diagram
Asset type: single shareable PNG report image, 3:2 landscape dashboard
Primary request: Create a polished {visual_language} Amazon purchase summary infographic with exact text blocks below. The image should feel like a premium operational dashboard, not a marketing poster.

Critical accuracy rule:
- Keep all numbers and labels exactly as written.
- Do not invent extra totals, discounts, orders, dates, categories, or advice.
- If a text block is too long, use line breaks rather than rewriting the values.
- The {labels['amount_top']} section must show product photos or generated thumbnails next to each listed product name.

Title:
{labels['report_title']}

{labels['core_metrics']}:
- {labels['total_spend']}: {summary.get('total_spend', labels['unrecognized'])}
- {labels['order_count']}: {summary.get('order_count', 0)}
- {labels['item_count']}: {summary.get('item_count', 0)}
- {labels['date_range']}: {summary.get('date_range', labels['unrecognized'])}

{labels['prime_value']}:
- {labels['year']}: {prime.get('year', '')}
- {labels['membership_plan']}: {prime.get('membership_plan_display') or prime.get('membership_plan', '')}
- {labels['membership_cost']}: {prime.get('membership_cost', '')}
- {labels['hypothetical_shipping']}: {prime.get('hypothetical_non_member_shipping', '')}
- {labels['shipping_paid']}: {prime.get('shipping_paid_identified', '')}
- {labels['net_value']}: {prime.get('net_value', '')}
{annual_plan_line}- {conclusion_label(language)}: {visual.get('emoji', '😭')} {visual.get('label', '')}
- {calculation_label(language)}: {prime.get('verdict', '')}

{labels['amount_top']}:
{top_lines}

{labels['monthly_ranking']}:
{monthly_lines}

{labels['category_top']}:
{category_lines}

Visual direction:
- Clean dashboard infographic, white and light grey base, restrained blue and neutral accents.
- Use the same 3:2 local web report composition: centered title, four icon metric cards, wide Prime value card, bottom three cards for Top purchases with product photos, monthly ranking bars, and category totals.
- Prime value card must make the conclusion visually obvious: green with 👍 when recovered, red with 😭 when not recovered.
- No Amazon logo, no copyrighted brand marks, no payment card visuals, no fake UI browser chrome.
- Output should be readable at desktop preview size.
"""


def monthly_prompt_line(item: dict, labels: dict, language: str) -> str:
    if language == "en":
        return f"- {item.get('month', labels['unknown_month'])}: {item.get('amount', '')}, {item.get('order_count', 0)} orders, {item.get('item_count', 0)} items"
    return f"- {item.get('month', labels['unknown_month'])}: {item.get('amount', '')}，{item.get('order_count', 0)} 个订单，{item.get('item_count', 0)} 件物品"


def conclusion_label(language: str) -> str:
    return "Conclusion" if language == "en" else "结论"


def calculation_label(language: str) -> str:
    return "Calculation" if language == "en" else "计算说明"


def write_json(analysis: dict, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
    return path


def write_text(text: str, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def enriched_csv_path(input_path: str, explicit_output: str = "") -> str:
    if explicit_output:
        return os.path.abspath(os.path.expanduser(explicit_output))
    directory = os.path.dirname(os.path.abspath(input_path))
    stem, extension = os.path.splitext(os.path.basename(input_path))
    return os.path.join(directory, f"{stem}_with_amazon_photos{extension or '.csv'}")


def enriched_image_dir(input_path: str, explicit_dir: str = "") -> str:
    if explicit_dir:
        return os.path.abspath(os.path.expanduser(explicit_dir))
    return os.path.join(os.path.dirname(os.path.abspath(input_path)), "amazon_photos_amazon")


def prepare_input_paths(args: argparse.Namespace) -> list[str]:
    if not args.fetch_amazon_images:
        return args.inputs
    if args.amazon_enriched_csv and len(args.inputs) > 1:
        raise ValueError("--amazon-enriched-csv can only be used with one input CSV")

    enriched_paths = []
    for input_path in args.inputs:
        output_path = enriched_csv_path(input_path, args.amazon_enriched_csv if len(args.inputs) == 1 else "")
        image_dir = enriched_image_dir(input_path, args.amazon_image_dir)
        enriched_paths.append(
            enrich_csv_with_amazon_images(
                input_path,
                output_path,
                image_dir,
                args.amazon_marketplace,
                args.amazon_image_min_score,
            )
        )
    return enriched_paths


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize Amazon order CSV exports into an interactive report.")
    parser.add_argument("inputs", nargs="+", help="CSV files exported from Amazon order/report pages.")
    parser.add_argument("--json", default=os.path.expanduser("~/Desktop/amazon-purchase-analysis.json"), help="Output analysis JSON path.")
    parser.add_argument("--html", default=os.path.expanduser("~/Desktop/amazon-purchase-report.html"), help="Output local HTML report path. Pass an empty string to skip HTML.")
    parser.add_argument("--png", default=os.path.expanduser("~/Desktop/amazon-purchase-report.png"), help="Output exact PNG report path.")
    parser.add_argument("--background", default="", help="Optional GPT-image2-generated no-text background PNG for the exact report image.")
    parser.add_argument("--image-prompt", default=os.path.expanduser("~/Desktop/amazon-purchase-image-prompt.txt"), help="Output GPT-image2 prompt path.")
    parser.add_argument("--currency", default="AUD", help="Default currency when the CSV value only uses '$'.")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to use for Prime value analysis.")
    parser.add_argument("--prime-cost", default="79", help="Prime membership cost to compare against shipping savings.")
    parser.add_argument("--prime-plan", default="auto", choices=["auto", "annual", "monthly"], help="Prime membership plan. Auto detects Prime membership charge rows when present.")
    parser.add_argument("--prime-annual-cost", default="79", help="Annual Prime membership cost used for plan comparison.")
    parser.add_argument("--prime-monthly-cost", default="9.99", help="Monthly Prime membership cost used for plan comparison.")
    parser.add_argument("--prime-paid-months", default="", help="Paid months to use when --prime-plan monthly is set without detected membership charge rows.")
    parser.add_argument("--language", default="auto", choices=["auto", "zh", "en"], help="Report label language. Use the user's operating/conversation language when known.")
    parser.add_argument("--non-member-shipping-per-order", default="", help="Optional assumed non-member shipping cost per eligible paid order, used when no explicit without-Prime shipping field exists.")
    parser.add_argument("--fetch-amazon-images", action="store_true", help="Read-only search Amazon for product photos, write an enriched CSV, and use those photos in the report.")
    parser.add_argument("--amazon-enriched-csv", default="", help="Output enriched CSV path when --fetch-amazon-images is used with one input.")
    parser.add_argument("--amazon-image-dir", default="", help="Directory for downloaded Amazon product photos. Defaults to amazon_photos_amazon beside each input CSV.")
    parser.add_argument("--amazon-marketplace", default=AMAZON_AU_BASE_URL, help="Amazon marketplace base URL for read-only image search.")
    parser.add_argument("--amazon-image-min-score", type=float, default=0.30, help="Minimum title-match score required before an Amazon search result image is used.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    input_paths = prepare_input_paths(args)
    analysis = build_analysis(
        input_paths,
        args.currency,
        args.year,
        args.prime_cost,
        args.language,
        args.non_member_shipping_per_order,
        args.prime_plan,
        args.prime_annual_cost,
        args.prime_monthly_cost,
        args.prime_paid_months,
    )
    write_json(analysis, args.json)
    write_text(analysis["image_prompt"], args.image_prompt)
    build_image_report.render_png(analysis, args.png, args.background or None)
    if args.html:
        build_report.render_report(analysis, args.html)
    print(args.html or args.png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
