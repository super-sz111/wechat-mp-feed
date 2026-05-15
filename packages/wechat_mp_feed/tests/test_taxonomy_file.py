from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
TAXONOMY = ROOT / "examples" / "taxonomy.finance.yaml"


class TaxonomyFileTest(unittest.TestCase):
    def test_finance_taxonomy_has_required_sections(self):
        text = TAXONOMY.read_text(encoding="utf-8")

        for section in ("source_categories:", "article_categories:", "tag_groups:", "importance_thresholds:", "llm_policy:"):
            self.assertIn(section, text)

    def test_finance_taxonomy_entries_have_display_names(self):
        lines = TAXONOMY.read_text(encoding="utf-8").splitlines()
        id_lines = [index for index, line in enumerate(lines) if line.lstrip().startswith("- id: ")]

        self.assertGreater(len(id_lines), 20)
        for index in id_lines:
            window = "\n".join(lines[index : index + 5])
            self.assertIn("name_zh:", window)


if __name__ == "__main__":
    unittest.main()
