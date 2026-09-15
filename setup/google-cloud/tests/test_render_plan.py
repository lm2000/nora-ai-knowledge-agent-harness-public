import unittest
import tempfile
from pathlib import Path
import sys
import json

# Ensure helpers module is on the path
helpers_path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(helpers_path))

from helpers import write_plan, load_config

class TestRenderPlan(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            'PROJECT_ID': 'demo-project',
            'REGION': 'us-central1',
            'ZONE': 'us-central1-a',
            'VECTOR_DB': 'qdrant',
            'MACHINE_TYPE': 'e2-medium',
            'DISK_SIZE_GB': '30',
            'BACKUP_BUCKET_NAME': 'demo-project-backup'
        }
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_dir = Path(self.tmp.name)
        self.plan_path = self.tmp_dir / "plan.txt"

    def test_successful_plan_creation(self):
        # Should create the plan file with exclusive write
        write_plan(self.cfg, self.plan_path)
        self.assertTrue(self.plan_path.is_file())
        content = self.plan_path.read_text()
        self.assertIn('Project: demo-project', content)
        self.assertIn('Vector DB: Deploy qdrant instance', content)
        self.assertIn('Compute Engine VM: type=e2-medium, dedicated-data-disk=30GiB', content)

    def test_prevent_overwrite(self):
        # First creation succeeds
        write_plan(self.cfg, self.plan_path)
        # Capture original content
        original = self.plan_path.read_bytes()
        # Second attempt must raise FileExistsError and leave file unchanged
        with self.assertRaises(FileExistsError):
            write_plan(self.cfg, self.plan_path)
        self.assertEqual(original, self.plan_path.read_bytes())

    def test_invalid_config_raises(self):
        bad_cfg = self.cfg.copy()
        bad_cfg['REGION'] = 'invalid-region'
        with self.assertRaises(ValueError):
            write_plan(bad_cfg, self.plan_path)
        self.assertFalse(self.plan_path.exists())

if __name__ == '__main__':
    unittest.main()

class TestShellEntrypoint(unittest.TestCase):
    def test_script_from_other_directory_and_output_preservation(self):
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory(prefix='cloud setup ') as tmp:
            bundle=Path(tmp)/'bundle with spaces';bundle.mkdir()
            for name in ['02-render-plan.sh','helpers.py']:
                shutil.copy(helpers_path/name,bundle/name)
            config='PROJECT_ID=example-project\nREGION=europe-west12\nZONE=europe-west12-a\nVECTOR_DB=qdrant\nMACHINE_TYPE=e2-standard-4\nDISK_SIZE_GB=100\nBACKUP_BUCKET_NAME=example-project-test-backup\n'
            (bundle/'config.env').write_text(config)
            command=['bash',str(bundle/'02-render-plan.sh')]
            first=subprocess.run(command,cwd=tmp,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            output=bundle/'plan-output/plan.txt';original=output.read_bytes()
            self.assertIn(b'europe-west12',original)
            second=subprocess.run(command,cwd=tmp,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(output.read_bytes(),original)
            self.assertEqual((bundle/'config.env').read_text(),config)
