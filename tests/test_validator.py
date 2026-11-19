import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "validator" / "validate.py"


class ValidatorTest(unittest.TestCase):
    def write_delivery(self, root: Path) -> Path:
        delivery = root / "delivery"
        for part in ("images", "labels", "masks"):
            (delivery / part).mkdir(parents=True)
        image = delivery / "images" / "one.jpg"
        image.write_bytes(b"fixture image")
        (delivery / "labels" / "one.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        (delivery / "classes.txt").write_text("0 person\n", encoding="utf-8")
        (delivery / "jobs.csv").write_text("job_id,annotator,reviewer,guideline\nJ01,A01,Q01,v1.2\n", encoding="utf-8")
        (delivery / "metadata.json").write_text(json.dumps({"items": [{"image": "one", "scene_id": "scene_1", "split": "train", "job_id": "J01", "guideline_version": "v1.2"}]}), encoding="utf-8")
        (delivery / "panoptic.json").write_text(json.dumps({"categories": [], "images": [], "annotations": []}), encoding="utf-8")
        (delivery / "manifest.json").write_text(json.dumps({"items": {"one": {
            "image": "images/one.jpg", "label": "labels/one.txt", "mask": "masks/one.png",
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        }}}), encoding="utf-8")
        return delivery

    def run_validator(self, delivery: Path, root: Path) -> list[dict]:
        output = root / "errors.json"
        subprocess.run([sys.executable, str(VALIDATOR), str(delivery), "--out", str(output)], check=True)
        return json.loads(output.read_text(encoding="utf-8"))["errors"]

    def test_clean_minimum_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(self.run_validator(self.write_delivery(root), root), [])

    def test_detects_hash_invalid_class_bbox_and_scene_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery = self.write_delivery(root)
            (delivery / "labels" / "one.txt").write_text("1 1.05 0.5 0.2 0.2\n", encoding="utf-8")
            (delivery / "images" / "one.jpg").write_bytes(b"changed fixture image")
            doc = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))
            doc["items"].append({"image": "two", "scene_id": "scene_1", "split": "val", "job_id": "J01", "guideline_version": "v1.3"})
            (delivery / "metadata.json").write_text(json.dumps(doc), encoding="utf-8")
            manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))
            manifest["items"]["two"] = dict(manifest["items"]["one"])
            (delivery / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            found = {(item["type"], item["target"]) for item in self.run_validator(delivery, root)}
            self.assertTrue({("wrong_hash", "one"), ("invalid_class", "one"), ("bbox_out_of_bounds", "one"),
                             ("guideline_mismatch", "two"), ("scene_leak", "scene_1")} <= found)


if __name__ == "__main__":
    unittest.main()
