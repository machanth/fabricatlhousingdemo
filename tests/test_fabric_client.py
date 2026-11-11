from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import FABRIC, fabric


class FabricClientTests(unittest.TestCase):
    def test_regional_operation_location_uses_canonical_api(self):
        operation = "6798200c-b7a8-4621-a41b-768f44a3a2f9"
        responses = [
            (202, {"location": f"https://wabi-west-us3-a-primary-redirect.analysis.windows.net/v1/operations/{operation}",
                   "retry-after": "0"}, None),
            (200, {}, {"status": "Succeeded"}),
            (200, {}, {"id": "created"}),
        ]
        with patch("common.request", side_effect=responses) as request, patch("common.time.sleep"):
            self.assertEqual(fabric("POST", "workspaces/example/notebooks", {}), {"id": "created"})
            self.assertEqual(request.call_args_list[1].args[1], f"{FABRIC}/operations/{operation}")

    def test_failed_operation_is_not_success_shaped(self):
        operation = "6798200c-b7a8-4621-a41b-768f44a3a2f9"
        with patch("common.request", side_effect=[
            (202, {"x-ms-operation-id": operation, "retry-after": "0"}, None),
            (200, {}, {"status": "Failed", "error": {"errorCode": "Denied"}}),
        ]), patch("common.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "Fabric operation failed"):
                fabric("POST", "example", {})

    def test_update_operation_with_no_result_does_not_fetch_result_endpoint(self):
        operation = "6798200c-b7a8-4621-a41b-768f44a3a2f9"
        with patch("common.request", side_effect=[
            (202, {"x-ms-operation-id": operation, "retry-after": "0"}, None),
            (200, {}, {"status": "Succeeded"}),
        ]) as request, patch("common.time.sleep"):
            self.assertIsNone(fabric("POST", "example/updateDefinition", {}, has_result=False))
            self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
