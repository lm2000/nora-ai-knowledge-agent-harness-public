import unittest
import tempfile
from pathlib import Path
import sys

# Insert the helpers module location into sys.path
helpers_path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(helpers_path))

from helpers import load_config, validate_config

class TestConfigValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Base valid config dictionary
        self.valid_cfg = {
            'PROJECT_ID': 'my-test-project',
            'REGION': 'us-central1',
            'ZONE': 'us-central1-a',
            'VECTOR_DB': 'qdrant',
            'MACHINE_TYPE': 'e2-standard-4',
            'DISK_SIZE_GB': '50',
            'BACKUP_BUCKET_NAME': 'my-test-project-backup'
        }

    def test_missing_required_fields(self):
        for key in self.valid_cfg:
            cfg = self.valid_cfg.copy()
            cfg[key] = ''
            with self.assertRaises(ValueError) as cm:
                validate_config(cfg)
            self.assertIn(f"Missing required configuration: {key}", str(cm.exception))

    def test_explicit_project_allowed(self):
        cfg = self.valid_cfg.copy()
        cfg['PROJECT_ID'] = 'example-project'  # should be accepted when explicitly set
        try:
            validate_config(cfg)
        except Exception as e:
            self.fail(f"validate_config raised {e} for allowed PROJECT_ID='example-project'")

    def test_invalid_vector_db(self):
        cfg = self.valid_cfg.copy()
        cfg['VECTOR_DB'] = 'milvus'  # milvus is no longer accepted
        with self.assertRaises(ValueError) as cm:
            validate_config(cfg)
        self.assertIn('VECTOR_DB must be "qdrant"', str(cm.exception))

    def test_allowed_vector_db_values(self):
        for db in ['qdrant']:
            cfg = self.valid_cfg.copy()
            cfg['VECTOR_DB'] = db
            try:
                validate_config(cfg)
            except Exception as e:
                self.fail(f"validate_config raised {e} for allowed VECTOR_DB='{db}'")

    def test_load_config_malformed_line(self):
        bad_content = "PROJECT_ID=myproj\nMALFORMEDLINE\nREGION=us-east1\n"
        tmp_path = Path(self.tmp.name) / (self._testMethodName + ".env")
        tmp_path.write_text(bad_content)
        try:
            with self.assertRaises(ValueError) as cm:
                load_config(tmp_path)
            self.assertIn('Malformed line', str(cm.exception))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_duplicate_key_detection(self):
        dup_content = "PROJECT_ID=myproj\nPROJECT_ID=other\nREGION=us-east1\nZONE=us-east1-a\n"
        tmp_path = Path(self.tmp.name) / (self._testMethodName + ".env")
        tmp_path.write_text(dup_content)
        try:
            with self.assertRaises(ValueError) as cm:
                load_config(tmp_path)
            self.assertIn('Duplicate configuration key', str(cm.exception))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_unknown_key_detection(self):
        unk_content = "PROJECT_ID=myproj\nFOO=bar\nREGION=us-east1\nZONE=us-east1-a\n"
        tmp_path = Path(self.tmp.name) / (self._testMethodName + ".env")
        tmp_path.write_text(unk_content)
        try:
            with self.assertRaises(ValueError) as cm:
                load_config(tmp_path)
            self.assertIn('Unknown configuration key', str(cm.exception))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_zone_region_mismatch(self):
        cfg = self.valid_cfg.copy()
        cfg['REGION'] = 'us-central1'
        cfg['ZONE'] = 'europe-west1-b'
        with self.assertRaises(ValueError) as cm:
            validate_config(cfg)
        self.assertIn('ZONE must belong to REGION', str(cm.exception))

    def test_valid_region_patterns(self):
        for region, zone in [('us-central1', 'us-central1-a'), ('europe-west1', 'europe-west1-b'), ('europe-west12', 'europe-west12-a'), ('northamerica-northeast1', 'northamerica-northeast1-a')]:
            cfg = self.valid_cfg.copy()
            cfg['REGION'] = region
            cfg['ZONE'] = zone
            try:
                validate_config(cfg)
            except Exception as e:
                self.fail(f"validate_config rejected valid region/zone pair {region}/{zone}: {e}")

if __name__ == '__main__':
    unittest.main()
