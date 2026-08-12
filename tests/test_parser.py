import gzip
import unittest
from unittest.mock import patch

from kaitori_collector.html import DCInsideHTMLParser, parse_html
from kaitori_collector.parser import (
    SourceResponseError,
    build_list_url,
    extract_gallery,
    extract_post,
    fetch_text,
    fetch_text_auto,
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
