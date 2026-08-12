import unittest

from kaitori_collector.parser import build_list_url, extract_gallery, extract_post, parse_sale_line


class ParserTests(unittest.TestCase):
    def test_build_list_url_uses_configured_gallery_url(self):
        url = build_list_url(
            "tcggame",
            2,
            "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
        )

        self.assertEqual(
            url,
            "https://gall.dcinside.com/mgallery/board/lists?id=tcggame&page=2&list_num=50",
        )

    def test_inferred_unit_and_unknown_shipping_need_review(self):
        row = parse_sale_line("블루아이즈 울레 3.5", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["price_krw"], 35000)
        self.assertEqual(row["price_unit"], "만원 단위 추정")
        self.assertIsNone(row["shipping_included"])
        self.assertEqual(row["review_status"], "needs_review")

    def test_explicit_won_and_shipping_included_can_be_parsed(self):
        row = parse_sale_line("블루아이즈 울레 35,000원 택포", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["price_krw"], 35000)
        self.assertEqual(row["price_unit"], "원 명시")
        self.assertTrue(row["shipping_included"])
        self.assertEqual(row["review_status"], "parsed")

    def test_bundle_and_multiple_cards_are_never_auto_approved(self):
        bundle = parse_sale_line("블루아이즈 일괄 10만원 택포", True, None)
        multiple = parse_sale_line("블루아이즈, 레드아이즈 5만원 택포", True, None)

        self.assertIsNotNone(bundle)
        self.assertIsNotNone(multiple)
        assert bundle is not None and multiple is not None
        self.assertEqual(bundle["review_status"], "needs_review")
        self.assertIn("일괄·세트 가격", bundle["review_reason"])
        self.assertEqual(multiple["review_status"], "needs_review")
        self.assertIn("복수 카드 가격", multiple["review_reason"])

    def test_extract_post_keeps_original_metadata_and_marks_image_only_post(self):
        html = """
        <html><head><script type="application/ld+json">
        {"headline":"판매 블루아이즈","datePublished":"2026-08-12T10:00:00+09:00","articleBody":"블루아이즈 울레 35,000원 택포"}
        </script></head><body>
          <span class="title_headtext">판매</span>
          <span class="title_subject">블루아이즈</span>
          <div class="write_div">블루아이즈 울레 35,000원 택포</div>
        </body></html>
        """

        rows = extract_post(html, "https://example.test/post/1", "tcggame")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].post_title, "블루아이즈")
        self.assertEqual(rows[0].post_url, "https://example.test/post/1")
        self.assertEqual(rows[0].posted_at, "2026-08-12T10:00:00+09:00")

    def test_extract_gallery_filters_subject_and_deduplicates_urls(self):
        list_html = """
        <table><tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&no=1">첫 글</a></td></tr>
        <tr><td class="gall_subject">질문</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&no=2">질문</a></td></tr>
        <tr><td class="gall_subject">판매</td><td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&no=1">중복</a></td></tr></table>
        """
        post_html = '<span class="title_subject">첫 글</span><div class="write_div">카드 35,000원 택포</div>'
        calls: list[str] = []

        def fetcher(url: str) -> str:
            calls.append(url)
            return list_html if "lists" in url else post_html

        rows = extract_gallery("tcggame", "판매", 1, 2, 0, fetcher=fetcher)

        self.assertEqual(len(rows), 1)
        self.assertEqual(len([url for url in calls if "view" in url]), 1)

    def test_price_less_buy_post_is_preserved_as_demand_sample(self):
        html = """
        <html><head><script type="application/ld+json">
        {"headline":"블루아이즈 구해요","datePublished":"2026-08-12","articleBody":"블루아이즈 상태 좋은 카드 찾습니다"}
        </script></head><body><span class="title_subject">블루아이즈 구해요</span><div class="write_div">상태 좋은 카드 찾습니다</div></body></html>
        """

        rows = extract_post(html, "https://example.test/post/buy", "tcggame", "거래")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].listing_type, "buy")
        self.assertEqual(rows[0].price_krw, 0)
        self.assertEqual(rows[0].review_reason, "희망가 미기재")


if __name__ == "__main__":
    unittest.main()
