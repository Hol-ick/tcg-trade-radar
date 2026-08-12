import unittest

from kaitori_collector.observability import inspect_source_response, retry_delay


class ObservabilityTests(unittest.TestCase):
    def test_empty_and_blocked_sources_are_not_treated_as_no_posts(self):
        empty = inspect_source_response("", "https://example.test/list", expected="list")
        blocked = inspect_source_response("<html>자동입력 방지</html>", "https://example.test/list", expected="list")

        self.assertEqual(empty.state, "empty")
        self.assertEqual(blocked.state, "blocked")
        self.assertNotEqual(blocked.reason, "정상 응답으로 판별")

    def test_list_structure_is_required(self):
        profile = inspect_source_response("<html><body>정상처럼 보이는 본문</body></html>", "https://example.test/list", expected="list")

        self.assertEqual(profile.state, "structure_changed")

    def test_captcha_asset_in_normal_post_is_not_a_blocked_response(self):
        html = '''
        <html><body>
          <div class="gallview-tit-box">판매 카드</div>
          <div class="thum-txtin">블루아이즈 3.5</div>
          <img src="/captcha/captcha.png" alt="captcha">
          <script>const captcha = document.querySelector('#captcha');</script>
        </body></html>
        '''

        profile = inspect_source_response(html, "https://m.example.test/post/1", expected="post")

        self.assertEqual(profile.state, "ok")

    def test_retry_backoff_is_bounded(self):
        self.assertEqual(retry_delay(0), 1.0)
        self.assertEqual(retry_delay(1), 2.0)
        self.assertEqual(retry_delay(10), 8.0)


if __name__ == "__main__":
    unittest.main()
