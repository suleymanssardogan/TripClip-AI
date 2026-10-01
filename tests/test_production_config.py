import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('production', Path(__file__).resolve().parents[1] / 'scripts/check-production.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ProductionConfigTests(unittest.TestCase):
    def config(self):
        return {'services': {'core-api': {'environment': {
            'JWT_SECRET_KEY': 'j' * 32, 'INTERNAL_API_SECRET': 'i' * 32,
            'MONGODB_ROOT_USERNAME': 'tripclip_admin', 'MONGODB_ROOT_PASSWORD': 'm' * 32,
            'PRIVACY_REVIEWED_PROVIDERS': 'gemini,nominatim,overpass', 'GEMINI_API_KEY': 'test', 'AI_ASSISTANT_PROVIDER': 'gemini',
            'ALLOWED_ORIGINS': 'https://example.com', 'ALLOWED_HOSTS': 'core-api,example.com',
            'SMTP_HOST': 'smtp.example.com', 'SMTP_USER': 'test', 'SMTP_PASSWORD': 'test',
            'PASSWORD_RESET_URL_BASE': 'https://example.com/reset-password',
        }}, 'celery-worker': {'environment': {'USE_GEMINI': 'true', 'PRIVACY_REVIEWED_PROVIDERS': 'gemini,nominatim,overpass'}},
        'web': {'build': {'args': {
            'NEXT_PUBLIC_LEGAL_OPERATOR_NAME': 'Example Operator',
            'NEXT_PUBLIC_LEGAL_CONTACT_EMAIL': 'privacy@example.com',
            'LEGAL_CONTENT_APPROVED': 'true',
        }}}}}

    def test_valid(self):
        self.assertEqual(module.validate(self.config()), [])

    def test_rejects_weak_secrets_and_missing_recovery(self):
        config = self.config()
        core = config['services']['core-api']['environment']
        core.update(JWT_SECRET_KEY='', SMTP_PASSWORD='', PASSWORD_RESET_URL_BASE='http://localhost:3000/reset-password')
        errors = module.validate(config)
        for key in ['JWT_SECRET_KEY', 'SMTP_PASSWORD', 'PASSWORD_RESET_URL_BASE']:
            self.assertTrue(any(key in error for error in errors), errors)

    def test_partial_optional_features_rejected(self):
        config = self.config()
        config['services']['core-api']['environment']['GOOGLE_CLIENT_ID'] = 'test'
        config['services']['celery-worker']['environment']['APNS_KEY_ID'] = 'test'
        self.assertEqual(len(module.validate(config)), 2)

    def test_origin_must_match_hosts(self):
        config = self.config()
        config['services']['core-api']['environment']['ALLOWED_HOSTS'] = 'core-api'
        self.assertTrue(module.validate(config))

    def test_legal_pages_require_operator_and_review(self):
        config = self.config()
        config['services']['web']['build']['args'] = {}
        errors = module.validate(config)
        for key in ['LEGAL_OPERATOR_NAME', 'LEGAL_CONTACT_EMAIL', 'LEGAL_CONTENT_APPROVED']:
            self.assertTrue(any(key in error for error in errors), errors)

    def test_unreviewed_provider_blocks_deployment(self):
        config = self.config()
        config['services']['celery-worker']['environment']['PRIVACY_REVIEWED_PROVIDERS'] = ''
        errors = module.validate(config)
        self.assertTrue(any('celery-worker/gemini' in error for error in errors))

    def test_optional_analytics_cannot_be_enabled_before_erasure_support(self):
        config = self.config()
        config['services']['core-api']['environment']['ANALYTICS_ENABLED'] = 'true'
        self.assertTrue(any('ANALYTICS_ENABLED' in error for error in module.validate(config)))
