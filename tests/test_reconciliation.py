import sys
from pathlib import Path
import unittest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import household_metrics, reconcile


class ReconciliationTests(unittest.TestCase):
    def test_program_grain_preserves_second_program(self):
        frame = pd.DataFrame([
            (20250101, "A", "H1", "With children", "Elderly"),
            (20250101, "B", "H1", "With children", "Elderly"),
            (20250101, "A", "H2", "Without children", "Disabled"),
        ], columns=["EffectiveDateKey", "ProgramTypeCode", "HouseholdID", "HouseholdType", "Category"])
        actual = household_metrics(frame).set_index("ProgramTypeCode")
        self.assertEqual(actual.loc["A", "Households"], 2)
        self.assertEqual(actual.loc["B", "Households"], 1)
        self.assertEqual(actual.loc["A", "HWC_Elderly"], 1)
        self.assertEqual(actual.loc["A", "HWOC_Disabled"], 1)

    def test_missing_and_unexpected_keys_are_errors(self):
        expected = pd.DataFrame([(20250101, "A", 3)], columns=["EffectiveDateKey", "ProgramTypeCode", "Households"])
        actual = pd.DataFrame([(20250101, "B", 3)], columns=expected.columns)
        self.assertEqual(len(reconcile(actual, expected, ["Households"])), 2)

    def test_null_vacancy_is_not_zero(self):
        expected = pd.DataFrame([(20250101, "A", None)], columns=["EffectiveDateKey", "ProgramTypeCode", "VacantUnits"])
        actual = expected.copy()
        self.assertEqual(reconcile(actual, expected, ["VacantUnits"]), [])
        actual["VacantUnits"] = 0
        self.assertEqual(len(reconcile(actual, expected, ["VacantUnits"])), 1)


if __name__ == "__main__":
    unittest.main()
