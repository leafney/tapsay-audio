#!/usr/bin/env python3
"""Compare a completed build with the frozen reference's effective settings."""

import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_build", ROOT / "scripts/capture-driver-build.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
REFERENCE_SOURCE_SHA = "5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6"
REFERENCE_PROJECT_SHA = "8346211852797b491245302d6ad5d3e6b855d3d07bf37e4d4d5b0e64656a6c88"
IDENTITY_MACROS = {
    "kDriver_Name", "kDriver_Name_Format", "kHas_Driver_Name_Format", "kPlugIn_BundleID",
    "kPlugIn_Icon", "kBox_UID", "kDevice_UID", "kDevice2_UID", "kDevice_ModelUID",
    "kDevice_Name", "kDevice2_Name", "kManufacturer_Name",
}
PATH_SETTINGS = {"LD_DEPENDENCY_INFO_FILE", "LD_MAP_FILE_PATH"}
BUILD_KEYS = {
    "ARCHS", "ONLY_ACTIVE_ARCH", "MACOSX_DEPLOYMENT_TARGET", "MACH_O_TYPE",
    "DEBUG_INFORMATION_FORMAT", "DEAD_CODE_STRIPPING", "COPY_PHASE_STRIP",
    "DEPLOYMENT_POSTPROCESSING", "SDKROOT", "SDK_VERSION", "CC", "CPLUSPLUS",
}
EXCEPTIONS = ["product_identity", "owned_objects_index", "uid_qualifier_validation",
              "hidden_control_list_filter", "brand_resources", "platform_support"]


def read_settings(text):
    match = re.search(r'\[\s*\{\s*"action"\s*:', text)
    if not match:
        raise ValueError("Reference Xcode settings are missing")
    entries, _ = json.JSONDecoder().raw_decode(text[match.start():])
    return next(item["buildSettings"] for item in entries if item["target"] == "BlackHole")


def definitions(value):
    return [item for item in value.split() if item.split("=")[0] not in {
        "kDriver_Name", "kPlugIn_BundleID", "kNumber_Of_Channels",
    }]


def macros(source, settings, reference=False):
    command = ["xcrun", "--sdk", "macosx", "clang", "-E", "-dM",
               "-target", settings["ARCHS"] + "-apple-macosx" + settings["MACOSX_DEPLOYMENT_TARGET"],
               "-isysroot", settings["SDKROOT"], "-DDEBUG=0"]
    if reference:
        command += ['-DkDriver_Name="MiRemoteV"', '-DkPlugIn_BundleID="com.hd838a.MiRemoteV2ch"',
                    "-DkNumber_Of_Channels=2"]
    else:
        command += ["-I", settings["HEADER_SEARCH_PATHS"]]
    result = subprocess.check_output(command + [str(source)]).decode("utf-8", errors="replace")
    return {name: " ".join(value.split()) for name, value in
            re.findall(r"^#define (k\w+) (.*)$", result, re.M) if name not in IDENTITY_MACROS}


