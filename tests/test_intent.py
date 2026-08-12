import unittest

from kaitori_collector.intent import classify_listing


class IntentTests(unittest.TestCase):
    def test_buy_post_without_price_is_demand(self):
        result = classify_listing("블루아이즈 구해요", "상태 좋은 카드 찾습니다", "거래")

        self.assertEqual(result.listing_type, "buy")
        self.assertEqual(result.price_type, "wanted")
        self.assertGreater(result.confidence, 0.8)

    def test_trade_subject_without_text_is_not_sale(self):
        result = classify_listing("카드 교환", "원하는 카드와 교환합니다", "거래")

        self.assertEqual(result.listing_type, "trade")
        self.assertEqual(result.price_type, "unknown")

    def test_conflicting_signals_require_review(self):
        result = classify_listing("블루아이즈 팝니다", "이 카드는 구합니다", "거래")

        self.assertEqual(result.listing_type, "unknown")
        self.assertLess(result.confidence, 0.5)

    def test_sale_subject_is_only_a_low_confidence_fallback(self):
        result = classify_listing("카드 나눔", "내용 확인", "판매")

        self.assertEqual(result.listing_type, "sell")
        self.assertLess(result.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
