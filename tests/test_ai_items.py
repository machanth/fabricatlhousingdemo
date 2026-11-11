import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from configure_ai_items import configure_ontology, datasource, decode, encode
from query_data_agent import parse_response
from validate_ai_answers import same_rows


ROOT = Path(__file__).resolve().parents[1]


class AIItemsTests(unittest.TestCase):
    def test_ontology_excludes_permission_map_preserves_source_metrics_and_updates_context(self):
        source = {
            "model.tmdl": "model Model\nref table ProgramScope\nref table FactHouseholdSnapshot\n",
            "tables/ProgramScope.tmdl": "table ProgramScope\ncolumn UserPrincipalName",
            "tables/FactHouseholdSnapshot.tmdl":
                "/// Old description\ntable FactHouseholdSnapshot\n\tmeasure Households = EXTERNALMEASURE(...)",
            "expressions.tmdl": 'AnalysisServices.Database("WORKSPACE_NAME_PLACEHOLDER","SM_HouseholdsServed")'
        }
        result = configure_ontology(source, {"tables": {"FactHouseholdSnapshot": "Reviewed grain."}})
        self.assertNotIn("ProgramScope", "".join(result.values()))
        self.assertIn("/// Reviewed grain.\ntable", result["tables/FactHouseholdSnapshot.tmdl"])
        self.assertIn("EXTERNALMEASURE(...)", result["tables/FactHouseholdSnapshot.tmdl"])
        self.assertEqual(source["expressions.tmdl"], result["expressions.tmdl"])
        self.assertEqual(configure_ontology(result, {"tables": {
            "FactHouseholdSnapshot": "Reviewed grain."}}), result)
        self.assertIn("tables/ProgramScope.tmdl", source)

    def test_agent_has_one_model_source_without_permission_map(self):
        model = json.loads((ROOT / "semantic-model" / "model.bim").read_text())["model"]
        result = datasource(model, "workspace", "model")
        self.assertEqual(result["artifactId"], "model")
        self.assertEqual(result["type"], "semantic_model")
        self.assertEqual(len(result["elements"]), 11)
        self.assertNotIn("ProgramScope", json.dumps(result["elements"]))
        self.assertNotIn("UserPrincipalName", json.dumps(result["elements"]))
        unsafe = {"tables": [{"name": "Fact", "columns": [{"name": "HouseholdID"}]}]}
        with self.assertRaisesRegex(RuntimeError, "HouseholdID"):
            datasource(unsafe, "workspace", "model")

    def test_definition_roundtrip_preserves_ontology_binding_and_published_parts(self):
        parts = {
            "Files/Config/draft/ontologies/ONT_ATL_Housing/ontology.json": '{"artifactId":"ontology"}',
            "Files/Config/published/stage_config.json": '{"aiInstructions":"Published"}'
        }
        self.assertEqual(decode(encode(parts)), parts)

    def test_unordered_baselines_keep_duplicates_nulls_and_exact_keys(self):
        rows = [{"rule": "Z", "count": None}, {"rule": "a", "count": 0}]
        self.assertTrue(same_rows(rows, list(reversed(rows))))
        self.assertFalse(same_rows(rows, [{"rule": "Z", "count": 0}, rows[1]]))
        self.assertFalse(same_rows(rows, rows + [rows[0]]))
        self.assertFalse(same_rows(rows, [{"rule": "Z"}, rows[1]]))

    def test_runtime_accepts_json_and_sse_but_rejects_empty_sse_result(self):
        payload = '{"jsonrpc":"2.0","id":3,"result":{"content":[]}}'
        self.assertEqual(parse_response(payload), parse_response("event: message\ndata: " + payload + "\n\n"))
        with self.assertRaisesRegex(RuntimeError, "did not contain"):
            parse_response("event: ping\n\n")


if __name__ == "__main__":
    unittest.main()
