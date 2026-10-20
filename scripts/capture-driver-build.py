#!/usr/bin/env python3
"""Save effective settings from the same command used to build the driver."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def settings_from_output(text):
    # Some Xcode versions interleave simulator diagnostics with JSON output.
    match = re.search(r'\[\s*\{\s*"action"\s*:', text)
    if not match:
        raise ValueError("Xcode did not return build settings")
    entries, _ = json.JSONDecoder().raw_decode(text[match.start():])
    return next(item["buildSettings"] for item in entries if item["target"] == "TapSayAudio")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = Path(sys.argv[1])
    command = sys.argv[3:]
    if sys.argv[2] != "--" or not command or command[-1] != "build":
        raise ValueError("Usage: capture-driver-build.py OUTPUT -- xcodebuild ... build")
    if output.exists():
        output.unlink()
    query = command[:-1] + ["-showBuildSettings", "-json"]
    result = subprocess.run(query, check=True, capture_output=True, text=True)
    settings = settings_from_output(result.stdout)
    sources = [
        ROOT / "Driver/TapSayAudio/TapSayAudio.c",
        ROOT / "Driver/TapSayAudio.xcodeproj/project.pbxproj",
        Path(settings["INFOPLIST_FILE"]),
        Path(settings["HEADER_SEARCH_PATHS"]) / "TapSayAudioBuildConfig.h",
        ROOT / "scripts/build-driver.sh",
        Path(__file__),
    ]
    before = {str(path): sha256(path) for path in sources}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changes = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    ).splitlines()
    subprocess.run(command, check=True)
    if before != {str(path): sha256(path) for path in sources}:
        raise ValueError("Driver build inputs changed during compilation")
    executable = Path(settings["TARGET_BUILD_DIR"]) / settings["EXECUTABLE_PATH"]
    report = {
        "source_commit": commit,
        "source_changes": changes,
        "build_command": command,
        "settings_command": query,
        "effective_settings": settings,
        "source_sha256": before,
        "driver_sha256": sha256(executable),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(output)
    print(f"Build evidence saved: {output}")


if __name__ == "__main__":
    main()
