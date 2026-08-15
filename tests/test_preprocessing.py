import unittest

from kaitori_collector.preprocessing import analysis_status, classify_post, classify_price, is_likely_artifact


class PreprocessingTests(unittest.TestCase):
    def test_image_only_post_is_context_only(self):
        result = classify_post("카드 일괄 판매", "", image_count=4, row_count=0)
        self.assertEqual(result.status, "image_only")
        self.assertEqual(result.image_count, 4)

    def test_completed_and_reserved_posts_are_not_active(self):
        self.assertEqual(classify_post("블루아이즈 거래완료", "가격 삭제").status, "price_removed")
        self.assertEqual(classify_post("블루아이즈 예약중", "").status, "reserved")

    def test_price_states_keep_missing_separate_from_estimated(self):
        self.assertEqual(classify_price(raw_price="", price_unit="", quantity=1, raw_line="블루아이즈 구매", post_status="active")[0], "missing")
        self.assertEqual(classify_price(raw_price="3.5", price_unit="만원 단위 추정", quantity=1, raw_line="블루아이즈 3.5", post_status="active")[0], "estimated")
        self.assertEqual(classify_price(raw_price="", price_unit="", quantity=1, raw_line="블루아이즈 거래완료", post_status="completed")[0], "removed")

    def test_bundle_and_multi_quantity_are_not_card_prices(self):
        self.assertEqual(classify_price(raw_price="10", price_unit="만원 단위 추정", quantity=1, raw_line="블루아이즈 일괄 10", post_status="active")[1], "bundle")
        self.assertEqual(classify_price(raw_price="4.5", price_unit="만원 단위 추정", quantity=3, raw_line="스파크 3장 4.5", post_status="active")[1], "per_quantity")

    def test_only_active_per_card_rows_are_usable(self):
        self.assertEqual(analysis_status(post_status="active", listing_type="sell", card_name="블루아이즈", price_status="exact", price_scope="per_card"), "usable")
        self.assertEqual(analysis_status(post_status="active", listing_type="sell", card_name="블루아이즈", price_status="estimated", price_scope="per_card"), "needs_review")
        self.assertEqual(analysis_status(post_status="active", listing_type="sell", card_name="블루아이즈", price_status="missing", price_scope="unknown"), "needs_review")
        self.assertEqual(analysis_status(post_status="completed", listing_type="sell", card_name="블루아이즈", price_status="exact", price_scope="per_card"), "context_only")

    def test_script_and_ad_fragments_are_excluded_from_market_analysis(self):
        self.assertTrue(is_likely_artifact("loadScript('https://pagead.example/ad.js')"))
        self.assertTrue(is_likely_artifact("DOM 삽입 헬퍼 현재 스크립트 위치 기준"))
        self.assertTrue(is_likely_artifact("등포"))
        self.assertTrue(is_likely_artifact("한 장"))
        self.assertTrue(is_likely_artifact("장당"))
        self.assertTrue(is_likely_artifact("일괄시"))
        self.assertTrue(is_likely_artifact("준등포 2만"))
        self.assertTrue(is_likely_artifact("1.5 0.5 1.0"))
        self.assertEqual(
            analysis_status(
                post_status="active",
                listing_type="sell",
                card_name="var safe = window.dcAd && window.dcAd.safe ==",
                price_status="exact",
                price_scope="per_card",
            ),
            "excluded",
        )


if __name__ == "__main__":
    unittest.main()
