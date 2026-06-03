import json
import os
import tempfile
import unittest

from PIL import Image

import organize_orders


class OrganizeOrdersTests(unittest.TestCase):
    def write_csv(self, content):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        handle.write(content)
        handle.close()
        return handle.name

    def test_orders_are_normalized_without_tier_grading(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,ASIN,Order Status\n"
            "2026-01-05,111-1111111-1111111,USB-C Cable,2,$19.98,B000CABLE,Shipped\n"
            ",222-2222222-2222222,Unknown Desk Part,1,$42.00,B000PART,Shipped\n"
            "2026-01-08,333-3333333-3333333,Digital Gift Card,1,$100.00,B000GIFT,Shipped\n"
        )

        analysis = organize_orders.build_analysis([csv_path])

        self.assertEqual(analysis["summary"]["order_count"], 3)
        self.assertEqual(analysis["summary"]["item_count"], 4)
        self.assertNotIn("tier_counts", analysis["summary"])
        self.assertNotIn("tiers", analysis)
        self.assertEqual([item["order_id"] for item in analysis["orders"]], [
            "111-1111111-1111111",
            "222-2222222-2222222",
            "333-3333333-3333333",
        ])
        self.assertEqual(analysis["orders"][0]["category_key"], "Electronics")
        self.assertEqual(analysis["orders"][0]["category"], "电子产品")
        self.assertEqual(analysis["orders"][2]["category_key"], "Gift Cards & Digital")
        self.assertEqual(analysis["orders"][2]["category"], "礼品卡与数字内容")

    def test_cli_writes_json_and_html_report(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Shipping Savings\n"
            "2026-02-01,444-4444444-4444444,Notebook,3,$15.00,$7.99\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "amazon-analysis.json")
            html_path = os.path.join(tmp, "amazon-report.html")
            image_prompt_path = os.path.join(tmp, "amazon-image-prompt.txt")
            png_path = os.path.join(tmp, "amazon-report.png")

            exit_code = organize_orders.main([
                csv_path,
                "--json",
                json_path,
                "--html",
                html_path,
                "--image-prompt",
                image_prompt_path,
                "--png",
                png_path,
                "--year",
                "2026",
                "--prime-cost",
                "9.99",
            ])

            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(json_path))
            self.assertTrue(os.path.exists(html_path))
            self.assertTrue(os.path.exists(png_path))
            self.assertGreater(os.path.getsize(png_path), 10_000)
            with Image.open(png_path) as image:
                self.assertEqual(image.size, (1536, 1024))
            with open(json_path, "r", encoding="utf-8") as handle:
                analysis = json.load(handle)
            self.assertEqual(analysis["summary"]["order_count"], 1)
            self.assertEqual(analysis["prime_value"]["membership_cost"], "AUD 9.99")
            self.assertEqual(analysis["prime_value"]["shipping_savings_identified"], "AUD 7.99")
            self.assertEqual(analysis["prime_value"]["net_value"], "AUD -2.00")
            self.assertEqual(analysis["labels"]["total_spend"], "总花费")
            self.assertEqual(analysis["labels"]["net_value"], "已省下")
            self.assertEqual(analysis["labels"]["shipping_paid"], "运费")
            self.assertTrue(os.path.exists(image_prompt_path))
            with open(html_path, "r", encoding="utf-8") as handle:
                html = handle.read()
            self.assertIn("Amazon Purchase Organizer", html)
            self.assertIn("Notebook", html)
            self.assertIn("Prime 价值判断", html)
            self.assertIn("月度排序", html)
            self.assertIn('class="report-frame"', html)
            self.assertIn("aspect-ratio:3/2", html)
            self.assertIn("renderExactReport", html)
            self.assertIn("prime-badge", html)
            self.assertIn("report-hero", html)
            self.assertIn("metric-icon", html)
            self.assertIn("prime-shield-wrap", html)
            self.assertIn("prime-shield", html)
            self.assertIn("prime-crown", html)
            self.assertIn("prime-word", html)
            self.assertIn("prime-sparkle", html)
            self.assertIn("product-photo", html)
            self.assertIn("monthly-bar", html)
            self.assertNotIn("数据口径", html)
            self.assertNotIn("订单分级", html)
            self.assertNotIn("绿灯", html)
            self.assertNotIn("黄灯", html)
            self.assertNotIn("红灯", html)
            with open(image_prompt_path, "r", encoding="utf-8") as handle:
                prompt = handle.read()
            self.assertIn("Use case: infographic-diagram", prompt)
            self.assertIn("3:2", prompt)
            self.assertIn("Prime 价值判断", prompt)
            self.assertIn("月度排序", prompt)
            self.assertIn("总花费", prompt)
            self.assertIn("已省下", prompt)
            self.assertIn("运费", prompt)
            self.assertNotIn("分级", prompt)
            self.assertNotIn("绿灯", prompt)

    def test_cli_defaults_to_local_html_report(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total\n"
            "2026-02-01,444-4444444-4444444,Notebook,3,$15.00\n"
        )

        args = organize_orders.parse_args([csv_path])

        self.assertTrue(args.html.endswith("amazon-purchase-report.html"))

    def test_shipping_costs_are_compared_to_prime_membership_for_year(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Shipping Savings,Shipping Charge\n"
            "5 January 2026,111-1111111-1111111,USB-C Cable,1,$19.98,$9.99,$0.00\n"
            "2026-03-10,222-2222222-2222222,Notebook,2,$15.00,$5.50,$0.00\n"
            "2025-12-20,333-3333333-3333333,Desk Lamp,1,$35.00,$12.00,$0.00\n"
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026, prime_cost="79")

        self.assertEqual(analysis["prime_value"]["year"], 2026)
        self.assertEqual(analysis["prime_value"]["orders_with_shipping_savings"], 2)
        self.assertEqual(analysis["prime_value"]["shipping_savings_identified"], "AUD 15.49")
        self.assertEqual(analysis["prime_value"]["hypothetical_non_member_shipping"], "AUD 15.49")
        self.assertEqual(analysis["prime_value"]["non_member_shipping_basis"], "shipping_savings")
        self.assertEqual(analysis["prime_value"]["shipping_paid_identified"], "AUD 0.00")
        self.assertEqual(analysis["prime_value"]["membership_cost"], "AUD 79.00")
        self.assertEqual(analysis["prime_value"]["net_value"], "AUD -63.51")
        self.assertEqual(analysis["prime_value"]["status"], "not_yet_recovered")
        self.assertIn("还差 AUD 63.51", analysis["prime_value"]["verdict"])
        self.assertEqual(analysis["prime_value"]["visual"], {
            "tone": "red",
            "emoji": "😭",
            "label": "未值回会员费",
        })
        self.assertIn("结论: 😭 未值回会员费", analysis["image_prompt"])
        self.assertEqual(analysis["monthly_totals"], [
            {"month": "2026-03", "amount": "AUD 15.00", "order_count": 1, "item_count": 2},
            {"month": "2026-01", "amount": "AUD 19.98", "order_count": 1, "item_count": 1},
            {"month": "2025-12", "amount": "AUD 35.00", "order_count": 1, "item_count": 1},
        ])

    def test_top_purchase_titles_are_shortened_without_changing_order_title(self):
        long_title = (
            "LEGO Art Hokusai – The Great Wave Building Set for Adults, "
            "Japanese Wall Art Model Kit, Creative Crafts Activity"
        )
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total\n"
            f'2026-05-19,555-5555555-5555555,"{long_title}",1,$155.20\n'
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026)

        self.assertEqual(analysis["orders"][0]["title"], long_title)
        self.assertEqual(
            analysis["top_purchases"][0]["display_title"],
            "LEGO Art Hokusai - The Great Wave Building Set",
        )
        self.assertLessEqual(len(analysis["top_purchases"][0]["display_title"]), 52)
        self.assertIn("LEGO Art Hokusai - The Great Wave Building Set", analysis["image_prompt"])
        self.assertNotIn("Japanese Wall Art Model Kit", analysis["image_prompt"])

    def test_top_purchases_include_product_images_or_generated_thumbnails(self):
        provided_image = "data:image/png;base64,iVBORw0KGgo="
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Image URL\n"
            f'2026-05-19,555-5555555-5555555,LEGO Art Hokusai Great Wave,1,$155.20,"{provided_image}"\n'
            "2026-05-20,666-6666666-6666666,Scivation Xtend BCAA Powder,1,$91.62,\n"
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026)
        top = analysis["top_purchases"]

        self.assertEqual(top[0]["product_image"], provided_image)
        self.assertEqual(top[0]["product_image_source"], "provided")
        self.assertTrue(top[1]["product_image"].startswith("data:image/svg+xml;base64,"))
        self.assertEqual(top[1]["product_image_source"], "generated")
        self.assertIn("商品图片", top[1]["product_image_alt"])
        self.assertIn("product photos or generated thumbnails", analysis["image_prompt"])

    def test_report_headers_follow_requested_language(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Shipping Savings\n"
            "2026-02-01,444-4444444-4444444,Notebook,3,$15.00,$7.99\n"
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026, prime_cost="9.99", language="en")

        self.assertEqual(analysis["language"], "en")
        self.assertEqual(analysis["labels"]["amount_top"], "Amount Top")
        self.assertEqual(analysis["labels"]["monthly_ranking"], "Monthly Ranking")
        self.assertEqual(analysis["labels"]["total_spend"], "Total Spend")
        self.assertEqual(analysis["labels"]["net_value"], "Saved")
        self.assertEqual(analysis["labels"]["shipping_paid"], "Shipping")
        self.assertEqual(analysis["summary"]["date_range"], "2026-02-01 to 2026-02-01")
        self.assertEqual(analysis["top_purchases"][0]["category_key"], "Office")
        self.assertEqual(analysis["top_purchases"][0]["category"], "Office")
        self.assertIn("Prime Value:", analysis["image_prompt"])
        self.assertIn("Amount Top:", analysis["image_prompt"])
        self.assertIn("Monthly Ranking:", analysis["image_prompt"])
        self.assertNotIn(" 至 ", analysis["image_prompt"])
        self.assertNotIn("Prime 价值判断:", analysis["image_prompt"])
        self.assertNotIn("金额 Top:", analysis["image_prompt"])
        self.assertNotIn("月度排序:", analysis["image_prompt"])

    def test_prime_value_can_use_assumed_non_member_shipping_per_order(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Order Status\n"
            "2026-01-05,111-1111111-1111111,USB-C Cable,1,$19.98,Shipped\n"
            "2026-02-10,222-2222222-2222222,Notebook,2,$15.00,Shipped\n"
            "2026-03-10,333-3333333-3333333,Cancelled Item,1,$0.00,Cancelled\n"
        )

        analysis = organize_orders.build_analysis(
            [csv_path],
            report_year=2026,
            prime_cost="79",
            non_member_shipping_per_order="9.99",
        )

        self.assertEqual(analysis["prime_value"]["hypothetical_non_member_shipping"], "AUD 19.98")
        self.assertEqual(analysis["prime_value"]["orders_with_hypothetical_shipping"], 2)
        self.assertEqual(analysis["prime_value"]["non_member_shipping_basis"], "estimated_per_order")
        self.assertEqual(analysis["prime_value"]["net_value"], "AUD -59.02")
        self.assertEqual(analysis["prime_value"]["status"], "not_yet_recovered")
        self.assertIn("按每单 AUD 9.99 假设", analysis["prime_value"]["verdict"])
        self.assertEqual(analysis["prime_value"]["visual"]["tone"], "red")
        self.assertEqual(analysis["prime_value"]["visual"]["emoji"], "😭")

    def test_recovered_prime_value_uses_green_thumb_visual(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total\n"
            "2026-01-05,111-1111111-1111111,USB-C Cable,1,$19.98\n"
            "2026-02-10,222-2222222-2222222,Notebook,2,$15.00\n"
        )

        analysis = organize_orders.build_analysis(
            [csv_path],
            report_year=2026,
            prime_cost="10",
            non_member_shipping_per_order="9.99",
        )

        self.assertEqual(analysis["prime_value"]["status"], "recovered")
        self.assertEqual(analysis["prime_value"]["visual"], {
            "tone": "green",
            "emoji": "👍",
            "label": "已值回会员费",
        })
        self.assertIn("结论: 👍 已值回会员费", analysis["image_prompt"])

    def test_categories_are_distinguished_without_uncategorized_bucket(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total\n"
            "2026-01-01,111,LEGO Art Hokusai - The Great Wave Building Set,1,$155.20\n"
            "2026-01-02,222,Scivation Xtend BCAA Powder Blue Raspberry,1,$91.62\n"
            "2026-01-03,333,MOUNTUP Dual Monitor Stand for Desk,1,$56.99\n"
            "2026-01-04,444,Durex Latex-Free Condoms 10 pack,1,$10.00\n"
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026)
        categories = [item["category"] for item in analysis["orders"]]
        category_keys = [item["category_key"] for item in analysis["orders"]]

        self.assertEqual(categories, ["兴趣玩具", "健康健身", "办公", "个人护理"])
        self.assertEqual(category_keys, ["Hobbies & Toys", "Health & Fitness", "Office", "Personal Care"])
        self.assertNotIn("Uncategorized", categories)
        self.assertNotIn("Uncategorized", [item["category"] for item in analysis["category_totals"]])
        self.assertNotIn("无法分类", categories)

    def test_monthly_prime_plan_is_auto_detected_and_compared_to_annual(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total\n"
            "2026-01-01,p1,Amazon Prime Membership,1,$9.99\n"
            "2026-02-01,p2,Amazon Prime Membership,1,$9.99\n"
            "2026-02-10,111,Notebook,1,$15.00\n"
        )

        analysis = organize_orders.build_analysis(
            [csv_path],
            report_year=2026,
            prime_plan="auto",
            prime_annual_cost="79",
            prime_monthly_cost="9.99",
            non_member_shipping_per_order="9.99",
        )

        self.assertEqual(analysis["prime_value"]["membership_plan"], "monthly")
        self.assertEqual(analysis["prime_value"]["membership_cost"], "AUD 19.98")
        self.assertEqual(analysis["prime_value"]["membership_paid_months"], 2)
        self.assertEqual(analysis["prime_value"]["monthly_annualized_cost"], "AUD 119.88")
        self.assertEqual(analysis["prime_value"]["annual_plan_difference"], "AUD 40.88")
        self.assertIn("年费可省 AUD 40.88", analysis["prime_value"]["annual_plan_verdict"])
        self.assertIn("年费对比: 年费可省 AUD 40.88", analysis["image_prompt"])

    def test_shipping_charges_without_savings_are_not_treated_as_prime_savings(self):
        csv_path = self.write_csv(
            "Order Date,Order ID,Title,Quantity,Item Total,Shipping Charge\n"
            "2026-01-05,111-1111111-1111111,USB-C Cable,1,$19.98,$9.99\n"
        )

        analysis = organize_orders.build_analysis([csv_path], report_year=2026, prime_cost="79")

        self.assertEqual(analysis["prime_value"]["shipping_paid_identified"], "AUD 9.99")
        self.assertEqual(analysis["prime_value"]["shipping_savings_identified"], "AUD 0.00")
        self.assertEqual(analysis["prime_value"]["hypothetical_non_member_shipping"], "AUD 0.00")
        self.assertEqual(analysis["prime_value"]["status"], "insufficient_hypothetical_data")
        self.assertIn("没有无会员运费假设", analysis["prime_value"]["verdict"])

    def test_full_english_month_dates_are_parsed(self):
        self.assertEqual(organize_orders.canonical_date("31 January 2026"), "2026-01-31")
        self.assertEqual(organize_orders.canonical_date("7 February 2026"), "2026-02-07")


if __name__ == "__main__":
    unittest.main()
