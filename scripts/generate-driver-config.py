#!/usr/bin/env python3
"""Generate the C identity and audio defaults from the product metadata."""

import json
import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "product.json"
OUTPUT = ROOT / "Driver" / "TapSayAudio" / "TapSayAudioBuildConfig.h"


def c_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    product = data["product"]
    driver = data["driver"]
    rates = ", ".join(str(rate) for rate in driver["sample_rates_hz"])
    definitions = [
        "/* Generated from config/product.json. Do not edit by hand. */",
        f"#define TAPSAY_PRODUCT_NAME {c_string(product['name'])}",
        f"#define TAPSAY_PRODUCT_VERSION {c_string(product['version'])}",
        f"#define TAPSAY_DEFAULT_SAMPLE_RATE {driver['default_sample_rate_hz']}.0",
        f"#define kPlugIn_BundleID {c_string(driver['bundle_identifier'])}",
        f"#define kBox_UID {c_string(driver['box_uid'])}",
        f"#define kDevice_UID {c_string(driver['device_uid'])}",
        f"#define kDevice_ModelUID {c_string(driver['model_uid'])}",
        f"#define kDevice_Name {c_string(driver['device_name'])}",
        '#define kDevice2_Name ""',
        "#define kDevice_IsHidden false",
        "#define kDevice2_IsHidden true",
        "#define kDevice_HasInput true",
        "#define kDevice_HasOutput true",
        f"#define kManufacturer_Name {c_string(driver['manufacturer'])}",
        f"#define kNumber_Of_Channels {driver['channels']}",
        f"#define kSampleRates {rates}",
    ]
    OUTPUT.write_text("\n".join(definitions) + "\n", encoding="utf-8")
    plist_path = ROOT / "Driver" / "TapSayAudio" / "TapSayAudio.plist"
    info = plistlib.loads(plist_path.read_bytes())
    info["CFPlugInFactories"] = {driver["plugin_factory_uuid"]: "TapSayAudio_Create"}
    info["CFPlugInTypes"] = {driver["audio_server_plugin_type_uuid"]: [driver["plugin_factory_uuid"]]}
    plist_path.write_bytes(plistlib.dumps(info, sort_keys=False))
    print(f"Generated {OUTPUT.relative_to(ROOT)} and plugin registration")


if __name__ == "__main__":
    main()
