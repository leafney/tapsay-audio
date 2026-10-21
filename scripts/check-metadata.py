#!/usr/bin/env python3
"""Validate the product identity contract before building release artifacts."""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "config" / "product.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("reference-48k", "reference-16k"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    product = data["product"]
    driver = data["driver"]
    uninstaller = data["uninstaller"]
    upstream = data["upstream"]

    require(data["schema_version"] == 1, "Unsupported metadata schema_version")
    require(product["name"] == "TapSay Audio", "Unexpected product name")
    require(product["version"] == "0.1.0", "Unexpected initial product version")
    require(product["build_number"] == "1", "Unexpected initial build number")
    require(product["minimum_macos"] == "14.0", "Unexpected minimum macOS version")
    require(
        product["architectures"] == ["arm64"],
        "本阶段只支持 arm64",
    )
    require(driver["device_name"] == "TapSay Audio 2ch", "Unexpected device name")
    require(
        driver["device_uid"] == "com.leafney.tapsay.audio.device.2ch",
        "Unexpected device UID",
    )
    require(
        driver["bundle_identifier"] == "com.leafney.tapsay.audio.driver",
        "Unexpected driver bundle identifier",
    )
    require(
        driver["package_receipt_identifier"] == "com.leafney.tapsay.audio.pkg",
        "Unexpected package receipt identifier",
    )
    require(
        uninstaller["bundle_identifier"] == "com.leafney.tapsay.audio.uninstaller",
        "Unexpected uninstaller bundle identifier",
    )
    require(driver["channels"] == 2, "The device must expose exactly two channels")
    rates = [8000, 16000, 24000, 44100, 48000, 88200, 96000,
             176400, 192000, 352800, 384000, 705600, 768000]
    require(driver["sample_rates_hz"] == rates, "采样率列表必须与参考一致")
    require(driver["default_sample_rate_hz"] == 48000, "默认采样率必须是 48000 Hz")
    require(driver["transport_type"] == "usb", "设备 transport 必须是 USB")
    require(driver["hidden_device_uids"] == ["com.leafney.tapsay.audio.device.2ch.2"], "隐藏设备 UID 不匹配")
    if args.profile is not None:
        raise ValueError("正式构建不接受实验 profile")
    factory_uuid = str(uuid.UUID(driver["plugin_factory_uuid"])).upper()
    require(
        factory_uuid == driver["plugin_factory_uuid"],
        "plugin_factory_uuid must be a canonical uppercase UUID",
    )
    interface_uuid = str(uuid.UUID(driver["audio_server_plugin_type_uuid"])).upper()
    require(
        interface_uuid == driver["audio_server_plugin_type_uuid"],
        "audio_server_plugin_type_uuid must be a canonical uppercase UUID",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", upstream["commit"]) is not None,
        "Upstream commit must be a full 40-character Git object ID",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", upstream["archive_sha256"]) is not None,
        "Upstream archive_sha256 must be a full SHA-256 digest",
    )
    require(
        upstream["license"] == "GPL-3.0",
        "Unexpected upstream license classification",
    )

    identities = [
        driver["device_uid"],
        driver["box_uid"],
        driver["model_uid"],
        driver["bundle_identifier"],
        driver["package_receipt_identifier"],
        uninstaller["bundle_identifier"],
    ]
    require(len(identities) == len(set(identities)), "Product identifiers collide")
    label = ""
    print(f"Metadata valid{label}: {METADATA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Metadata validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
