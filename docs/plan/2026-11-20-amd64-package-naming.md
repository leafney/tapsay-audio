Related discussion: [docs/discuss/2026-11-20-amd64-package-naming.md](../discuss/2026-11-20-amd64-package-naming.md)

# Intel 安装包命名调整

## 目标

手动构建和 Tag 发布的 Intel 安装包文件名使用 `amd64`，与 Apple Silicon 的 `arm64` 命名对应。`amd64` 与 `x86_64` 在此仅表示同一目标架构的不同名称；实际编译与校验继续使用 `x86_64`。

## 命名规则

- Intel 手动构建 DMG：`TapSayAudio-2ch-<版本>-amd64.dmg`。
- Intel 认证 Release DMG：`TapSayAudio-2ch-<版本>-amd64.dmg`。
- Intel 未认证 Release DMG：`TapSayAudio-2ch-<版本>-amd64-Unverified.dmg`。
- DMG 内的 Intel PKG：`TapSayAudio-2ch-<版本>-amd64.pkg`。`Unverified` 仅用于公开未认证 DMG 的现有命名规则。
- Apple Silicon 命名保持原样。`SHA256SUMS.txt` 必须引用实际生成的文件名并匹配散列。
- 手动 Actions Artifact 的容器名也使用 `amd64`，方便用户辨认；相应 Release 下载步骤必须同步使用该容器名。历史 Artifact 和 Release 不修改。

## 具体实施

1. 在共享的产品工具中集中提供文件名架构映射：`arm64 → arm64`、`x86_64 → amd64`，未知值报错。构建参数、配置字段、脚本命令参数、Swift 架构识别、`uname`、`lipo` 和 `vtool` 检查仍使用原始架构，不得把实际构建架构改为 `amd64`。
2. 修改 `scripts/build-packages.py` 的 DMG 和内部 PKG 前缀；手动产物的校验文件跟随实际文件名。保持包收据、驱动身份和内容不变。
3. 修改 `scripts/check-dmg.py` 的 DMG 及内部 PKG 文件名期望，仍按传入的 `x86_64` 检查真实载荷架构。区分未认证公开 DMG 的 `-Unverified` 后缀与内部 PKG 的名称。
4. 修改 `scripts/assemble-release.py` 输入文件、公开文件命名及校验；修改 `scripts/release_checks.py`、`scripts/publish-github-release.py` 的预期资产名。继续严格检查双架构、资产集合、散列、签名和公证，不通过跳过校验来实现重命名。
5. 修改 `.github/workflows/package-arch.yml` 的 Artifact 容器命名，并同步 `.github/workflows/release.yml` 的下载名称；确认两种工作流输出一致，不能把工作流实际架构参数改成 `amd64`。
6. 更新 `README.md` 和当前用户文档中关于下载文件的说明，明确 Intel 用户选择 `amd64`，内部架构仍为 `x86_64`。保留历史记录，不修改已发布版本。

## 验证与验收

- 测试映射、未知架构拒绝，以及 Intel 和 Apple Silicon 的 DMG、PKG 和 Artifact 命名。
- 测试认证与未认证发布的资产集合、`Unverified` 后缀、校验文件与实际散列；错误架构或旧文件名应被既有校验拒绝。
- 测试手动构建上传与 Tag 发布下载使用同一个 Artifact 名称；确保内部真实架构仍为 `x86_64`，最低系统仍为 macOS 13。
- 运行 `python3 Tests/ReleaseToolsTests.py`、相关发布说明测试及 `git diff --check`。如未实际运行 GitHub Actions 或 macOS 打包，明确报告限制；不得声称已验证真实安装包。
- 不修改现有 Release，不推送 Tag，不主动触发 GitHub Actions；后续由用户自行发布和验证。

本规划获用户明确批准后才开始实施；若实施中需要变更规划，先更新并取得批准。
