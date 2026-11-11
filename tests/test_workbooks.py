from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from landing import inspect_workbook, put_immutable


def workbook(rows, sheet="Roster"):
    stream = BytesIO()
    pd.DataFrame(rows).to_excel(stream, sheet_name=sheet, index=False)
    return stream.getvalue()


class WorkbookTests(unittest.TestCase):
    def test_encrypted_container_is_blocked_not_regenerated(self):
        result = inspect_workbook("SupportiveHousing_202501.xlsx", bytes.fromhex("D0CF11E0A1B11AE1") + b"EncryptedPackage")
        self.assertEqual(result["status"], "BLOCKED")

    def test_roster_program_is_part_of_grain(self):
        rows = [{"ReportMonth": "2025-01-01", "HouseholdID": "H1", "Program": p, "SupportType": "Other"}
                for p in ("A", "B")]
        self.assertEqual(inspect_workbook("SupportiveHousing_202501.xlsx", workbook(rows))["rows"], 2)
        with self.assertRaisesRegex(ValueError, "Duplicate grain"):
            inspect_workbook("SupportiveHousing_202501.xlsx", workbook([rows[0], rows[0]]))

    def test_month_and_shape_cannot_silently_change(self):
        rows = [{"ReportMonth": "2025-02-01", "HouseholdID": "H1", "Program": "A", "SupportType": "Other"}]
        with self.assertRaisesRegex(ValueError, "ReportMonth disagrees"):
            inspect_workbook("SupportiveHousing_202501.xlsx", workbook(rows))
        rows[0] = {"Program": "A", "VASH": 1, "OtherSupportive": 2}
        with self.assertRaisesRegex(ValueError, "Unexpected columns"):
            inspect_workbook("SupportiveHousing_202501.xlsx", workbook(rows))

    def test_new_landing_detects_same_size_corruption(self):
        fs = Mock()
        file = fs.get_file_client.return_value
        file.exists.return_value = False
        file.get_file_properties.return_value.size = 7
        file.download_file.return_value.readall.return_value = b"changed"
        with self.assertRaisesRegex(RuntimeError, "hash differs"):
            put_immutable(fs, "approved-run/file.json", b"trusted")
        file.upload_data.assert_called_once()

    def test_existing_landing_is_never_overwritten(self):
        fs = Mock()
        file = fs.get_file_client.return_value
        file.exists.return_value = True
        file.get_file_properties.return_value.size = 7
        file.download_file.return_value.readall.return_value = b"changed"
        with self.assertRaisesRegex(RuntimeError, "hash differs"):
            put_immutable(fs, "approved-run/file.json", b"trusted")
        file.upload_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
