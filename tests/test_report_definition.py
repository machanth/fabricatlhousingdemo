import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_report import build


class ReportDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.documents = build("test-model-id")
        self.visuals = {
            doc["name"]: doc["visual"] for path, doc in self.documents.items()
            if path.endswith("/visual.json")
        }

    def test_all_projected_fields_exist_in_explicit_model(self):
        model = json.loads((ROOT / "semantic-model" / "model.bim").read_text())["model"]
        fields = {}
        for table in model["tables"]:
            fields[table["name"]] = {
                "Column": {c["name"] for c in table["columns"]},
                "Measure": {m["name"] for m in table.get("measures", [])},
            }
        for visual in self.visuals.values():
            for role in visual.get("query", {}).get("queryState", {}).values():
                for projection in role["projections"]:
                    kind, field = next(iter(projection["field"].items()))
                    table = field["Expression"]["SourceRef"]["Entity"]
                    self.assertIn(field["Property"], fields[table][kind])

    def test_slicer_default_is_semantic_filter_not_untyped_object(self):
        slicer = self.visuals["month_selection"]
        value = slicer["objects"]["general"][0]["properties"]["filter"]["filter"]
        source = value["From"][0]
        predicate = value["Where"][0]["Condition"]["In"]
        column = predicate["Expressions"][0]["Column"]
        self.assertEqual(source["Entity"], "DimDate")
        self.assertEqual(column["Expression"]["SourceRef"]["Source"], source["Name"])
        self.assertEqual(column["Property"], "MonthYear")
        self.assertEqual(len(predicate["Values"]), 1)
        controls = slicer["objects"]["selection"][0]["properties"]
        self.assertEqual(controls["strictSingleSelect"],
                         {"expr": {"Literal": {"Value": "true"}}})

    def test_expanded_categories_are_active_and_pinned(self):
        visual = self.visuals["occupied"]
        projections = visual["query"]["queryState"]["Rows"]["projections"]
        levels = visual["expansionStates"][0]["levels"]
        self.assertEqual([p["queryRef"] for p in projections],
                         [level["queryRefs"][0] for level in levels])
        self.assertTrue(all(p["active"] for p in projections))
        self.assertTrue(all(level["isPinned"] for level in levels))

    def test_metric_rows_and_cell_scoped_color_survive_serialization(self):
        for name in ("inventory", "supportive"):
            visual = json.loads(json.dumps(self.visuals[name]))
            self.assertEqual(visual["objects"]["values"][0]["properties"]["valuesOnRow"],
                             {"expr": {"Literal": {"Value": "true"}}})
        color = self.visuals["inventory"]["objects"]["values"][1]
        self.assertTrue(color["selector"]["data"])
        measure = color["properties"]["fontColor"]["solid"]["color"]["expr"]["Measure"]
        self.assertEqual(measure["Property"], "Vacancy Color")


if __name__ == "__main__":
    unittest.main()
