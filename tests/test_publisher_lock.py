from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import publisher_lock


class PublisherLockTests(unittest.TestCase):
    def test_competing_publisher_is_rejected_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as directory, patch("common.ROOT", Path(directory)):
            with publisher_lock():
                with self.assertRaisesRegex(RuntimeError, "Another local publisher"):
                    with publisher_lock():
                        self.fail("A competing publisher acquired the lock")
            with publisher_lock():
                pass

    def test_failure_does_not_leave_stale_lock(self):
        with tempfile.TemporaryDirectory() as directory, patch("common.ROOT", Path(directory)):
            with self.assertRaisesRegex(ValueError, "load failed"):
                with publisher_lock():
                    raise ValueError("load failed")
            with publisher_lock():
                pass


if __name__ == "__main__":
    unittest.main()
