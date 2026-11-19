"""The product configuration and generated packaging metadata."""
import json
from pathlib import Path
import plistlib
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTION_APPROVED_STATUS = 'approved for distribution'
MINIMUM_MACOS = {'arm64': '14.0', 'x86_64': '13.0'}


def minimum_macos(metadata, architecture):
    mapping = metadata['product']['minimum_macos_by_architecture']
    if mapping != MINIMUM_MACOS or architecture not in MINIMUM_MACOS:
        raise ValueError('最低系统版本或架构无效')
    return mapping[architecture]


def load_product(path=None):
    data = json.loads(Path(path or ROOT / 'config/product.json').read_text())
    p, d, u = data['product'], data['driver'], data['uninstaller']
    if data['schema_version'] != 1:
        raise ValueError('不支持的产品配置版本')
    for key, pattern in [('version', r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'),
                         ('build_number', r'[1-9][0-9]*')]:
        if not isinstance(p[key], str) or re.fullmatch(pattern, p[key]) is None:
            raise ValueError('版本字段格式错误：' + key)
    expected = {
        'device_name': 'TapSay Audio 2ch', 'device_uid': 'com.leafney.tapsay.audio.device.2ch',
        'box_uid': 'com.leafney.tapsay.audio.box', 'model_uid': 'com.leafney.tapsay.audio.model.2ch',
        'bundle_identifier': 'com.leafney.tapsay.audio.driver',
        'package_receipt_identifier': 'com.leafney.tapsay.audio.pkg',
        'executable_name': 'TapSayAudio', 'plugin_factory_uuid': 'CC1226D1-A123-47B7-B113-5228AB089AA8',
        'audio_server_plugin_type_uuid': '443ABAB8-E7B3-491A-B985-BEB9187030DB',
        'channels': 2, 'default_sample_rate_hz': 48000, 'transport_type': 'usb',
        'hidden_device_uids': ['com.leafney.tapsay.audio.device.2ch.2'],
        'sample_rates_hz': [8000,16000,24000,44100,48000,88200,96000,176400,192000,352800,384000,705600,768000],
    }
    for key, value in expected.items():
        if d.get(key) != value:
            raise ValueError('稳定驱动合同不匹配：' + key)
    if (p['name'] != 'TapSay Audio'
            or p['architectures'] != ['arm64', 'x86_64']
            or p['minimum_macos_by_architecture'] != MINIMUM_MACOS):
        raise ValueError('产品名称或平台合同不匹配')
    if u['bundle_identifier'] != 'com.leafney.tapsay.audio.uninstaller':
        raise ValueError('卸载入口标识不匹配')
    upstream = data['upstream']
    if upstream['commit'] != 'e2b22aaaba4e507a097131704bf96dabc004d9cf' or upstream['license'] != 'GPL-3.0':
        raise ValueError('固定上游来源不匹配')
    if upstream['source_import_status'] not in (
            'integrated from fixed upstream commit; final distribution review pending',
            DISTRIBUTION_APPROVED_STATUS):
        raise ValueError('上游分发审查状态无效')
    if re.fullmatch(r'[0-9a-f]{64}', upstream['archive_sha256']) is None:
        raise ValueError('上游散列格式错误')
    return data


def render_uninstaller(destination, metadata, native, architecture, *, icon_path):
    if architecture not in ('arm64', 'x86_64'):
        raise ValueError('卸载工具架构无效：' + str(architecture))
    destination, native, icon_path = Path(destination), Path(native), Path(icon_path)
    if not icon_path.is_file() or icon_path.read_bytes()[:4] != b'icns':
        raise ValueError('卸载工具图标无效')
    shutil.copytree(ROOT / 'Uninstaller.app', destination)
    executable_directory = destination / 'Contents/MacOS'
    (executable_directory / 'TapSayAudioUninstaller').unlink(missing_ok=True)
    for pattern in ('TapSayAudioUninstaller-*', 'TapSayAudioTransaction-*'):
        for stale in executable_directory.glob(pattern):
            stale.unlink()
    info_path = destination / 'Contents/Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    icon_name = icon_path.name
    info.update(CFBundleShortVersionString=metadata['product']['version'],
                CFBundleVersion=metadata['product']['build_number'],
                CFBundleIdentifier=metadata['uninstaller']['bundle_identifier'],
                CFBundleExecutable='TapSayAudioUninstaller-' + architecture,
                CFBundleIconFile=icon_name,
                LSMinimumSystemVersion=minimum_macos(metadata, architecture))
    info_path.write_bytes(plistlib.dumps(info))
    resources = destination / 'Contents/Resources'
    resources.mkdir(exist_ok=True)
    shutil.copy2(icon_path, resources / icon_name)
    (resources / 'product.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    for name, source in [
        ('TapSayAudioUninstaller-' + architecture, 'TapSayAudioUninstaller'),
        ('TapSayAudioTransaction-' + architecture, 'TapSayAudioTransaction'),
    ]:
        shutil.copy2(native / source, executable_directory / name)
