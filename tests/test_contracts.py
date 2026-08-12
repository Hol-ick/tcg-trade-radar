import unittest

from kaitori_collector.contracts import ExtractedRow, JobRequest, to_public_row


class ContractTests(unittest.TestCase):
    def test_public_row_uses_string_shipping_contract(self):
        row = ExtractedRow(
            gallery_id="tcggame",
            post_title="판매 카드",
            post_url="https://example.test/post/1",
            posted_at="2026-08-12T10:00:00+09:00",
            card_name="블루아이즈",
            rarity="울레",
            raw_price="3.5",
            price_krw=35000,
            price_unit="만원 단위 추정",
            quantity=1,
            shipping_included=None,
            shipping_price_krw=None,
            review_status="needs_review",
            review_reason="배송비 포함 여부 미확정",
            raw_line="블루아이즈 울레 3.5",
        )

        public = to_public_row(row)

        self.assertEqual(public["shipping_included"], "unknown")
        self.assertEqual(public["price_krw"], 35000)
        self.assertEqual(set(public), set(row.__dataclass_fields__))

    def test_job_request_defaults_and_limits(self):
        request = JobRequest.from_dict({"gallery_id": "tcggame"})

        self.assertEqual(request.subject, "판매")
        self.assertEqual(request.max_posts, 20)
        self.assertEqual(request.buy_rate, 60)
        self.assertTrue(request.keep_raw)
        self.assertTrue(request.review_unmatched)

        with self.assertRaises(ValueError):
            JobRequest.from_dict({"gallery_id": "tcggame", "max_posts": 201})

        with self.assertRaises(ValueError):
            JobRequest.from_dict({"gallery_id": "tcggame", "buy_rate": 101})


if __name__ == "__main__":
    unittest.main()
