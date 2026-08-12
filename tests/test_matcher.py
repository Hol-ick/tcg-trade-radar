import unittest

from kaitori_collector.matcher import CatalogCard, match_card


CATALOG = [
    CatalogCard(id="blue-ur", code="QCCP-JP001", name="블루아이즈", game="유희왕", set_name="QCC", rarity="울레"),
    CatalogCard(id="blue-pr", code="QCCP-JP001", name="블루아이즈", game="유희왕", set_name="QCC", rarity="프싴"),
    CatalogCard(id="red-ur", code="QCCP-JP002", name="레드아이즈", game="유희왕", set_name="QCC", rarity="울레"),
]


class MatcherTests(unittest.TestCase):
    def test_card_code_is_stronger_than_name_candidates(self):
        result = match_card("QCCP-JP001 블루아이즈", "울레", CATALOG)

        self.assertEqual(result.status, "matched")
        self.assertEqual(result.card_code, "QCCP-JP001")
        self.assertEqual([candidate.card.id for candidate in result.candidates], ["blue-ur"])
        self.assertEqual(result.candidates[0].matched_by, "card_code")

    def test_multiple_name_candidates_require_review(self):
        result = match_card("블루아이즈", "", CATALOG)

        self.assertEqual(result.status, "needs_review")
        self.assertGreater(len(result.candidates), 1)
        self.assertIn("복수", result.reason)

    def test_unknown_name_requires_review(self):
        result = match_card("이미지 카드", "", CATALOG)

        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.candidates, [])
        self.assertIn("일치", result.reason)


if __name__ == "__main__":
    unittest.main()
