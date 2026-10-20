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
    parser.add_argument("--profile", choices=("reference-48k", "reference-16k"))
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
        product["architectures"] == ["arm64", "x86_64"],
        "Architectures must be arm64 and x86_64 in this order",
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
    if args.profile is None:
        require(
            driver["sample_rates_hz"] == [16000, 44100, 48000],
            "Unexpected supported sample rates",
        )
        require(
            driver["default_sample_rate_hz"] == 16000,
            "The default sample rate must be 16000 Hz",
        )
        require(driver["transport_type"] == "usb", "Unexpected transport type")
        require(
            driver["hidden_device_uids"] == [],
            "TapSay must not publish hidden audio devices",
        )
    else:
        profile_path = ROOT / "config" / "driver-profiles.json"
        profiles = json.loads(profile_path.read_text(encoding="utf-8"))
        rates = profiles["sample_rates_hz"]
        require(
            rates == [8000, 16000, 24000, 44100, 48000, 88200, 96000,
                      176400, 192000, 352800, 384000, 705600, 768000],
            "Reference sample-rate list must match the ordered upstream list",
        )
        require(
            set(profiles["profiles"]) == {"reference-48k", "reference-16k"},
            "Unexpected reference profiles",
        )
        require(
            all(set(profile) == {"default_sample_rate_hz"} for profile in profiles["profiles"].values()),
            "Profiles may differ only by default_sample_rate_hz",
        )
        require(
            profiles["profiles"]["reference-48k"]["default_sample_rate_hz"] == 48000,
            "reference-48k must default to 48000 Hz",
        )
        require(
            profiles["profiles"]["reference-16k"]["default_sample_rate_hz"] == 16000,
            "reference-16k must default to 16000 Hz",
        )
        require(
            profiles["profiles"]["reference-48k"] != profiles["profiles"]["reference-16k"],
            "Reference profiles must differ by their default sample rate",
        )
        require(profiles["device"]["channels"] == 2, "Reference device must be stereo")
        require(profiles["device"]["hidden"] is False, "Primary device must be visible")
        require(profiles["device"]["has_input"] and profiles["device"]["has_output"],
                "Primary device must expose input and output")
        require(profiles["device"]["transport"] == "usb", "Device transport must be USB")
        require(profiles["box_transport"] == "virtual", "Box transport must be Virtual")
        require(profiles["latency_frame_size"] == 0, "Latency must remain zero")
        require(profiles["device_ring_buffer_size"] == 16384,
                "Device ring-buffer period must match upstream")
        require(profiles["ring_buffer_frame_size"] == 65536,
                "Ring-buffer frame count must match upstream")
        require(profiles["device2"]["hidden"] is True, "Second device must remain hidden")
        require(profiles["device2"]["uid"] == "com.leafney.tapsay.audio.device.2ch.2",
                "Unexpected hidden device UID")
        require(profiles["device2"]["name"] == "TapSay Audio 2ch 2",
                "Unexpected hidden device name")
        require(profiles["device2"]["has_input"] and profiles["device2"]["has_output"],
                "Hidden device must expose input and output")
        identities = [
            driver["device_uid"], profiles["device2"]["uid"],
            driver["box_uid"], driver["model_uid"],
            driver["bundle_identifier"], driver["package_receipt_identifier"],
        ]
        require(len(identities) == len(set(identities)), "Profile identities collide")
        require(
            profiles["device2"]["uid"].startswith("com.leafney.tapsay.audio."),
            "Hidden device UID must use the TapSay namespace",
        )

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
    label = f" ({args.profile})" if args.profile else ""
    print(f"Metadata valid{label}: {METADATA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Metadata validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
