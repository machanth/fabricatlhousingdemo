from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import build_workshop_guide as guide
except ModuleNotFoundError as error:
    if error.name not in {"docx", "markdown", "playwright"}:
        raise
    raise unittest.SkipTest("Install requirements-docs.txt to exercise document rendering.") from error


class WorkshopGuideTests(unittest.TestCase):
    def test_missing_local_asset_is_an_error_not_an_empty_link(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory)
            (docs / "workshop-attendee-guide.md").write_text("[SQL](missing.sql)")
            with patch.object(guide, "DOCS", docs), self.assertRaises(FileNotFoundError):
                guide.parse_manual()

    def test_screenshot_and_caption_stay_one_figure(self):
        with tempfile.TemporaryDirectory() as directory:
            docs = Path(directory)
            (docs / "screen.png").write_bytes(b"fixture")
            (docs / "workshop-attendee-guide.md").write_text(
                "![Actual settings](screen.png)\n\n*Figure 1. Actual settings.*\n\nNext step.")
            with patch.object(guide, "DOCS", docs):
                tree = guide.parse_manual()
            self.assertEqual([n.tag for n in tree], ["figure", "p"])
            self.assertEqual(tree.find("figure/figcaption").text, "Figure 1. Actual settings.")
            self.assertEqual(tree.find("figure/img").get("alt"), "Actual settings")

    def test_word_numbering_preserves_resumed_steps_and_schema_order(self):
        document = guide.Document()
        number = guide.numbered_list_id(document, 10)
        root = document.part.numbering_part.element
        entries = [n for n in root if n.tag == guide.qn("w:num")]
        entry = next(n for n in entries if n.get(guide.qn("w:numId")) == str(number))
        restart = entry.find(guide.qn("w:lvlOverride")).find(guide.qn("w:startOverride"))
        self.assertEqual(restart.get(guide.qn("w:val")), "10")
        tags = [n.tag for n in root]
        self.assertLess(max(i for i, tag in enumerate(tags) if tag == guide.qn("w:abstractNum")),
                        min(i for i, tag in enumerate(tags) if tag == guide.qn("w:num")))


if __name__ == "__main__":
    unittest.main()
