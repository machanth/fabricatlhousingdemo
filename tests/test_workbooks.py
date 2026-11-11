from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from landing import EXPECTED_COLUMNS, inspect_workbook, preflight, put_immutable


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

    def test_local_inventory_failure_does_not_contact_cloud(self):
        with tempfile.TemporaryDirectory() as directory, patch("landing.AzureCliCredential") as credential:
            with self.assertRaisesRegex(RuntimeError, "exactly the 24"):
                preflight(directory)
            credential.assert_not_called()

    def test_local_originals_are_read_without_modification_or_cloud_access(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("landing.AzureCliCredential") as credential, \
                patch("landing.inspect_workbook") as inspect, \
                patch("landing.save_state"), patch("builtins.print"):
            for kind in EXPECTED_COLUMNS:
                for month in range(1, 13):
                    (Path(directory) / f"{kind}_{202500 + month}.xlsx").write_bytes(b"original")
            inspect.side_effect = lambda name, content: {"file": name, "status": "READABLE"}
            self.assertEqual(len(preflight(directory)), 24)
            self.assertTrue(all(call.args[1] == b"original" for call in inspect.call_args_list))
            self.assertTrue(all(p.read_bytes() == b"original" for p in Path(directory).glob("*.xlsx")))
            credential.assert_not_called()


if __name__ == "__main__":
    unittest.main()
