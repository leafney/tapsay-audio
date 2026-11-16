# GitHub Actions 双架构构包验收

日期：2026-11-16

相关规格：`docs/plan/2026-11-16-github-actions-packaging.md`

## 当前范围

项目提供两条独立流水线：

| 入口 | 触发方式 | 签名 | 产物去向 |
| --- | --- | --- | --- |
| `build-artifacts.yml` | 只能手动触发 | 固定 ad hoc | 14 天有效期的 Actions Artifacts |
| `release.yml` | 推送严格的 `vX.Y.Z` Tag | 固定 Developer ID、公证和 staple | GitHub Pre-release |

手动入口不会创建 Release。Tag 入口不会降级为 ad hoc 签名。触发方式决定产物去向，签名要求由入口固定。

支持矩阵：

| 架构 | GitHub Runner | 最低系统 |
| --- | --- | --- |
| arm64 | `macos-15` | macOS 14.0 |
| x86_64 | `macos-15-intel` | macOS 14.0 |

## 版本规则

手动入口保留 `config/product.json` 中的版本。Tag 入口只接受：

```text
v<major>.<minor>.<patch>
```

例如 `v0.2.0` 会写入产品版本 `0.2.0`。不接受预发布后缀、前导零或多段版本。构建号统一使用 GitHub Actions 的 `run_number`，不要求手工修改 `config/product.json`。

构建元数据脚本只修改工作区中的有效配置，不提交版本变更，也不移动 Tag：

```bash
python3 scripts/prepare-build-metadata.py \
  --mode manual \
  --build-number 123 \
  --config config/product.json \
  --output-json .build/build-metadata.json
```

Tag 构建将 `--mode` 改为 `tag`，并传入 `--tag v0.2.0`。

## 手动构建与测试

在 GitHub 仓库中打开 **Actions → Build Internal Artifacts → Run workflow**。工作流会并行执行 arm64 与 x86_64：

1. 校验 Runner 架构与目标架构一致。
2. 写入本次构建号和有效版本。
3. 运行配置、源码、驱动合同和安装事务测试。
4. 构建驱动、原生工具、PKG、卸载 APP 和 DMG。
5. 使用 ad hoc 签名。
6. 检查 PKG、DMG、卸载工具、Mach-O 架构和 macOS 14.0 最低系统。
7. 上传该架构的 DMG、PKG 和单架构 `SHA256SUMS.txt`。

Artifact 名称格式：

```text
TapSayAudio-2ch-<版本>-arm64-build-<构建号>
TapSayAudio-2ch-<版本>-x86_64-build-<构建号>
```

内部测试步骤：

1. 从对应 Actions 运行页面下载架构 ZIP。
2. 解压后先验证散列。
3. 在匹配架构的 Mac 上打开 DMG。
4. 双击 DMG 中的 PKG 完成安装。
5. 打开小声点，选择 `TapSay Audio 2ch` 进行语音链路测试。
6. 测试结束后运行 DMG 中的卸载工具。
7. 返回 GitHub Releases 页面，确认本次手动运行没有新增 Release。

散列验证：

```bash
shasum -a 256 -c SHA256SUMS.txt
```

检查 Mach-O 架构和最低系统：

```bash
lipo -archs /path/to/TapSayAudio
xcrun vtool -show-build /path/to/TapSayAudio
```

## 正式发布凭据

正式 Tag 发布需要以下 GitHub Actions Secrets：

```text
DEVELOPER_ID_APPLICATION_P12_BASE64
DEVELOPER_ID_APPLICATION_P12_PASSWORD
DEVELOPER_ID_INSTALLER_P12_BASE64
DEVELOPER_ID_INSTALLER_P12_PASSWORD
APPLE_TEAM_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64
```

`.p12` 和 `.p8` 文件需要先转成单行 Base64。不要在仓库、Issue、聊天或日志中保存原始证书、私钥和密码。

工作流会创建临时 Keychain，分别导入 Developer ID Application 和 Developer ID Installer 身份。证书身份由 Runner 实际枚举，不把完整证书名称写成仓库常量的必要条件。

## 正式 Tag 发布

证书和 Secrets 配置完成后：

1. 确认代码与测试已经进入要发布的提交。
2. 创建并推送严格格式的 Tag，例如 `v0.2.0`。
3. `release.yml` 从 Tag 生成版本，两个 Runner 使用同一个 `run_number`。
4. 两个架构分别完成 Developer ID 签名、PKG `productsign`、DMG 公证、staple 和系统策略验证。
5. 任一架构失败时，发布任务不会运行。
6. 两个架构都成功后才创建 Pre-release。

公开 Release 只包含：

```text
TapSayAudio-2ch-<版本>-arm64.dmg
TapSayAudio-2ch-<版本>-x86_64.dmg
TapSayAudio-2ch-<版本>-source.tar.gz
SHA256SUMS.txt
```

独立 PKG、构建记录和临时文件不会进入公开 Release。同名 Release 已存在时工作流失败，不覆盖原 Release。

## 本地验收命令

```bash
python3 scripts/check-metadata.py
python3 Tests/ReleaseToolsTests.py
python3 Tests/DriverSourceTests.py
bash scripts/build-packages.sh \
  --arch arm64 \
  --output /private/tmp/tapsay-audio-arm64-test
```

本机没有 Developer ID 证书时只运行 ad hoc 单架构构包。不要推送 Tag 测试正式发布。

## 验收记录

- 本地 arm64 全链路：通过。测试基于提交 `d0391a963a5be968fd42fc089909ec94467fbcaf`，产物目录为 `/private/tmp/tapsay-audio-arm64-test`。
- 配置、ReleaseTools 与驱动源码测试：全部通过。
- arm64 驱动和四个原生工具：架构检查通过，最低系统均为 macOS 14.0。
- HAL 合同：格式、插件属性和控制列表矩阵全部通过。
- 隔离安装事务：安装、覆盖、故障恢复、卸载与结果协议全部通过。
- PKG、DMG 与卸载 APP：内容和架构检查通过。
- `/usr/bin/shasum -a 256 -c SHA256SUMS.txt`：PKG 与 DMG 均为 `OK`。
- 本地包为 ad hoc 内部测试包，不代表 Developer ID 签名或 Apple 公证已通过。

arm64 实测散列：

```text
fc268a262a83a3f2d3c3eec4c988c43c067580de219081f9899b7f2c77c4a320  TapSayAudio-2ch-0.1.1-arm64.pkg
1962f4674d2a3d2d5f1e74963f25ec18f6b73f115c5ee40a06886243a9c4bbc9  TapSayAudio-2ch-0.1.1-arm64.dmg
```

- x86_64 原生构建：等待 GitHub `macos-15-intel` Runner 执行。
- GitHub 手动双架构 Artifact：待第 9 阶段记录。
- 正式 Tag 发布：证书配置完成前不执行。
