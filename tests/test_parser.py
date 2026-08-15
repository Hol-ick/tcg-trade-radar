import gzip
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from kaitori_collector.browser_transport import BrowserTransportError
from kaitori_collector.html import DCInsideHTMLParser, parse_html
from kaitori_collector.parser import (
    SourceResponseError,
    build_list_url,
    extract_gallery,
    extract_post,
    fetch_text,
    fetch_text_auto,
    is_dcinside_public_url,
    mobile_url_for,
    parse_sale_line,
)


class _EmptyResponse:
    status = 200

    class _Headers:
        def get_content_charset(self):
            return "utf-8"

        def get(self, name):
            return {"Content-Length": "0", "Server": "nginx"}.get(name)

    headers = _Headers()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b""


class _CompressedResponse:
    status = 200

    class _Headers:
        def get_content_charset(self):
            return "utf-8"

        def get(self, name):
            return {"Content-Encoding": "gzip", "Content-Length": "42", "Server": "nginx"}.get(name)

    headers = _Headers()

    def __init__(self, body):
        self.body = gzip.compress(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class ParserTests(unittest.TestCase):
    def test_mobile_url_for_desktop_list_and_post(self):
        self.assertEqual(
            mobile_url_for("https://gall.dcinside.com/mgallery/board/lists?id=tcggame&page=2"),
            "https://m.dcinside.com/board/tcggame?page=2",
        )
        self.assertEqual(
            mobile_url_for("https://gall.dcinside.com/mgallery/board/view/?id=tcggame&no=4305567"),
            "https://m.dcinside.com/board/tcggame/4305567",
        )

    def test_dcinside_public_url_detection(self):
        self.assertTrue(is_dcinside_public_url("https://gall.dcinside.com/mgallery/board/lists?id=tcggame"))
        self.assertTrue(is_dcinside_public_url("https://m.dcinside.com/board/tcggame"))
        self.assertFalse(is_dcinside_public_url("https://example.test/list"))

    def test_dcinside_auto_transport_uses_mobile_before_desktop(self):
        mobile_html = '''
        <!DOCTYPE html><html><body><ul class="gall-detail-lst">
          <li><div class="gall-detail-lnktb"><a class="lt" href="/board/tcggame/1">
            <ul class="ginfo"><li>판매</li></ul>
          </a></div></li>
        </ul></body></html>
        '''
        url = "https://gall.dcinside.com/mgallery/board/lists?id=tcggame"
        with patch("kaitori_collector.parser.fetch_text_mobile", return_value=mobile_html) as mobile:
            with patch("kaitori_collector.parser.fetch_text") as desktop:
                self.assertEqual(fetch_text_auto(url), mobile_html)
                mobile.assert_called_once()
                desktop.assert_not_called()

    def test_auto_transport_tries_mobile_after_empty_http_response(self):
        mobile_html = "<html><body>mobile gallery</body></html>"
        http_error = SourceResponseError(
            "https://example.test/list",
            status=200,
            content_length="0",
            server="nginx",
        )
        with patch("kaitori_collector.parser.fetch_text", side_effect=http_error):
            with patch("kaitori_collector.parser.fetch_text_mobile", return_value=mobile_html) as mobile:
                self.assertEqual(fetch_text_auto("https://example.test/list"), mobile_html)
                mobile.assert_called_once()

    def test_auto_transport_rejects_unrecognized_mobile_shape_before_browser(self):
        mobile_html = "<!DOCTYPE html><html><body>challenge</body></html>"
        browser_html = '<!DOCTYPE html><table><tr><td class="gall_subject">판매</td></tr></table>'
        http_error = SourceResponseError(
            "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
            status=200,
            content_length="0",
            server="nginx",
        )
        with patch("kaitori_collector.parser.fetch_text", side_effect=http_error):
            with patch("kaitori_collector.parser.fetch_text_mobile", return_value=mobile_html):
                with patch("kaitori_collector.parser.fetch_text_browser", return_value=browser_html) as browser:
                    self.assertEqual(fetch_text_auto(http_error.url), browser_html)
                    browser.assert_called_once()

    def test_auto_transport_rejects_unrecognized_desktop_shape_before_mobile(self):
        desktop_html = "<!DOCTYPE html><html><head><title>잠시만 기다려 주세요</title></head><body>retry</body></html>"
        mobile_html = '''
        <html><body><table><tr>
          <td class="gall_subject">판매</td>
          <td><a class="gall_tit" href="/mgallery/board/view/?id=tcggame&amp;no=1">첫 글</a></td>
        </tr></table></body></html>
        '''
        url = "https://gall.dcinside.com/mgallery/board/lists?id=tcggame"
        with patch("kaitori_collector.parser.fetch_text", return_value=desktop_html):
            with patch("kaitori_collector.parser.fetch_text_mobile", return_value=mobile_html) as mobile:
                with patch("kaitori_collector.parser.fetch_text_browser") as browser:
                    self.assertEqual(fetch_text_auto(url), mobile_html)
                    mobile.assert_called_once()
                    browser.assert_not_called()

    def test_auto_transport_does_not_return_unrecognized_browser_shape(self):
        invalid_html = "<!DOCTYPE html><html><head><title>retry</title></head><body>retry</body></html>"
        url = "https://gall.dcinside.com/mgallery/board/lists?id=tcggame"
        with patch("kaitori_collector.parser.fetch_text", return_value=invalid_html):
            with patch("kaitori_collector.parser.fetch_text_mobile", return_value=invalid_html):
                with patch("kaitori_collector.parser.fetch_text_browser", return_value=invalid_html):
                    with self.assertRaises(SourceResponseError) as context:
                        fetch_text_auto(url)
        self.assertIn("response-shape-unrecognized", context.exception.fallback_error)

    def test_mobile_list_rows_are_parsed(self):
        html = '''
        <ul class="gall-detail-lst">
          <li><div class="gall-detail-lnktb">
            <a class="lt" href="https://m.dcinside.com/board/tcggame/1">
              <span class="subject-add"><span class="subjectin">카드 팝니다</span></span>
              <ul class="ginfo"><li>판매</li><li class="list-nick">카드상인<span class="sp-nick gonick"></span></li></ul>
            </a>
          </div></li>
        </ul>
        '''
        parser = DCInsideHTMLParser()
        parser.feed(html)

        self.assertEqual(len(parser.list_rows), 1)
        self.assertEqual(parser.list_rows[0]["subject"], "판매")
        self.assertEqual(parser.list_rows[0]["href"], "https://m.dcinside.com/board/tcggame/1")

    def test_mobile_post_marker_sets_guest_author_type(self):
        html = '''
        <div class="gallview-tit-box">
          <div class="ginfo-area"><button class="nick">Maki</button><span class="sp-nick nogonick"></span></div>
        </div>
        <div class="thum-txtin">블루아이즈 3.5</div>
        '''

        document, _ = parse_html(html, "https://m.dcinside.com/board/tcggame/1")

        self.assertEqual(document["author_name"], "Maki")
        self.assertEqual(document["author_type"], "guest")

    def test_auto_transport_falls_back_to_browser_after_empty_http_response(self):
        browser_html = '<html><body><table><tr><td class="gall_subject">판매</td></tr></table></body></html>'
        http_error = SourceResponseError(
            "https://example.test/list",
            status=200,
            content_length="0",
            server="nginx",
        )
        with patch("kaitori_collector.parser.fetch_text", side_effect=http_error):
            with patch("kaitori_collector.parser.fetch_text_browser", return_value=browser_html):
                self.assertEqual(fetch_text_auto("https://example.test/list"), browser_html)

    def test_auto_transport_preserves_http_error_when_browser_fallback_fails(self):
        url = "https://gall.dcinside.com/mgallery/board/lists?id=vg"
        desktop_error = HTTPError(url, 403, "blocked", {}, None)
        browser_error = BrowserTransportError(
            url,
            status=None,
            characters=0,
            title="",
            reason="browser dns failure",
        )
        with patch("kaitori_collector.parser.fetch_text", side_effect=desktop_error):
            with patch("kaitori_collector.parser.fetch_text_mobile", side_effect=OSError("mobile dns failure")):
                with patch("kaitori_collector.parser.fetch_text_browser", side_effect=browser_error):
                    with self.assertRaises(SourceResponseError) as context:
                        fetch_text_auto(url)
        self.assertEqual(context.exception.status, 403)
        self.assertIn("mobile dns failure", context.exception.fallback_error)

    def test_empty_source_response_exposes_http_diagnostics(self):
        with patch("kaitori_collector.parser.urlopen", return_value=_EmptyResponse()):
            with self.assertRaises(SourceResponseError) as context:
                fetch_text("https://gall.dcinside.com/mgallery/board/lists/?id=tcggame")

        error = context.exception
        self.assertIn("status=200", str(error))
        self.assertEqual(error.as_dict()["content_length"], "0")

    def test_fetch_text_decodes_gzip_http_response_before_parsing(self):
        html = '<table><tr><td class="gall_subject">판매</td></tr></table>'.encode()
        with patch("kaitori_collector.parser.urlopen", return_value=_CompressedResponse(html)):
            self.assertEqual(fetch_text("https://example.test/list"), html.decode())

    def test_extract_post_keeps_public_author_marker(self):
        html = '''
        <div class="w_top_left"><dl><dt>글쓴이</dt><dd><span class="nickname" user_name="카드상인" user_id="carddealer">카드상인</span></dd></dl></div>
        <span class="title_subject">판매 카드</span><div class="write_div">블루아이즈 3.5</div>
        '''

        document, _ = parse_html(html, "https://example.test/post/1")

        self.assertEqual(document["author_name"], "카드상인")
        self.assertEqual(document["author_type"], "registered")

    def test_guest_author_is_classified_without_preserving_ip(self):
        html = '''
        <div class="w_top_left"><dl><dt>글쓴이</dt><dd><span class="nickname">ㅇㅇ(39.7)</span></dd></dl></div>
        <span class="title_subject">판매 카드</span><div class="write_div">블루아이즈 3.5</div>
        '''

        document, _ = parse_html(html, "https://example.test/post/1")

        self.assertEqual(document["author_type"], "guest")
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

    def test_attached_copy_count_is_not_ten_thousand_won_price(self):
        row = parse_sale_line("이상한사탕1", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "이상한사탕")
        self.assertEqual(row["quantity"], 1)
        self.assertEqual(row["raw_price"], "")
        self.assertEqual(row["price_krw"], 0)
        self.assertEqual(row["price_status"], "missing")
        self.assertEqual(row["price_scope"], "unknown")
        self.assertIn("수량 표기 감지", row["review_reason"])

    def test_x_quantity_marker_is_not_ten_thousand_won_price(self):
        row = parse_sale_line("나옹 x 2", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "나옹")
        self.assertEqual(row["quantity"], 2)
        self.assertEqual(row["price_status"], "missing")
        self.assertEqual(row["price_krw"], 0)

    def test_attached_copy_count_is_split_before_a_won_amount(self):
        row = parse_sale_line("하솔3 3500", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "하솔")
        self.assertEqual(row["quantity"], 3)
        self.assertEqual(row["raw_price"], "3500")
        self.assertEqual(row["price_krw"], 3500)
        self.assertEqual(row["price_unit"], "원 단위 추정")
        self.assertEqual(row["price_scope"], "per_quantity")

    def test_quantity_before_price_is_not_used_as_the_price(self):
        row = parse_sale_line("레드카드 1 2000", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "레드카드")
        self.assertEqual(row["quantity"], 1)
        self.assertEqual(row["raw_price"], "2000")
        self.assertEqual(row["price_krw"], 2000)

    def test_multiple_attached_copy_counts_are_not_collapsed_into_a_price(self):
        row = parse_sale_line("파도타기비치sr1 일반1", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "파도타기비치sr 일반")
        self.assertEqual(row["quantity"], 2)
        self.assertEqual(row["price_status"], "missing")
        self.assertEqual(row["price_krw"], 0)

    def test_unitless_four_digit_amount_is_won_estimate(self):
        row = parse_sale_line("블루아이즈 3500", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["price_krw"], 3500)
        self.assertEqual(row["price_unit"], "원 단위 추정")

    def test_inventory_post_uses_context_to_classify_spaced_copy_counts(self):
        html = """
        <html><body>
          <span class="title_subject">덱소스 일괄판매</span>
          <div class="write_div">이상한사탕1<br>고래킹 3<br>나옹 x 2</div>
        </body></html>
        """

        rows = extract_post(html, "https://example.test/post/inventory", "pokemoncardgame", "판매")

        self.assertEqual([row.card_name for row in rows], ["이상한사탕", "고래킹", "나옹"])
        self.assertEqual([row.quantity for row in rows], [1, 3, 2])
        self.assertTrue(all(row.price_krw == 0 for row in rows))
        self.assertTrue(all(row.price_status == "missing" for row in rows))

    def test_set_code_digits_are_not_treated_as_copy_counts(self):
        row = parse_sale_line("bt-24 아이기오몬 슈레 1장 구합니다", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["quantity"], 1)

    def test_decimal_before_per_card_marker_is_not_split_as_a_quantity(self):
        row = parse_sale_line("ex9 글판 파워드라몬 시크 1.6 장당 구함다", None, None)

        self.assertIsNone(row)

    def test_set_code_inside_parenthesized_status_is_not_split_as_a_quantity(self):
        row = parse_sale_line("(완료)ex9 파워드라몬 희소 구매합니다.", None, None)

        self.assertIsNone(row)

    def test_set_code_prefix_does_not_add_to_explicit_card_quantity(self):
        row = parse_sale_line("Lm2 매그너몬 1장 0.05", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["quantity"], 1)

    def test_explicit_won_and_shipping_included_can_be_parsed(self):
        row = parse_sale_line("블루아이즈 울레 35,000원 택포", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["price_krw"], 35000)
        self.assertEqual(row["price_unit"], "원 명시")
        self.assertTrue(row["shipping_included"])
        self.assertEqual(row["shipping_price_krw"], 2000)
        self.assertEqual(row["review_status"], "parsed")

    def test_taekpo_before_price_and_trailing_request_are_parsed(self):
        row = parse_sale_line("판스메르미아 4장 택포 7에 구해봅니다", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "판스메르미아")
        self.assertEqual(row["quantity"], 4)
        self.assertEqual(row["price_krw"], 70000)
        self.assertTrue(row["shipping_included"])
        self.assertEqual(row["shipping_price_krw"], 2000)

    def test_explicit_shipping_fee_overrides_default(self):
        row = parse_sale_line("블루아이즈 35,000원 택포", None, 1800)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["shipping_price_krw"], 1800)

    def test_decimal_attached_to_card_name_is_not_truncated_to_integer_price(self):
        row = parse_sale_line("택포 1.4야노망 Z로 추정되는 2중프텍", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["card_name"], "야노망 Z로 추정되는 2중프텍")
        self.assertEqual(row["price_krw"], 14000)
        self.assertEqual(row["price_unit"], "만원 단위 추정")
        self.assertTrue(row["shipping_included"])
        self.assertEqual(row["shipping_price_krw"], 2000)

    def test_unitless_decimal_is_ten_thousand_won_when_card_name_precedes_price(self):
        row = parse_sale_line("야노망 1.4 택포", None, None)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["price_krw"], 14000)

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
        self.assertEqual(rows[0].price_status, "missing")
        self.assertEqual(rows[0].analysis_status, "needs_review")

    def test_completed_post_is_context_only_and_bundle_is_not_a_card_price(self):
        completed = """
        <html><body><span class="title_subject">블루아이즈 거래완료</span><div class="write_div">블루아이즈 울레 35,000원 거래완료</div></body></html>
        """
        bundle = """
        <html><body><span class="title_subject">카드 일괄 판매</span><div class="write_div">블루아이즈, 레드아이즈 일괄 10만원</div></body></html>
        """
        completed_row = extract_post(completed, "https://example.test/post/completed", "tcggame", "판매")[0]
        bundle_row = extract_post(bundle, "https://example.test/post/bundle", "tcggame", "판매")[0]
        self.assertEqual(completed_row.post_status, "completed")
        self.assertEqual(completed_row.analysis_status, "context_only")
        self.assertEqual(bundle_row.price_scope, "bundle")
        self.assertEqual(bundle_row.analysis_status, "needs_review")

    def test_image_only_post_has_no_fake_price_row(self):
        html = '<html><body><span class="title_subject">카드 사진 판매</span><div class="write_div"><img src="https://example.test/card.jpg" /></div></body></html>'
        self.assertEqual(extract_post(html, "https://example.test/post/image", "tcggame", "판매"), [])


if __name__ == "__main__":
    unittest.main()
