#!/usr/bin/env python3
"""Offline packaging checks, not App Review approval or a signed archive validation."""
import json
from pathlib import Path
import plistlib
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    errors = []
    project = (root / 'ios/TripClipApp.xcodeproj/project.pbxproj').read_text()
    paths = [('TripClipApp/Resources', {'CA92.1', '1C8F.1'}), ('TripClipShare', {'1C8F.1'})]
    for folder, required in paths:
        data = plistlib.loads((root / 'ios' / folder / 'PrivacyInfo.xcprivacy').read_bytes())
        reasons = {r for api in data.get('NSPrivacyAccessedAPITypes', [])
                   if api.get('NSPrivacyAccessedAPIType') == 'NSPrivacyAccessedAPICategoryUserDefaults'
                   for r in api.get('NSPrivacyAccessedAPITypeReasons', [])}
        if not required <= reasons:
            errors.append(f'{folder}: missing App Group/local UserDefaults reasons')
        if data.get('NSPrivacyTracking') is not False:
            errors.append(f'{folder}: tracking declaration does not match current app')
        types = {r['NSPrivacyCollectedDataType'] for r in data.get('NSPrivacyCollectedDataTypes', [])}
        if 'NSPrivacyCollectedDataTypePhotosorVideos' not in types:
            errors.append(f'{folder}: video collection declaration missing')
    if project.count('PrivacyInfo.xcprivacy in Resources */ =') != 2:
        errors.append('Main app and extension must each bundle their manifest')
    main = plistlib.loads((root / 'ios/TripClipApp/Resources/TripClipApp.entitlements').read_bytes())
    extension = plistlib.loads((root / 'ios/TripClipShare/TripClipShare.entitlements').read_bytes())
    if main.get('com.apple.developer.applesignin') != ['Default']:
        errors.append('Sign in with Apple entitlement missing')
    if not main.get('com.apple.security.application-groups') or main.get('com.apple.security.application-groups') != extension.get('com.apple.security.application-groups'):
        errors.append('Main and extension App Groups do not match')
    if main.get('aps-environment') != '$(APS_ENVIRONMENT)':
        errors.append('APNs environment must follow build configuration')
    for path in ('TripClipApp/Resources/Info.plist', 'TripClipShare/Info.plist'):
        info = plistlib.loads((root / 'ios' / path).read_bytes())
        if info.get('NSAppTransportSecurity', {}).get('NSAllowsArbitraryLoads'):
            errors.append(f'{path}: unrestricted HTTP enabled')
        if not info.get('NSLocalNetworkUsageDescription'):
            errors.append(f'{path}: development LAN usage explanation missing')
    icons = root / 'ios/TripClipApp/Resources/Assets.xcassets/AppIcon.appiconset'
    contents = json.loads((icons / 'Contents.json').read_text())
    marketing = [r for r in contents['images'] if r.get('size') == '1024x1024' and r.get('filename')]
    if not marketing:
        errors.append('1024px App Store icon missing')
    for row in marketing:
        raw = (icons / row['filename']).read_bytes()
        if raw[:8] != b'\x89PNG\r\n\x1a\n' or len(raw) < 33 or struct.unpack('>II', raw[16:24]) != (1024, 1024):
            errors.append('App Store icon must be a valid 1024x1024 PNG')
        elif raw[25] in (4, 6) or b'tRNS' in raw:
            errors.append('App Store icon must not contain an alpha channel/transparency')
    return errors


if __name__ == '__main__':
    try:
        errors = check()
    except (OSError, ValueError, KeyError) as exc:
        print(f'Packaging check failed: {type(exc).__name__}')
        sys.exit(1)
    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print('Offline packaging checks passed. Signed archive, live services and App Review remain unverified.')
