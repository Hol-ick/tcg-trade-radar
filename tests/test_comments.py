import unittest

from kaitori_collector.comments import parse_comments


class CommentParserTests(unittest.TestCase):
    def test_parse_comments_keeps_public_author_and_omits_ip(self):
        html = '''
        <div class="gallery_re_contents"><table>
          <tr class="reply_line">
            <td class="user user_layer" user_name="카드상인" user_id="carddealer">카드상인</td>
            <td class="reply">거래 가능해요 <span class="etc_ip">123.45</span></td>
            <td class="retime">2026-08-12 15:10:00</td>
            <td><p class="pp_input"><a onclick="javascript:re_delete('77','1','tcggame','77');">삭제</a></p></td>
          </tr>
          <tr class="reply_line">
            <td class="user user_layer">ㅇㅇ(39.7)</td>
            <td class="reply">사진 확인했습니다.</td>
            <td class="retime">2026-08-12 15:11:00</td>
          </tr>
        </table></div>
        '''

        comments = parse_comments(html, "https://example.test/post/1", "tcggame")

        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0].author_type, "registered")
        self.assertEqual(comments[0].comment_id, "77")
        self.assertNotIn("123.45", comments[0].body)
        self.assertEqual(comments[1].author_type, "guest")


if __name__ == "__main__":
    unittest.main()
