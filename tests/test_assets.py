from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_assets.py"
SPEC = importlib.util.spec_from_file_location("prepare_assets", SCRIPT)
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


class AssetTests(unittest.TestCase):
    def test_complete_model_matches_manifest_and_historical_benchmark(self):
        import json
        root = SCRIPT.parents[1]
        manifest = json.loads((root / "assets/models/manifest.json").read_text(encoding="utf-8"))
        report = json.loads((root / "artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img640.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(manifest["files"], report["artifacts"]["model"]["files"])
        assets.verify_model()

    def test_bad_existing_input_is_not_overwritten_or_downloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jpg"
            path.write_bytes(b"existing")
            with patch.object(assets.urllib.request, "urlopen") as network:
                with self.assertRaises(ValueError):
                    assets.download_verified(path, ["https://example.com/input.jpg"], "0" * 64)
                network.assert_not_called()
            self.assertEqual(path.read_bytes(), b"existing")

    def test_valid_existing_input_works_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jpg"
            path.write_bytes(b"existing")
            with patch.object(assets.urllib.request, "urlopen") as network:
                assets.download_verified(path, ["https://example.com/input.jpg"], assets.digest(path))
                network.assert_not_called()

    def test_mismatch_download_is_discarded(self):
        import io
        class Response(io.BytesIO):
            def geturl(self):
                return "https://example.com/input.jpg"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jpg"
            with patch.object(assets.urllib.request, "urlopen", return_value=Response(b"wrong")):
                with self.assertRaises(RuntimeError):
                    assets.download_verified(path, ["https://example.com/input.jpg"], "0" * 64)
            self.assertFalse(path.exists())
            self.assertEqual(list(path.parent.iterdir()), [])

    def test_verified_download_is_installed_and_temporary_file_removed(self):
        import hashlib
        import io
        class Response(io.BytesIO):
            def geturl(self):
                return "https://example.com/input.jpg"
        content = b"verified input"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jpg"
            with patch.object(assets.urllib.request, "urlopen", return_value=Response(content)):
                assets.download_verified(
                    path, ["https://example.com/input.jpg"], hashlib.sha256(content).hexdigest()
                )
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(list(path.parent.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
