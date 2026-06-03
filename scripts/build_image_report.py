#!/usr/bin/env python3
"""Render an exact PNG summary image from Amazon purchase analysis JSON."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


W, H = 1536, 1024
MARGIN = 52
CARD = "#ffffff"
INK = "#071225"
MUTED = "#445064"
SUBTLE = "#6b7280"
LINE = "#dce3ec"
GREEN = "#08752f"
GREEN_BG = "#f1fbf2"
RED = "#b3261e"
RED_BG = "#fff0ef"
BLUE = "#0f5bd7"
BLUE_2 = "#2478ef"
BLUE_BG = "#eaf3ff"
YELLOW = "#966600"
PAGE = "#fbfdff"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size, index=1 if bold and path.endswith(".ttc") else 0)
            except Exception:
                continue
    return ImageFont.load_default()


def load_emoji_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            for candidate_size in [size, 64, 48, 32, 128]:
                try:
                    return ImageFont.truetype(path, size=candidate_size)
                except Exception:
                    continue
    return load_font(size, True)


FONT_TITLE = load_font(58, True)
FONT_H2 = load_font(29, True)
FONT_H3 = load_font(22, True)
FONT_BODY = load_font(18)
FONT_SMALL = load_font(15)
FONT_TINY = load_font(13)
FONT_NUM = load_font(31, True)
FONT_PRIME = load_font(20, True)
FONT_EMOJI = load_emoji_font(64)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=LINE, radius=14, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy, value, font=FONT_BODY, fill=INK, max_chars=None, line_gap=5):
    x, y = xy
    lines = [str(value)]
    if max_chars:
        lines = []
        for part in str(value).splitlines() or [""]:
            lines.extend(wrap(part, width=max_chars) or [""])
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def center_text(draw: ImageDraw.ImageDraw, box, value, font, fill=INK):
    bbox = draw.textbbox((0, 0), str(value), font=font)
    x = box[0] + (box[2] - box[0] - (bbox[2] - bbox[0])) / 2
    y = box[1] + (box[3] - box[1] - (bbox[3] - bbox[1])) / 2
    draw.text((x, y), str(value), font=font, fill=fill)


def fit_line(value: str, max_chars: int) -> str:
    value = " ".join(str(value).split())
    return value if len(value) <= max_chars else value[: max(0, max_chars - 1)].rstrip() + "…"


def emoji_text(draw: ImageDraw.ImageDraw, xy, value: str, font: ImageFont.FreeTypeFont, fill=INK):
    try:
        draw.text(xy, value, font=font, embedded_color=True)
    except TypeError:
        draw.text(xy, value, font=font, fill=fill)


def paste_emoji(image: Image.Image, xy, value: str, target_size: int = 36):
    canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    canvas_draw = ImageDraw.Draw(canvas)
    emoji_text(canvas_draw, (0, 0), value, FONT_EMOJI)
    alpha_box = canvas.getchannel("A").getbbox()
    if not alpha_box:
        return
    cropped = canvas.crop(alpha_box)
    cropped.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
    image.alpha_composite(cropped, (int(xy[0]), int(xy[1])))


def draw_icon(draw: ImageDraw.ImageDraw, x: int, y: int, kind: str, color=BLUE):
    if kind == "money":
        draw.ellipse((x + 14, y + 14, x + 74, y + 74), outline=color, width=5)
        center_text(draw, (x + 14, y + 13, x + 74, y + 74), "$", load_font(42, True), color)
    elif kind == "bag":
        draw.rounded_rectangle((x + 18, y + 30, x + 70, y + 74), radius=6, fill=color)
        draw.arc((x + 30, y + 14, x + 58, y + 44), 180, 360, fill=color, width=5)
    elif kind == "cube":
        draw.polygon([(x + 44, y + 14), (x + 76, y + 32), (x + 44, y + 50), (x + 12, y + 32)], fill=color)
        draw.polygon([(x + 12, y + 36), (x + 44, y + 54), (x + 44, y + 84), (x + 12, y + 66)], fill="#2f7cf0")
        draw.polygon([(x + 76, y + 36), (x + 44, y + 54), (x + 44, y + 84), (x + 76, y + 66)], fill="#0b4fbf")
    elif kind == "calendar":
        draw.rounded_rectangle((x + 16, y + 18, x + 72, y + 74), radius=5, outline=color, width=5)
        draw.line((x + 16, y + 34, x + 72, y + 34), fill=color, width=5)
        for px in [30, 46, 62]:
            for py in [48, 62]:
                draw.rectangle((x + px - 3, y + py - 3, x + px + 3, y + py + 3), fill=color)


def metric(draw, x, y, w, h, label, value, icon_kind):
    rounded(draw, (x, y, x + w, y + h), CARD, radius=14)
    rounded(draw, (x + 24, y + 28, x + 112, y + 116), BLUE_BG, outline=BLUE_BG, radius=20)
    draw_icon(draw, x + 24, y + 28, icon_kind)
    draw.text((x + 136, y + 38), str(label), font=FONT_H3, fill=INK)
    font = FONT_H3 if icon_kind == "calendar" else (FONT_NUM if len(str(value)) <= 24 else FONT_H2)
    draw.text((x + 136, y + 78), str(value), font=font, fill=BLUE)


def parse_amount(value) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group(0)) if match else 0.0


def draw_title(draw):
    title = "Amazon 购买整理报告"
    bbox = draw.textbbox((0, 0), title, font=FONT_TITLE)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    ty = 24
    draw.text((tx, ty), title, font=FONT_TITLE, fill=INK)
    cy = ty + 30
    draw.line((tx - 160, cy, tx - 40, cy), fill=BLUE_2, width=2)
    draw.ellipse((tx - 172, cy - 6, tx - 160, cy + 6), fill=BLUE_2)
    draw.line((tx + tw + 40, cy, tx + tw + 160, cy), fill=BLUE_2, width=2)
    draw.ellipse((tx + tw + 160, cy - 6, tx + tw + 172, cy + 6), fill=BLUE_2)


def star_points(cx, cy, r1, r2):
    return [
        (cx, cy - r1), (cx + r2, cy - r2), (cx + r1, cy),
        (cx + r2, cy + r2), (cx, cy + r1), (cx - r2, cy + r2),
        (cx - r1, cy), (cx - r2, cy - r2),
    ]


def draw_prime_sparkle(draw, cx, cy, size):
    draw.polygon(star_points(cx, cy, size, max(2, size // 4)), fill="#7fca98")


def shield_polygon(x, y, w, h):
    return [
        (x + w * 0.50, y + h * 0.02),
        (x + w * 0.68, y + h * 0.12),
        (x + w * 0.88, y + h * 0.21),
        (x + w * 0.92, y + h * 0.47),
        (x + w * 0.86, y + h * 0.68),
        (x + w * 0.70, y + h * 0.86),
        (x + w * 0.50, y + h * 0.98),
        (x + w * 0.30, y + h * 0.86),
        (x + w * 0.14, y + h * 0.68),
        (x + w * 0.08, y + h * 0.47),
        (x + w * 0.12, y + h * 0.21),
        (x + w * 0.32, y + h * 0.12),
    ]


def draw_prime_shield(image, draw, x, y, w=136, h=156):
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    points = shield_polygon(x + 4, y + 7, w, h)
    shadow_draw.polygon(points, fill=(0, 80, 30, 34))
    image.alpha_composite(shadow)

    mask = Image.new("L", (W, H), 0)
    mask_draw = ImageDraw.Draw(mask)
    points = shield_polygon(x, y, w, h)
    mask_draw.polygon(points, fill=255)
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad_px = gradient.load()
    for yy in range(int(y), int(y + h) + 1):
        t = min(1, max(0, (yy - y) / h))
        if t < 0.48:
            k = t / 0.48
            r = int(79 * (1 - k) + 21 * k)
            g = int(206 * (1 - k) + 154 * k)
            b = int(131 * (1 - k) + 80 * k)
        else:
            k = (t - 0.48) / 0.52
            r = int(21 * (1 - k) + 4 * k)
            g = int(154 * (1 - k) + 115 * k)
            b = int(80 * (1 - k) + 52 * k)
        for xx in range(int(x), int(x + w) + 1):
            grad_px[xx, yy] = (r, g, b, 255)
    gradient.putalpha(mask)
    image.alpha_composite(gradient)
    draw.line(points + [points[0]], fill="#08752f", width=2)

    crown = [
        (x + w * 0.28, y + h * 0.55),
        (x + w * 0.20, y + h * 0.33),
        (x + w * 0.40, y + h * 0.45),
        (x + w * 0.50, y + h * 0.25),
        (x + w * 0.60, y + h * 0.45),
        (x + w * 0.80, y + h * 0.33),
        (x + w * 0.72, y + h * 0.55),
    ]
    draw.polygon(crown, fill="#ffffff")
    draw.rounded_rectangle((x + w * 0.30, y + h * 0.60, x + w * 0.70, y + h * 0.67), radius=2, fill="#ffffff")
    center_text(draw, (x + w * 0.10, y + h * 0.71, x + w * 0.90, y + h * 0.90), "Prime", FONT_PRIME, "#ffffff")


def draw_prime(image, draw, analysis, y=272):
    labels = analysis.get("labels", {})
    prime = analysis.get("prime_value", {})
    visual = prime.get("visual") or {}
    x, w, h = MARGIN, W - MARGIN * 2, 238
    tone = visual.get("tone", "red")
    accent = GREEN if tone == "green" else RED
    fill = GREEN_BG if tone == "green" else RED_BG
    rounded(draw, (x, y, x + w, y + h), fill, outline=accent, radius=14)
    draw_prime_sparkle(draw, x + 34, y + 164, 14)
    draw_prime_sparkle(draw, x + 172, y + 42, 12)
    draw_prime_shield(image, draw, x + 54, y + 38, 118, 146)
    draw.text((x + 214, y + 32), labels.get("prime_value", "Prime 价值判断"), font=FONT_H2, fill=accent)

    cols = [
        (labels.get("year", "年份"), prime.get("year", "")),
        (labels.get("membership_plan", "会员方案"), prime.get("membership_plan_display") or prime.get("membership_plan", "")),
        (labels.get("membership_cost", "会员费"), prime.get("membership_cost", "")),
        (labels.get("hypothetical_shipping", "假设无会员运费"), prime.get("hypothetical_non_member_shipping", "")),
        (labels.get("shipping_paid", "运费"), prime.get("shipping_paid_identified", "")),
        (labels.get("net_value", "已省下"), prime.get("net_value", "")),
    ]
    start_x = x + 214
    col_w = 138
    for index, (k, v) in enumerate(cols):
        cx = start_x + index * col_w
        if index:
            draw.line((cx - 16, y + 86, cx - 16, y + 132), fill="#b6d6c2", width=1)
        draw.text((cx, y + 86), str(k), font=FONT_SMALL, fill=INK)
        draw.text((cx, y + 124), str(v), font=FONT_BODY, fill=accent)

    result_x = x + w - 286
    draw.line((result_x - 26, y + 36, result_x - 26, y + h - 62), fill="#b6d6c2", width=1)
    draw.text((result_x, y + 42), "结论" if analysis.get("language") != "en" else "Conclusion", font=FONT_H3, fill=INK)
    rounded(draw, (result_x, y + 88, result_x + 260, y + 176), "#ffffff", outline=accent, radius=12, width=2)
    paste_emoji(image, (result_x + 22, y + 110), visual.get("emoji", "😭"), target_size=42)
    draw.text((result_x + 80, y + 118), fit_line(visual.get("label", ""), 12), font=FONT_H2, fill=accent)
    note = prime.get("verdict", "")
    text(draw, (x + 214, y + 176), f"{'计算说明' if analysis.get('language') != 'en' else 'Calculation'}：{note}", FONT_BODY, INK, max_chars=72, line_gap=3)


def load_raster_product_image(source: str):
    raw = source or ""
    try:
        if raw.startswith("data:image/") and ";base64," in raw and "svg" not in raw[:40]:
            encoded = raw.split(";base64,", 1)[1]
            return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
        if raw and os.path.exists(raw):
            return Image.open(raw).convert("RGBA")
    except Exception:
        return None
    return None


def draw_product_thumbnail(image, draw, x, y, w, h, item):
    rounded(draw, (x, y, x + w, y + h), BLUE_BG, outline="#dbeafe", radius=10)
    loaded = load_raster_product_image(item.get("product_image", ""))
    if loaded:
        loaded.thumbnail((w - 8, h - 8), Image.Resampling.LANCZOS)
        px = x + (w - loaded.width) // 2
        py = y + (h - loaded.height) // 2
        image.alpha_composite(loaded, (px, py))
        return
    category = item.get("category_key", "")
    if category == "Health & Fitness":
        draw.ellipse((x + 28, y + 8, x + w - 28, y + 20), fill="#d1d5db")
        draw.rounded_rectangle((x + 28, y + 14, x + w - 28, y + h - 10), radius=10, fill="#f8fafc", outline="#9ca3af", width=2)
        draw.rectangle((x + 36, y + 34, x + w - 36, y + 54), fill="#111827")
        center_text(draw, (x + 36, y + 34, x + w - 36, y + 54), "XTEND", FONT_TINY, "#ffffff")
    elif category == "Hobbies & Toys":
        draw.rectangle((x + 12, y + 14, x + w - 12, y + h - 12), fill="#111827")
        draw.rectangle((x + 20, y + 22, x + w - 20, y + h - 24), fill="#f8fafc")
        draw.arc((x + 22, y + 32, x + w - 20, y + h + 10), 200, 330, fill=BLUE, width=4)
        draw.line((x + 18, y + h - 12, x + w - 12, y + h - 12), fill="#1f2937", width=8)
    elif category == "Office":
        draw.rounded_rectangle((x + 15, y + 18, x + w - 15, y + 54), radius=5, fill=BLUE)
        draw.rectangle((x + 24, y + 27, x + w - 24, y + 45), fill="#eaf2ff")
        draw.polygon([(x + 44, y + 56), (x + 58, y + 56), (x + 66, y + h - 10), (x + 36, y + h - 10)], fill=BLUE)
    else:
        draw.rounded_rectangle((x + 18, y + 18, x + w - 18, y + h - 12), radius=10, fill="#f8fafc", outline=BLUE, width=3)
        draw.line((x + 18, y + 40, x + w - 18, y + 40), fill=BLUE, width=3)


def draw_section_title(draw, x, y, icon_kind, title, color=BLUE):
    if icon_kind == "trophy":
        draw.polygon([(x + 12, y + 4), (x + 40, y + 4), (x + 36, y + 24), (x + 16, y + 24)], fill=color)
        draw.rectangle((x + 24, y + 24, x + 28, y + 38), fill=color)
        draw.rectangle((x + 16, y + 38, x + 36, y + 42), fill=color)
    elif icon_kind == "chart":
        draw.line((x + 8, y + 38, x + 44, y + 38), fill=color, width=4)
        draw.line((x + 10, y + 32, x + 22, y + 20, x + 32, y + 26, x + 44, y + 10), fill=color, width=4)
    else:
        draw.pieslice((x + 6, y + 6, x + 42, y + 42), 270, 360, fill=color)
        draw.pieslice((x + 6, y + 6, x + 42, y + 42), 0, 270, fill="#1f6feb")
    draw.text((x + 58, y + 6), title, font=FONT_H2, fill=color)


def draw_amount_top(image, draw, analysis, x, y, w, h):
    labels = analysis.get("labels", {})
    rounded(draw, (x, y, x + w, y + h), CARD, radius=14)
    draw_section_title(draw, x + 20, y + 20, "trophy", labels.get("amount_top", "金额 Top"), BLUE)
    rows = (analysis.get("top_purchases") or [])[:3]
    row_y = y + 86
    for idx, item in enumerate(rows, start=1):
        if idx > 1:
            draw.line((x + 18, row_y - 14, x + w - 18, row_y - 14), fill=LINE, width=1)
        draw.ellipse((x + 20, row_y + 22, x + 52, row_y + 54), fill=BLUE)
        center_text(draw, (x + 20, row_y + 22, x + 52, row_y + 54), str(idx), FONT_BODY, "#ffffff")
        draw_product_thumbnail(image, draw, x + 70, row_y, 92, 74, item)
        title = fit_line(item.get("display_title") or item.get("title", labels.get("untitled", "")), 34)
        text(draw, (x + 178, row_y + 2), title, FONT_BODY, INK, max_chars=28, line_gap=2)
        draw.text((x + 178, row_y + 52), item.get("amount", ""), font=FONT_H3, fill=BLUE)
        draw.text((x + 178, row_y + 78), item.get("category", ""), font=FONT_SMALL, fill=MUTED)
        row_y += 112


def draw_monthly(draw, analysis, x, y, w, h):
    labels = analysis.get("labels", {})
    rounded(draw, (x, y, x + w, y + h), CARD, radius=14)
    draw_section_title(draw, x + 20, y + 20, "chart", labels.get("monthly_ranking", "月度排序"), BLUE)
    rows = (analysis.get("monthly_totals") or [])[:5]
    max_amount = max([parse_amount(item.get("amount", "")) for item in rows] or [0])
    row_y = y + 98
    for item in rows:
        draw.text((x + 20, row_y), item.get("month", ""), font=FONT_BODY, fill=INK)
        bar_x, bar_y, bar_w = x + 102, row_y + 5, 134
        rounded(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + 18), "#edf2f7", outline="#edf2f7", radius=5)
        width = max(4, int(bar_w * parse_amount(item.get("amount", "")) / max_amount)) if max_amount else 4
        rounded(draw, (bar_x, bar_y, bar_x + width, bar_y + 18), BLUE, outline=BLUE, radius=5)
        draw.text((x + 252, row_y), item.get("amount", ""), font=FONT_BODY, fill=BLUE)
        if analysis.get("language") == "en":
            count = f"{item.get('order_count', 0)} orders, {item.get('item_count', 0)} items"
        else:
            count = f"{item.get('order_count', 0)} 个订单，{item.get('item_count', 0)} 件物品"
        draw.text((x + 362, row_y), count, font=FONT_SMALL, fill=MUTED)
        row_y += 62


def draw_category_icon(draw, x, y, category_key):
    draw.ellipse((x, y, x + 58, y + 58), fill=BLUE_BG)
    if "Health" in category_key:
        draw.line((x + 12, y + 32, x + 24, y + 32, x + 30, y + 18, x + 40, y + 42, x + 46, y + 26), fill=MUTED, width=4)
    elif "Hobbies" in category_key:
        draw.polygon([(x + 29, y + 13), (x + 48, y + 24), (x + 29, y + 35), (x + 10, y + 24)], fill=BLUE)
        draw.polygon([(x + 10, y + 28), (x + 29, y + 39), (x + 29, y + 51), (x + 10, y + 40)], fill="#2f7cf0")
    elif "Office" in category_key:
        draw.polygon([(x + 18, y + 43), (x + 42, y + 19), (x + 48, y + 25), (x + 24, y + 49)], fill=BLUE)
        draw.rectangle((x + 15, y + 46, x + 28, y + 50), fill=BLUE)
    else:
        draw.polygon([(x + 29, y + 14), (x + 48, y + 31), (x + 40, y + 31), (x + 40, y + 48), (x + 18, y + 48), (x + 18, y + 31), (x + 10, y + 31)], fill=BLUE)


def draw_categories(draw, analysis, x, y, w, h):
    labels = analysis.get("labels", {})
    rounded(draw, (x, y, x + w, y + h), CARD, radius=14)
    draw_section_title(draw, x + 20, y + 20, "pie", labels.get("category_top", "类别 Top"), BLUE)
    row_y = y + 86
    for idx, item in enumerate((analysis.get("category_totals") or [])[:4]):
        if idx:
            draw.line((x + 20, row_y - 14, x + w - 20, row_y - 14), fill=LINE, width=1)
        draw_category_icon(draw, x + 20, row_y, item.get("category_key", ""))
        draw.text((x + 92, row_y + 17), item.get("category", ""), font=FONT_BODY, fill=INK)
        amount = item.get("amount", "")
        bbox = draw.textbbox((0, 0), amount, font=FONT_BODY)
        draw.text((x + w - 24 - (bbox[2] - bbox[0]), row_y + 17), amount, font=FONT_BODY, fill=BLUE)
        row_y += 76


def render_png(analysis: dict, output_path: str, background_path: str | None = None) -> str:
    if background_path and os.path.exists(background_path):
        image = Image.open(background_path).convert("RGBA").resize((W, H))
        overlay = Image.new("RGBA", (W, H), (251, 253, 255, 224))
        image = Image.alpha_composite(image, overlay)
    else:
        image = Image.new("RGBA", (W, H), PAGE)
    draw = ImageDraw.Draw(image)
    labels = analysis.get("labels") or {}
    summary = analysis.get("summary", {})

    draw_title(draw)
    y = 110
    gap = 16
    widths = [354, 290, 290, 438]
    x = MARGIN
    metric(draw, x, y, widths[0], 146, labels.get("total_spend", "总花费"), summary.get("total_spend", ""), "money")
    x += widths[0] + gap
    metric(draw, x, y, widths[1], 146, labels.get("order_count", "订单数"), summary.get("order_count", 0), "bag")
    x += widths[1] + gap
    metric(draw, x, y, widths[2], 146, labels.get("item_count", "物品数"), summary.get("item_count", 0), "cube")
    x += widths[2] + gap
    metric(draw, x, y, widths[3], 146, labels.get("date_range", "日期范围"), summary.get("date_range", ""), "calendar")

    draw_prime(image, draw, analysis, 274)
    bottom_y, bottom_h = 528, 440
    draw_amount_top(image, draw, analysis, MARGIN, bottom_y, 444, bottom_h)
    draw_monthly(draw, analysis, 512, bottom_y, 492, bottom_h)
    draw_categories(draw, analysis, 1020, bottom_y, 464, bottom_h)

    footer = labels.get("safety_footer", "")
    draw.text((MARGIN, H - 36), footer, font=FONT_SMALL, fill=SUBTLE)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    image.convert("RGB").save(output_path, "PNG")
    return output_path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("Usage: build_image_report.py <analysis.json> <output.png> [background.png]")
        return 0
    with open(argv[0], "r", encoding="utf-8") as handle:
        analysis = json.load(handle)
    background = argv[2] if len(argv) > 2 else None
    print(render_png(analysis, argv[1], background))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
