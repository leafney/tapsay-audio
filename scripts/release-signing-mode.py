#!/usr/bin/env python3
"""Select a release signing mode without disclosing credentials."""
import os
import sys

NAMES = (
    'DEVELOPER_ID_APPLICATION_P12_BASE64',
    'DEVELOPER_ID_APPLICATION_P12_PASSWORD',
    'DEVELOPER_ID_INSTALLER_P12_BASE64',
    'DEVELOPER_ID_INSTALLER_P12_PASSWORD',
    'APPLE_TEAM_ID',
    'APP_STORE_CONNECT_ISSUER_ID',
    'APP_STORE_CONNECT_KEY_ID',
    'APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64',
)


def select(environment):
    count = sum(bool(environment.get(name, '').strip()) for name in NAMES)
    if count == 0:
        return 'adhoc'
    if count == len(NAMES):
        return 'developer-id'
    raise ValueError('签名凭据必须全部配置或全部留空')


if __name__ == '__main__':
    try:
        mode = select(os.environ)
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('signing_mode=' + mode + '\n')
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
