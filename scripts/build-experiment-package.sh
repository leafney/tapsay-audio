#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 reference-48k|reference-16k arm64|x86_64" >&2
    exit 2
fi

PROFILE="$1"
ARCH="$2"
case "$PROFILE" in
    reference-48k|reference-16k) ;;
    *) echo "Unknown reference profile: $PROFILE" >&2; exit 2 ;;
esac
case "$ARCH" in
    arm64|x86_64) ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 2 ;;
esac

python3 "$ROOT/scripts/check-metadata.py" --profile "$PROFILE"
DRIVER="$ROOT/.build/driver/profiles/$PROFILE/$ARCH/Build/Products/Release/TapSayAudio.driver"
TRANSACTION="$ROOT/.build/native/$ARCH/TapSayAudioTransaction"
BUILD_ID="$$"
SOURCE_COMMIT="$(git -C "$ROOT" rev-parse --short=12 HEAD)"
OUTPUT_DIR="$ROOT/.build/experiments/$PROFILE/$ARCH/$SOURCE_COMMIT"
PACKAGE="$OUTPUT_DIR/TapSayAudio-Reference-$PROFILE-$ARCH-$SOURCE_COMMIT.pkg"
PACKAGE_INFO="$OUTPUT_DIR/PACKAGE-INFO.json"
OUTPUT_MANIFEST="$OUTPUT_DIR/EXPERIMENT-MANIFEST.json"
STAGING="$OUTPUT_DIR/.package-scripts-$BUILD_ID"
EMPTY_ROOT="$OUTPUT_DIR/.empty-root-$BUILD_ID"
TEMP_PACKAGE="$OUTPUT_DIR/.TapSayAudio-Reference-$PROFILE-$ARCH-$SOURCE_COMMIT-$BUILD_ID.pkg"
MANIFEST="$ROOT/.build/generated/$PROFILE/profile-manifest.json"
BUILD_EVIDENCE="$(dirname "$DRIVER")/build-evidence.json"
REFERENCE_AUDIT="$(dirname "$DRIVER")/reference-audit.json"

if [[ ! -d "$DRIVER" ]]; then
    echo "Reference driver is missing; build it first: $DRIVER" >&2
    exit 1
fi
if [[ ! -x "$TRANSACTION" ]]; then
    echo "Native transaction tool is missing; build native tools first: $TRANSACTION" >&2
    exit 1
fi
if [[ ! -f "$MANIFEST" ]]; then
    echo "Reference profile manifest is missing; build the profile first: $MANIFEST" >&2
    exit 1
fi
if [[ ! -f "$BUILD_EVIDENCE" || ! -f "$REFERENCE_AUDIT" ]]; then
    echo "Missing build evidence or reference audit; rebuild and audit this architecture first." >&2
    exit 1
fi
if [[ -e "$PACKAGE" || -e "$PACKAGE_INFO" || -e "$OUTPUT_MANIFEST" ]]; then
    echo "Refusing to overwrite existing experiment outputs in: $OUTPUT_DIR" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
if [[ -e "$STAGING" || -e "$EMPTY_ROOT" || -e "$TEMP_PACKAGE" ]]; then
    echo "Refusing to reuse an existing temporary package path." >&2
    exit 1
fi
cleanup() {
    rm -f "$TEMP_PACKAGE"
    rm -rf "$STAGING" "$EMPTY_ROOT"
}
trap cleanup EXIT
mkdir "$STAGING" "$EMPTY_ROOT"
mkdir -p "$STAGING/package-payload"
cp -R "$DRIVER" "$STAGING/package-payload/TapSayAudio.driver"
mkdir -p "$STAGING/package-payload/TapSayAudio.driver/Contents/Resources"
DRIVER_SHA="$(/usr/bin/shasum -a 256 "$DRIVER/Contents/MacOS/TapSayAudio" | /usr/bin/awk '{print $1}')"
python3 - "$MANIFEST" "$STAGING/experiment-manifest.json" "$PROFILE" "$ARCH" "$SOURCE_COMMIT" "$DRIVER_SHA" "$ROOT" "$BUILD_EVIDENCE" "$REFERENCE_AUDIT" <<'PY'
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

source_manifest, output_manifest, profile, architecture, source_commit, driver_sha, root, evidence_path, audit_path = sys.argv[1:]
root = Path(root)
evidence = json.loads(Path(evidence_path).read_text())
audit = json.loads(Path(audit_path).read_text())
if (evidence.get("driver_sha256") != driver_sha or audit.get("driver_sha256") != driver_sha
        or audit.get("status") != "passed"
        or audit.get("build_evidence_sha256") != hashlib.sha256(Path(evidence_path).read_bytes()).hexdigest()
        or evidence["effective_settings"].get("ARCHS") != architecture
        or not evidence.get("source_commit", "").startswith(source_commit)):
    raise SystemExit("构建证据、参考核对、源码提交或驱动产物不匹配")
for path, digest in evidence["source_sha256"].items():
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
        raise SystemExit("构建后源码已改变，请重新构建：" + path)
