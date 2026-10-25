"""Offline tests: only verified historical bars can enter a data-only push plan."""

import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("publish_data", Path(__file__).with_name("push_validated_breeze_data.py"))
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


class FakeClient:
    def fetch(self, params):
        return dict(Status=200, Success=[dict(datetime=(datetime(2026, 6, 23, 9, 15)+timedelta(minutes=i)).isoformat(" "),
                                             stock_code="NIFTY", exchange_code="NSE", open=100, high=102,
                                             low=99, close=101, volume=0) for i in range(375)])


class DataPublishChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="algo8-data-publish-test-")
        self.root = Path(self.temp.name)
        self.data = self.root/"data"/"breeze"
        self.metadata = publish.fetch.fetch_day(FakeClient(), self.data, "NIFTY", date(2026, 6, 23))
        self.meta_path = next((self.data/"metadata").rglob("*.json"))

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_contains_only_three_validated_paths(self):
        (self.root/"unrelated.txt").write_text("unrelated")
        (self.root/".env").write_text("fake-test-only")
        files = publish.validated_files(self.root)
        self.assertEqual(len(files), 3)
        self.assertTrue(all(p.startswith("data/breeze/") for p in files))
        self.assertNotIn(".env", files)

    def test_corrupted_normalized_file_rejected(self):
        (self.data/self.metadata["normalized_path"]).write_text("changed\n")
        with self.assertRaises(publish.fetch.FetchError):
            publish.validated_files(self.root)

    def test_unexpected_raw_fields_rejected_even_with_updated_hash(self):
        raw = self.data/self.metadata["raw_path"]
        payload = json.loads(raw.read_text())
        payload["response"]["Success"][0]["session_token"] = "fake-test-only"
        raw.write_bytes(publish.fetch.canonical(payload))
        self.metadata["raw_sha256"] = publish.fetch.digest(raw.read_bytes())
        self.meta_path.write_bytes(publish.fetch.canonical(self.metadata))
        with self.assertRaises(publish.fetch.FetchError):
            publish.validated_files(self.root)

    def test_extra_metadata_field_rejected(self):
        self.metadata["api_key"] = "fake-test-only"
        self.meta_path.write_bytes(publish.fetch.canonical(self.metadata))
        with self.assertRaises(publish.fetch.FetchError):
            publish.validated_files(self.root)

    def test_path_outside_data_subtree_rejected(self):
        self.metadata["raw_path"] = "../../outside.json"
        self.meta_path.write_bytes(publish.fetch.canonical(self.metadata))
        with self.assertRaises(publish.fetch.FetchError):
            publish.validated_files(self.root)

    def test_no_completed_data_does_not_produce_push_plan(self):
        self.meta_path.unlink()
        with self.assertRaises(publish.fetch.FetchError):
            publish.validated_files(self.root)


if __name__ == "__main__":
    unittest.main()
