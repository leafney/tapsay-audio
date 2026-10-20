#!/usr/bin/env python3
"""Check a built HAL bundle against the approved product identity."""

import json
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = json.loads((ROOT / "config" / "product.json").read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    require(len(sys.argv) in (3, 4),
            "Usage: check-driver-artifact.py DRIVER_BUNDLE EXPECTED_ARCH [PROFILE]")
    bundle = Path(sys.argv[1]).resolve()
    expected_arch = sys.argv[2]
    profile = sys.argv[3] if len(sys.argv) == 4 else None
    info_path = bundle / "Contents" / "Info.plist"
    executable = bundle / "Contents" / "MacOS" / METADATA["driver"]["executable_name"]
    require(info_path.is_file(), f"Missing Info.plist: {info_path}")
    require(executable.is_file(), f"Missing driver executable: {executable}")

    with info_path.open("rb") as stream:
        info = plistlib.load(stream)

    product = METADATA["product"]
    driver = METADATA["driver"]
    expected_default_rate = driver["default_sample_rate_hz"]
    expected_rates = driver["sample_rates_hz"]
    expected_device2_uid = None
    expected_device2_name = None
    if profile:
        profile_data = json.loads((ROOT / "config" / "driver-profiles.json").read_text(encoding="utf-8"))
        require(profile in profile_data["profiles"], f"Unknown profile: {profile}")
        expected_default_rate = profile_data["profiles"][profile]["default_sample_rate_hz"]
        expected_rates = profile_data["sample_rates_hz"]
        expected_device2_uid = profile_data["device2"]["uid"]
        expected_device2_name = profile_data["device2"]["name"]
    expected_factories = {
        driver["plugin_factory_uuid"]: "TapSayAudio_Create"
    }
    expected_types = {
        driver["audio_server_plugin_type_uuid"]: [driver["plugin_factory_uuid"]]
    }
    require(info.get("CFBundleIdentifier") == driver["bundle_identifier"], "Driver Bundle ID mismatch")
    require(info.get("CFBundleExecutable") == driver["executable_name"], "Driver executable name mismatch")
    require(info.get("CFBundleShortVersionString") == product["version"], "Driver version mismatch")
    require(info.get("CFBundleVersion") == product["build_number"], "Driver build number mismatch")
    require(info.get("CFPlugInFactories") == expected_factories, "CFPlugInFactories mismatch")
    require(info.get("CFPlugInTypes") == expected_types, "CFPlugInTypes mismatch")
    if profile:
        require(info.get("TapSayAudioProfile") == profile, "Embedded profile mismatch")
        require(info.get("TapSayAudioDefaultSampleRate") == expected_default_rate,
                "Embedded default sample rate mismatch")
        require(info.get("TapSayAudioSupportedSampleRates") == expected_rates,
                "Embedded supported rates mismatch")

    archs = subprocess.check_output(["/usr/bin/lipo", "-archs", str(executable)], text=True).split()
    require(archs == [expected_arch], f"Expected only {expected_arch}; found {archs}")

    binary_strings = subprocess.check_output(["/usr/bin/strings", str(executable)], text=True)
    require(driver["device_uid"] in binary_strings, "Device UID missing from executable")
    require(driver["device_name"] in binary_strings, "Device name missing from executable")
    if profile:
        require(expected_device2_uid in binary_strings, "Hidden device UID missing from executable")
        require(expected_device2_name in binary_strings, "Hidden device name missing from executable")
    require(driver["plugin_factory_uuid"] in info["CFPlugInTypes"][driver["audio_server_plugin_type_uuid"]][0].upper(), "Factory UUID missing from plugin types")
    for forbidden in ("BlackHole", "MiRemoteV", "Q5C99V536K"):
        require(forbidden not in binary_strings, f"Upstream identity leaked into executable: {forbidden}")

    report = {
        "bundle": str(bundle), "architecture": expected_arch,
        "bundle_identifier": info["CFBundleIdentifier"],
        "version": info["CFBundleShortVersionString"],
        "build_number": info["CFBundleVersion"],
        "factory_uuid": driver["plugin_factory_uuid"],
        "profile": profile or "legacy",
        "default_sample_rate_hz": expected_default_rate,
        "supported_sample_rates_hz": expected_rates,
        "static_identity_check": "passed", "installed_device_check": "not_run",
        "audio_chain_check": "not_run", "intel_hardware_check": "not_run"
    }
    (bundle.parent / "identity-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Artifact identity valid: {bundle} ({expected_arch})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Driver artifact validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
