from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bulk_load import arrow_column


class CheckpointTypeTests(unittest.TestCase):
    def test_scd_end_date_does_not_overflow_timestamp_range(self):
        values = arrow_column(["9999-12-31", None], "date").to_pylist()
        self.assertEqual(values[0].isoformat(), "9999-12-31")
        self.assertIsNone(values[1])

    def test_decimal_values_do_not_round_trip_through_float(self):
        values = arrow_column(["1234567890123456.01", None], "decimal(18,2)").to_pylist()
        self.assertEqual(values, [Decimal("1234567890123456.01"), None])


if __name__ == "__main__":
    unittest.main()
