import unittest

from kaitori_collector.normalization import normalize_listing_card_label


class NormalizationTests(unittest.TestCase):
    def test_removes_trade_suffix_quantity_and_price_from_buy_label(self):
        self.assertEqual(normalize_listing_card_label("골디온 2장 0.6", "buy"), "골디온")
        self.assertEqual(normalize_listing_card_label("삼영의 상검사 산다이온 구합니다", "buy"), "삼영의 상검사 산다이온")

    def test_sell_and_buy_labels_share_a_key(self):
        self.assertEqual(
            normalize_listing_card_label("파멜라 판매 16,000원", "sell"),
            normalize_listing_card_label("파멜라 구해요", "buy"),
        )

    def test_preserves_card_numbers_and_codes(self):
        self.assertEqual(normalize_listing_card_label("No.39 유토피아 시크", "sell"), "No.39 유토피아 시크")
        self.assertEqual(normalize_listing_card_label("OP01-001 루피 2장", "sell"), "OP01-001 루피")

    def test_does_not_turn_trade_only_text_into_a_card(self):
        self.assertEqual(normalize_listing_card_label("구매합니다", "buy"), "")
        self.assertEqual(normalize_listing_card_label("", "sell"), "")


if __name__ == "__main__":
    unittest.main()
