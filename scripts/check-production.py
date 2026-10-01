#!/usr/bin/env python3
"""Validate resolved production config without printing secret values."""
import json
import subprocess
import sys
from urllib.parse import urlparse


def validate(config):
    errors = []
    services = config['services']
    core = services['core-api']['environment']
    worker = services['celery-worker']['environment']
    legal = services['web']['build'].get('args') or {}
    if not (legal.get('NEXT_PUBLIC_LEGAL_OPERATOR_NAME') or '').strip():
        errors.append('LEGAL_OPERATOR_NAME: legal operator identity is required')
    email = (legal.get('NEXT_PUBLIC_LEGAL_CONTACT_EMAIL') or '').strip()
    if '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
        errors.append('LEGAL_CONTACT_EMAIL: valid contact address is required')
    if legal.get('LEGAL_CONTENT_APPROVED') != 'true':
        errors.append('LEGAL_CONTENT_APPROVED: review legal pages before deployment')
    for name, env in (("core-api", core), ("celery-worker", worker)):
        reviewed = {v.strip().lower() for v in (env.get('PRIVACY_REVIEWED_PROVIDERS') or '').split(',') if v.strip()}
        required = {"nominatim", "overpass"}
        if env.get('USE_GEMINI') == 'true' or env.get('AI_ASSISTANT_PROVIDER') == 'gemini':
            required.add('gemini')
        if env.get('OLLAMA_URL'):
            required.add('ollama')
        if env.get('USE_GOOGLE_VISION') == 'true':
            required.add('google_vision')
        if env.get('SENTRY_DSN'):
            required.add('sentry')
        for provider in sorted(required - reviewed):
            errors.append(f'PRIVACY_REVIEWED_PROVIDERS: {name}/{provider} transfer review required')
        if env.get('ANALYTICS_ENABLED') == 'true':
            errors.append('ANALYTICS_ENABLED: keep optional analytics disabled until retention and erasure support are implemented')
    for key, default in (('RAW_UPLOAD_RETENTION_HOURS', '24'), ('FAILED_UPLOAD_RETENTION_HOURS', '168')):
        try:
            valid = 1 <= int(core.get(key, default)) <= 720
        except (ValueError, TypeError):
            valid = False
        if not valid:
            errors.append(f'{key}: retention must be between 1 and 720 hours')
    for key in ('JWT_SECRET_KEY', 'INTERNAL_API_SECRET'):
        if len(core.get(key) or '') < 32:
            errors.append(f'{key}: at least 32 characters required')
    for key in ('MONGODB_ROOT_USERNAME', 'MONGODB_ROOT_PASSWORD'):
        if len(core.get(key) or '') < (3 if key.endswith('USERNAME') else 32):
            errors.append(f'{key}: production credential is missing or too short')
    if core.get('JWT_SECRET_KEY') == core.get('INTERNAL_API_SECRET'):
        errors.append('JWT_SECRET_KEY and INTERNAL_API_SECRET must be independent')
    if not core.get('GEMINI_API_KEY') and (worker.get('USE_GEMINI') == 'true' or core.get('AI_ASSISTANT_PROVIDER') == 'gemini'):
        errors.append('GEMINI_API_KEY required for the configured Gemini features')
    for key in ('ALLOWED_ORIGINS', 'ALLOWED_HOSTS'):
        values = [v.strip() for v in (core.get(key) or '').split(',') if v.strip()]
        if not values or '*' in values:
            errors.append(f'{key}: explicit production values required')
    origins = [v.strip() for v in (core.get('ALLOWED_ORIGINS') or '').split(',') if v.strip()]
    if any(urlparse(v).scheme != 'https' or not urlparse(v).hostname or urlparse(v).hostname in ('localhost', '127.0.0.1') for v in origins):
        errors.append('ALLOWED_ORIGINS must contain public HTTPS origins')
    hosts = set((core.get('ALLOWED_HOSTS') or '').split(','))
    if any(urlparse(v).hostname not in hosts for v in origins):
        errors.append('ALLOWED_HOSTS must include each web origin hostname')
    # Password-based accounts are enabled: recovery must work before launch.
    for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'):
        if not core.get(key):
            errors.append(f'{key}: required for account recovery')
    reset = urlparse(core.get('PASSWORD_RESET_URL_BASE') or '')
    if reset.scheme != 'https' or not reset.hostname or reset.hostname in ('localhost', '127.0.0.1'):
        errors.append('PASSWORD_RESET_URL_BASE must be a public HTTPS URL')
    for env, keys in [(core, ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_ALLOWED_REDIRECT_URIS')),
                      (worker, ('APNS_KEY_ID', 'APNS_TEAM_ID', 'APNS_BUNDLE_ID', 'APNS_AUTH_KEY'))]:
        if any(env.get(k) for k in keys) and not all(env.get(k) for k in keys):
            errors.append('Configure all or none of: ' + ', '.join(keys))
    return errors


def main():
    result = subprocess.run(['docker', 'compose', '-f', 'docker-compose.prod.yml', 'config', '--format', 'json'], capture_output=True, text=True)
    if result.returncode:
        print('Production configuration invalid. Run docker compose -f docker-compose.prod.yml config --quiet.', file=sys.stderr)
        return 1
    errors = validate(json.loads(result.stdout))
    for error in errors:
        print('ERROR: ' + error, file=sys.stderr)
    if not errors:
        print('Production configuration checks passed (external services still require smoke testing).')
    return int(bool(errors))

if __name__ == '__main__':
    sys.exit(main())