manifest = json.loads(Path(source_manifest).read_text(encoding="utf-8"))
metadata = json.loads((root / "config/product.json").read_text(encoding="utf-8"))
manifest["product_identity"] = dict(metadata["driver"])
manifest["product_identity"]["default_sample_rate_hz"] = manifest["default_sample_rate_hz"]
manifest["product_identity"]["sample_rates_hz"] = manifest["sample_rates_hz"]
manifest["product_identity"]["hidden_device_uids"] = [manifest["device2"]["uid"]]
frozen = (root / "docs/implementation/2026-10-20-driver-reference-freeze.md").read_text(encoding="utf-8")
patch_match = re.search(r"无线麦补丁.*?SHA-256 `([0-9a-f]{64})`", frozen)
if not patch_match:
    raise SystemExit("无法从参考冻结记录读取无线麦补丁散列")
changes = subprocess.check_output(
    ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
    text=True,
).splitlines()
if changes != evidence.get("source_changes"):
    raise SystemExit("构建后工作区状态已改变，请从当前源码重新构建")
xcode = subprocess.check_output(["xcodebuild", "-version"], text=True).splitlines()
sdk_version = subprocess.check_output(
    ["xcrun", "--sdk", "macosx", "--show-sdk-version"], text=True
).strip()
manifest.update({
    "architecture": architecture,
    "source_commit": source_commit,
    "source_worktree_dirty": bool(changes),
    "source_changes": changes,
    "upstream_commit": metadata["upstream"]["commit"],
    "upstream_archive_sha256": metadata["upstream"]["archive_sha256"],
    "reference_patch_sha256": patch_match.group(1),
    "xcode": xcode,
    "sdk": {"name": "macosx", "version": sdk_version},
    "deployment_target": metadata["product"]["minimum_macos"],
    "build_settings": evidence["effective_settings"],
    "build_evidence": evidence,
    "build_evidence_sha256": hashlib.sha256(Path(evidence_path).read_bytes()).hexdigest(),
    "reference_audit": audit,
    "approved_exceptions": audit["approved_exceptions"],
    "package_signing": "unsigned local experiment",
    "driver_sha256": driver_sha,
    "reference_patch_sha256_source": "frozen implementation record",
})
Path(output_manifest).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY
cp "$STAGING/experiment-manifest.json" "$STAGING/package-payload/TapSayAudio.driver/Contents/Resources/TapSayAudio-experiment-manifest.json"
cp "$TRANSACTION" "$STAGING/TapSayAudioTransaction"
cp "$ROOT/config/product.json" "$STAGING/product.json"
cp "$ROOT/packaging/pkg-scripts/preinstall" "$ROOT/packaging/pkg-scripts/postinstall" "$STAGING/"
chmod 755 "$STAGING/preinstall" "$STAGING/postinstall" "$STAGING/TapSayAudioTransaction"

VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["product"]["version"])' "$ROOT/config/product.json")"
MINIMUM_MACOS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["product"]["minimum_macos"])' "$ROOT/config/product.json")"
RECEIPT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["driver"]["package_receipt_identifier"])' "$ROOT/config/product.json")"
/usr/bin/pkgbuild \
    --root "$EMPTY_ROOT" \
    --scripts "$STAGING" \
    --identifier "$RECEIPT" \
    --version "$VERSION" \
    --install-location / \
    --min-os-version "$MINIMUM_MACOS" \
    "$TEMP_PACKAGE"

python3 "$ROOT/scripts/check-package.py" "$TEMP_PACKAGE" "$ARCH" "$PROFILE"
mv -n "$TEMP_PACKAGE" "$PACKAGE"
if [[ ! -f "$PACKAGE" || -e "$TEMP_PACKAGE" ]]; then
    echo "Could not publish experiment package without overwriting an existing file." >&2
    exit 1
fi
cp "$STAGING/experiment-manifest.json" "$OUTPUT_MANIFEST"
PACKAGE_SHA="$(/usr/bin/shasum -a 256 "$PACKAGE" | /usr/bin/awk '{print $1}')"
MANIFEST_SHA="$(/usr/bin/shasum -a 256 "$OUTPUT_MANIFEST" | /usr/bin/awk '{print $1}')"
python3 - "$PACKAGE_INFO" "$PROFILE" "$ARCH" "$SOURCE_COMMIT" "$DRIVER_SHA" "$PACKAGE_SHA" "$MANIFEST_SHA" <<'PY'
import json
import sys
from pathlib import Path

path, profile, architecture, source_commit, driver_sha, package_sha, manifest_sha = sys.argv[1:]
Path(path).write_text(json.dumps({
    "profile": profile,
    "architecture": architecture,
    "source_commit": source_commit,
    "driver_sha256": driver_sha,
    "package_sha256": package_sha,
    "manifest_sha256": manifest_sha,
    "installation_check": "not_run",
    "real_audio_check": "not_run",
}, indent=2) + "\n", encoding="utf-8")
PY

echo "Experiment package built: $PACKAGE"
echo "Package SHA-256: $PACKAGE_SHA"
