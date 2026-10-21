# 重建阶段四：独立 arm64 分发

依据：`docs/plan/2026-10-21-reference-driver-cleanup.md`。

## 交付

- `scripts/build-packages.sh` 只生成 Apple Silicon `arm64` 资产；不再循环构建 Intel。
- `scripts/build-native-tools.sh` 只生成 arm64 事务工具、卸载工具、诊断工具和环回工具。
- PKG 仍采用空根目录载荷，驱动通过包内 `preinstall`/`postinstall` 事务部署；安装路径、收据、Bundle ID 和 UID 只允许 TapSay 自有值。
- DMG 内含 `TapSayAudio-2ch-0.1.0.pkg`、`卸载 TapSay Audio.app`、中文说明、GPLv3 和第三方许可说明。
- `README.md`、DMG 说明和卸载 App 内置产品合同同步为 arm64、默认 48 kHz、完整 13 项采样率。
- `check-package.py`、`check-release-readiness.py` 已拒绝/不再要求 Intel 资产；发行检查仍明确标记未签名、未公证、未发布下载地址。

## 构建结果

执行 `bash scripts/build-packages.sh`，提权后退出码 0。首次受限环境执行时 `hdiutil` 报“设备未配置”；提权重试成功。

| 资产 | SHA-256 |
| --- | --- |
| `dist/TapSayAudio-2ch-0.1.0-arm64.pkg` | `6e9995bee33ff9d1b02a013195dc9ea473d7e33c06ba37f9f1338061e2941cd3` |
| `dist/TapSayAudio-2ch-0.1.0-arm64.dmg` | `f3bcdaf67c0d0c0268e7706d272fb4bfb8a18e02a1c2795c574be221f077fd35` |
| `dist/TapSayAudio-2ch-0.1.0-source.tar.gz` | `8222118b9d2de3773cabaf48102f5fbf02849665ecdac0eed394d78dae58e873` |

PKG 检查通过：收据、驱动 Bundle/版本/构建号、工厂 UUID、arm64 Mach-O、TapSay UID/名称、安装脚本、原生事务工具和 GPL/来源材料均通过；二进制不含 `BlackHole`、`MiRemoteV` 或无线麦签名 Team ID。DMG 创建成功，源码归档生成成功。

## 隔离事务验证边界

阶段四未写入 `/Library/Audio/Plug-Ins/HAL/`，未重载 CoreAudio，未卸载现有 MiRemoteV，未删除 `.build/experiments/evidence` 或 `preinstall-backup`。现有 Swift 事务测试和卸载结果协议保留，真实安装、覆盖、降级、卸载、设备消失和重启提示属于阶段六真实验收。

发行检查结果仍为“不可正式发布”：本地 PKG 未签名，Developer ID/公证、GitHub Release、真实下载地址和真实音频链路尚未完成。未把本地资产地址写入主程序配置。
