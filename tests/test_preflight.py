"""Offline startup-contract tests. No real agent, credentials, or network."""
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / 'project with spaces').mkdir()
        (self.base / 'bin').mkdir()
        self.marker = self.base / 'started'
        for name in ('codex', 'claude', 'cc-connect'):
            p = self.base / 'bin' / name
            p.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then\n'
                         '  echo "cc-connect v1.5.0"\nelse\n'
                         '  touch "$TEST_START_MARKER"\nfi\n')
            p.chmod(0o700)
        self.env = {
            'PATH': str(self.base / 'bin') + ':/usr/bin:/bin',
            'PROJECT_NAME': 'offline-test',
            'PROJECT_DIR': str(self.base / 'project with spaces'),
            'BRIDGE_STATE_DIR': str(self.base / 'state'),
            'FEISHU_APP_ID': 'cli_Example123',
            'FEISHU_APP_SECRET': 'FAKE_SECRET_MUST_NOT_APPEAR',
            'FEISHU_ALLOW_FROM': 'ou_Example123',
            'DEEPSEEK_API_KEY': 'FAKE_API_MUST_NOT_APPEAR',
            'DEEPSEEK_MODEL': 'deepseek-flash',
            'CLAUDE_API_KEY': 'FAKE_API_MUST_NOT_APPEAR',
            'CLAUDE_MODEL': 'test-anthropic-model',
            'TEST_START_MARKER': str(self.marker),
        }

    def run_check(self, profile='codex-readonly'):
        result = subprocess.run(
            ['/bin/bash', str(ROOT / 'scripts/run-bridge.sh'), profile, '--check'],
            env=self.env, text=True, capture_output=True, timeout=10)
        self.assertFalse(self.marker.exists(), 'check must not start the bridge')
        self.assertFalse((self.base / 'state').exists(), 'check must not create state')
        self.assertNotIn('FAKE_SECRET_MUST_NOT_APPEAR', result.stdout + result.stderr)
        self.assertNotIn('FAKE_API_MUST_NOT_APPEAR', result.stdout + result.stderr)
        return result

    def test_all_profiles_preflight(self):
        for profile in ('codex-readonly', 'codex-approval', 'claude-anthropic', 'claude-deepseek'):
            with self.subTest(profile=profile):
                self.assertEqual(self.run_check(profile).returncode, 0)

    def test_missing_whitelist_fails_closed(self):
        del self.env['FEISHU_ALLOW_FROM']
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_invalid_whitelists_fail_closed(self):
        for value in ('', '  ', '*', 'ou_Example123,*', 'ou_Example123,', 'user@example.com'):
            with self.subTest(value=value):
                self.env['FEISHU_ALLOW_FROM'] = value
                self.assertNotEqual(self.run_check().returncode, 0)

    def test_explicit_multiple_users_allowed(self):
        self.env['FEISHU_ALLOW_FROM'] = 'ou_Example123,ou_Example456'
        self.assertEqual(self.run_check().returncode, 0)

    def test_missing_secret_does_not_start(self):
        del self.env['FEISHU_APP_SECRET']
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_deepseek_requires_own_key(self):
        del self.env['DEEPSEEK_API_KEY']
        self.assertNotEqual(self.run_check('claude-deepseek').returncode, 0)
        self.assertEqual(self.run_check('codex-readonly').returncode, 0)

    def test_example_and_multiline_inputs_rejected(self):
        for value in ('REPLACE_WITH_APP_SECRET', 'one\ntwo'):
            self.env['FEISHU_APP_SECRET'] = value
            self.assertNotEqual(self.run_check().returncode, 0)

    def test_unknown_profile_rejected(self):
        self.assertNotEqual(self.run_check('../../other').returncode, 0)

    def test_wrong_bridge_version_rejected(self):
        (self.base / 'bin/cc-connect').write_text('#!/bin/sh\necho "cc-connect v1.5.1-beta.1"\n')
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_templates_enforce_restricted_defaults(self):
        for path in (ROOT / 'configs').glob('*.toml'):
            with self.subTest(path=path.name):
                raw = path.read_text()
                cfg = tomllib.loads(raw)
                self.assertEqual(len(cfg['projects']), 1)
                project = cfg['projects'][0]
                self.assertEqual(project['reset_on_idle_mins'], 0)
                self.assertNotIn('admin_from', project)
                self.assertNotIn('heartbeat', project)
                options = project['platforms'][0]['options']
                self.assertEqual(options['allow_from'], '${FEISHU_ALLOW_FROM}')
                self.assertTrue(options['enable_feishu_card'])
                self.assertFalse(options['group_reply_all'])
                self.assertNotIn(project['agent']['options']['mode'], ('yolo', 'bypassPermissions'))
                self.assertTrue(set(re.findall(r'\$\{(\w+)\}', raw)) <= self.env.keys())
                if path.stem == 'codex-approval':
                    self.assertEqual(project['agent']['options']['app_server_url'], 'stdio://')

    def run_start(self, profile='claude-deepseek', check=False):
        args = ['/bin/bash', str(ROOT / 'scripts/run-bridge.sh'), profile]
        if check:
            args.append('--check')
        result = subprocess.run(args, env=self.env, text=True,
                                capture_output=True, timeout=10)
        self.assertNotIn('FAKE_SECRET_MUST_NOT_APPEAR', result.stdout + result.stderr)
        self.assertNotIn('FAKE_API_MUST_NOT_APPEAR', result.stdout + result.stderr)
        return result

    def test_runtime_config_literal_name_and_private_placeholders(self):
        originals = {p: p.read_bytes() for p in (ROOT / 'configs').glob('*.toml')}
        self.assertEqual(self.run_start().returncode, 0)
        path = self.base / 'state/config.claude-deepseek.toml'
        raw = path.read_text()
        cfg = tomllib.loads(raw)
        self.assertEqual(cfg['projects'][0]['name'], self.env['PROJECT_NAME'])
        self.assertIn('${DEEPSEEK_API_KEY}', raw)
        self.assertNotIn('FAKE_API_MUST_NOT_APPEAR', raw)
        self.assertNotIn('FAKE_SECRET_MUST_NOT_APPEAR', raw)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.marker.exists())
        for p, data in originals.items():
            self.assertEqual(p.read_bytes(), data)

    def test_runtime_model_selection_survives_restart(self):
        self.assertEqual(self.run_start().returncode, 0)
        path = self.base / 'state/config.claude-deepseek.toml'
        selected = path.read_text().replace('${DEEPSEEK_MODEL}', 'another-supported-model')
        path.write_text(selected)
        del self.env['DEEPSEEK_MODEL']
        self.assertEqual(self.run_start().returncode, 0)
        self.assertEqual(path.read_text(), selected)

    def test_runtime_added_provider_requires_its_secret(self):
        self.assertEqual(self.run_start().returncode, 0)
        path = self.base / 'state/config.claude-deepseek.toml'
        with path.open('a') as f:
            f.write('\n[[projects.agent.providers]]\nname = "extra"\napi_key = "${EXTRA_KEY}"\n')
        self.marker.unlink()
        self.assertNotEqual(self.run_start().returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_runtime_project_mismatch_fails(self):
        self.assertEqual(self.run_start().returncode, 0)
        self.marker.unlink()
        self.env['PROJECT_NAME'] = 'other-project'
        self.assertNotEqual(self.run_start().returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_check_existing_runtime_is_read_only(self):
        self.assertEqual(self.run_start().returncode, 0)
        self.marker.unlink()
        path = self.base / 'state/config.claude-deepseek.toml'
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.assertEqual(self.run_start(check=True).returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_anthropic_requires_api_not_subscription(self):
        del self.env['CLAUDE_API_KEY']
        self.env['CLAUDE_CODE_OAUTH_TOKEN'] = 'fake-subscription-token'
        self.assertNotEqual(self.run_check('claude-anthropic').returncode, 0)


if __name__ == '__main__':
    unittest.main()