def normalize_source(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def main():
    if len(sys.argv) != 3:
        raise ValueError("Usage: audit-reference-build.py REFERENCE_ROOT BUILD_EVIDENCE")
    reference_root, evidence_path = map(Path, sys.argv[1:])
    source = reference_root / "BlackHole/BlackHole.c"
    if capture.sha256(source) != REFERENCE_SOURCE_SHA:
        raise ValueError("Frozen reference source hash mismatch")
    if capture.sha256(reference_root / "BlackHole.xcodeproj/project.pbxproj") != REFERENCE_PROJECT_SHA:
        raise ValueError("Frozen reference project hash mismatch")
    metadata = json.loads((ROOT / "config/product.json").read_text())
    evidence = json.loads(evidence_path.read_text())
    current = evidence["effective_settings"]
    command = [
        "xcodebuild", "-project", str(reference_root / "BlackHole.xcodeproj"),
        "-target", "BlackHole", "-configuration", "Release", "-sdk", "macosx",
        "ARCHS=" + current["ARCHS"], "ONLY_ACTIVE_ARCH=NO", "CODE_SIGNING_ALLOWED=NO",
        "MACOSX_DEPLOYMENT_TARGET=" + metadata["product"]["minimum_macos"],
        "PRODUCT_NAME=MiRemoteV2ch", "PRODUCT_BUNDLE_IDENTIFIER=com.hd838a.MiRemoteV2ch",
        'GCC_PREPROCESSOR_DEFINITIONS=$GCC_PREPROCESSOR_DEFINITIONS kDriver_Name=\\"MiRemoteV\\" kPlugIn_BundleID=\\"com.hd838a.MiRemoteV2ch\\" kNumber_Of_Channels=2',
        "-showBuildSettings", "-json",
    ]
    reference = read_settings(subprocess.check_output(command, text=True, stderr=subprocess.PIPE))
    differences = {key: {"reference": reference.get(key), "current": current.get(key)}
                   for key in sorted(set(reference) | set(current))
                   if reference.get(key) != current.get(key)}
    critical = {key for key in set(reference) | set(current)
                if key.startswith(("GCC_", "CLANG_", "LLVM_", "LD_", "OTHER_", "ENABLE_", "STRIP_"))
                or key in BUILD_KEYS} - PATH_SETTINGS - {"GCC_PREPROCESSOR_DEFINITIONS"}
    failures = [key for key in sorted(critical) if reference.get(key) != current.get(key)]
    if definitions(reference.get("GCC_PREPROCESSOR_DEFINITIONS", "")) != definitions(current.get("GCC_PREPROCESSOR_DEFINITIONS", "")):
        failures.append("GCC_PREPROCESSOR_DEFINITIONS")
    current_source = ROOT / "Driver/TapSayAudio/TapSayAudio.c"
    reference_macros = macros(source, reference, True)
    current_macros = macros(current_source, current)
    macro_differences = {key: {"reference": reference_macros.get(key), "current": current_macros.get(key)}
                         for key in sorted(set(reference_macros) | set(current_macros))
                         if reference_macros.get(key) != current_macros.get(key)}
    if macro_differences:
        failures.append("effective_audio_macros")
    executable = Path(current["TARGET_BUILD_DIR"]) / current["EXECUTABLE_PATH"]
    if capture.sha256(executable) != evidence["driver_sha256"]:
        failures.append("built_driver_hash")
    for path, digest in evidence["source_sha256"].items():
        if capture.sha256(path) != digest:
            failures.append("changed_build_input:" + path)
    source_diff = "\n".join(difflib.unified_diff(
        normalize_source(source.read_text().replace("BlackHole", "TapSayAudio")),
        normalize_source(current_source.read_text()), fromfile="reference", tofile="current"
    )) + "\n"
    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "architecture": current["ARCHS"],
        "build_evidence_sha256": capture.sha256(evidence_path),
        "driver_sha256": evidence["driver_sha256"],
        "reference_source_sha256": capture.sha256(source),
        "reference_project_sha256": capture.sha256(reference_root / "BlackHole.xcodeproj/project.pbxproj"),
        "reference_settings_command": command,
        "reference_effective_settings": reference,
        "all_settings_differences": differences,
        "checked_codegen_settings": sorted(critical),
        "reference_audio_macros": reference_macros,
        "current_audio_macros": current_macros,
        "audio_macro_differences": macro_differences,
        "approved_exceptions": EXCEPTIONS,
        "source_diff": source_diff,
        "source_diff_sha256": hashlib.sha256(source_diff.encode()).hexdigest(),
        "source_review": "manual; full normalized source diff retained, not an automated equivalence proof",
    }
    output = evidence_path.parent / "reference-audit.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        raise ValueError("Reference comparison failed: " + ", ".join(failures))
    print(f"Reference build and audio macros verified: {output}")


if __name__ == "__main__":
    main()
