"""Deployment must fail closed; no running Docker daemon required."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/deploy.sh'

class DeployTests(unittest.TestCase):
    def run_deploy(self, fail_stage=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nginx/ssl').mkdir(parents=True)
            (root / 'nginx/nginx.conf').write_text('server_name example.com;')
            (root / 'scripts').mkdir()
            (root / 'scripts/check-production.py').write_text('')
            for name in ['fullchain.pem', 'privkey.pem']:
                (root / 'nginx/ssl' / name).touch()
            # Valid dotenv data must never be executed as shell code.
            (root / '.env').write_text('TEST=$(touch executed)\n')
            docker = root / 'docker'
            docker.write_text('''#!/bin/sh
case "$*" in
  *"config --quiet"*) [ "$FAIL_STAGE" != config ] ;;
  *"up -d"*) [ "$FAIL_STAGE" != up ] ;;
  *"exec -T"*) [ "$FAIL_STAGE" != ready ] ;;
  *) exit 0 ;;
esac
''')
            docker.chmod(0o755)
            result = subprocess.run(['bash', str(SCRIPT)], cwd=root,
                env={**os.environ, 'PATH': f'{root}:' + os.environ['PATH'], 'FAIL_STAGE': fail_stage},
                capture_output=True, text=True)
            self.assertFalse((root / 'executed').exists())
            return result

    def test_success(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Deployment complete', result.stdout)

    def test_failures_never_report_success(self):
        for stage in ['config', 'up', 'ready']:
            with self.subTest(stage=stage):
                result = self.run_deploy(stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Deployment complete', result.stdout)

if __name__ == '__main__':
    unittest.main()
