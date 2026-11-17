# GitHub Actions 双架构构包实施规格

日期：2026-11-16

Related discussion: `docs/discuss/2026-11-16-github-actions-packaging.md`

## Problem Statement

当前 TapSay Audio 的驱动、原生工具、安装包和校验流程均按 arm64 硬编码，项目也没有 GitHub Actions 工作流。维护者目前需要在本地手动执行构包命令，无法在 GitHub 上稳定生成 arm64 与 x86_64 两套安装包，也无法通过一次 Tag 推送完成双架构产物汇总和发布。

用户需要一个自动化流程：

- 手动运行时生成可供内部测试的 Actions Artifacts。
- 推送 `vX.Y.Z` Tag 时生成 macOS 14+ 双架构安装包。
- 当前先使用 ad hoc 临时签名。
- 后续取得 Apple Developer ID 材料和公证凭据后，只需配置 GitHub Secrets，不需要重构构建流程。

## Solution

将现有构建和打包能力改为架构感知的统一流水线，并提供两个独立触发入口。

手动入口：

```text
workflow_dispatch
        ↓
双架构并行构建与校验
        ↓
Actions Artifacts
（DMG、架构校验文件）
```

发布入口：

```text
推送 vX.Y.Z Tag
        ↓
从 Tag 生成版本和构建号
        ↓
双架构并行构建
        ↓
Developer ID 签名与公证
        ↓
合并产物并生成总校验文件
        ↓
GitHub Pre-release
（双架构 DMG、源码归档、SHA256SUMS.txt）
```

触发方式只决定产物去向；签名强度由入口固定决定。

- 手动入口固定使用 ad hoc 签名，不读取开发者证书。
- Tag 入口固定要求 Developer ID 签名、公证和 stapling。
- 不使用证书 Secrets 是否完整来判断应该发布 Artifact 还是 Release。

## User Stories

1. 作为项目维护者，我希望手动运行工作流即可生成 arm64 内部测试包，以便在 Apple Silicon Mac 上验证安装和功能。
2. 作为项目维护者，我希望手动运行工作流即可生成 x86_64 内部测试包，以便在 Intel Mac 上验证安装和功能。
3. 作为项目维护者，我希望手动运行只上传 Actions Artifacts，以便测试未认证版本时不会误发布到 GitHub Releases。
4. 作为项目维护者，我希望每个测试 Artifact 只包含 DMG 和校验文件，以便本地构建、内部测试和公开发布统一使用同一种交付格式。
5. 作为项目维护者，我希望两个架构在独立原生 Runner 上构建，以便真实执行各自架构的原生工具与安装事务测试。
6. 作为项目维护者，我希望 Tag `vX.Y.Z` 自动映射为产品版本 `X.Y.Z`，以便发布前不再手动提交版本修改。
7. 作为项目维护者，我希望 Tag 与手动构建都自动使用 GitHub Actions 运行编号作为构建号，以便区分同一版本的重复构建。
8. 作为项目维护者，我希望所有产物明确校验 macOS 14.0 最低系统，以便符合产品支持范围。
9. 作为项目维护者，我希望错误架构、错误最低版本、缺失文件或错误散列直接使工作流失败，以便不发布不完整产物。
10. 作为项目维护者，我希望任一架构构建失败时都不创建 Pre-release，以便双架构版本保持原子发布。
11. 作为项目维护者，我希望 Tag 构建缺少任何 Developer ID 或公证凭据时直接失败，以便绝不公开未认证包。
12. 作为项目维护者，我希望后续只需把证书和 API Key 配置为 GitHub Secrets，即可启用正式签名流水线。
13. 作为项目维护者，我希望公开 Release 只包含两个 DMG、一个源码归档和一个汇总校验文件，以便降低普通用户的下载选择成本。
14. 作为项目维护者，我希望源码归档包含 Tag、源码提交和实际构建版本信息，以便二进制与对应源码可追溯。
15. 作为项目维护者，我希望不限制 Tag 是否位于 `main` 历史，以便按当前发布习惯自由创建发布 Tag。
16. 作为内部测试人员，我希望从 Actions 运行页面下载明确标注架构的 ZIP，以便选择正确机器测试。
17. 作为内部测试人员，我希望能够验证 DMG 完整性、散列以及内部 PKG 的架构，以便排除下载、构包或安装载荷损坏。
18. 作为后续发布维护者，我希望正式 Tag 发布自动完成签名、公证、staple 和验证，以便日常发布只需要推送 Tag。

## Implementation Decisions

### 工作流入口

建立两个入口工作流：

1. **手动内部构建工作流**
   - 只接受 `workflow_dispatch`。
   - 使用仓库当前产品配置中的版本。
   - 构建号使用 `github.run_number`。
   - 固定采用 ad hoc 临时签名。
   - 不创建、更新或删除 GitHub Release。
   - 为 arm64 和 x86_64 分别上传独立 Artifact。

2. **Tag 发布工作流**
   - 只接受 `vX.Y.Z` 格式的 Tag 推送。
   - 从 Tag 自动生成产品版本。
   - 构建号使用 `github.run_number`。
   - 必须使用 Developer ID 证书完成签名。
   - 必须完成公证、stapling 和发布前验证。
   - 仅在两个架构全部成功后创建 GitHub Pre-release。

两个入口复用同一套底层构建、校验、打包和产物汇总逻辑。

### 版本和配置

- Tag 必须严格匹配 `v<major>.<minor>.<patch>`，不接受预发布后缀、重复分隔符或前导零。
- Tag 去掉 `v` 后作为有效产品版本，例如 `v0.2.0` 对应 `0.2.0`。
- 所有驱动、原生工具、PKG、DMG、源码归档和发布标题必须使用同一个有效版本。
- GitHub Actions 运行编号作为构建号。
- Tag 构建在临时工作区生成有效产品配置，不提交版本修改，不移动 Tag。
- 源码归档必须包含实际参与构建的有效产品配置。
- 源码归档继续记录源码提交 SHA，并补充 Tag 与有效产品版本。
- 不限制 Tag 指向的提交是否在 `main` 历史中。

### 架构矩阵

| 架构 | Runner | 最低系统 |
| --- | --- | --- |
| arm64 | `macos-15` | macOS 14.0 |
| x86_64 | `macos-15-intel` | macOS 14.0 |

两个任务并行执行。任何一个任务失败，最终发布任务不得运行。

### 产品配置

产品元数据从仅允许 arm64 改为显式声明双架构：

- `arm64`
- `x86_64`

构建、打包和校验入口必须拒绝配置之外或不在目标矩阵中的架构。

### 架构感知构建

驱动和原生工具构建接口接受明确的目标架构。构建过程必须：

- 仅在临时工作目录生成驱动源码和中间文件。
- 将目标架构传给 Xcode 和 Swift 编译器。
- 使用 macOS 14.0 deployment target。
- 生成单架构驱动和单架构原生工具，不生成 universal binary。
- 保持现有驱动源码审计、补丁散列和 HAL 合同检查。
- 生成包含架构、版本、构建号、源码位置、驱动散列和补丁散列的构建记录。

### 架构感知打包

每个架构独立发布：

- `TapSayAudio-2ch-<版本>-<架构>.dmg`
- 内部 Artifact 使用的 `SHA256SUMS.txt`

`TapSayAudio-2ch-<版本>-<架构>.pkg` 只在临时工作目录生成并复制进 DMG，不作为独立产物发布。

DMG 继续包含：

- 对应架构的 PKG。
- 对应架构的卸载工具。
- 中文安装说明。
- GPL 许可证。
- 第三方许可说明。

### 签名阶段边界

当前阶段：

- 驱动、卸载工具和相关可执行文件使用 ad hoc 签名。
- 手动 Artifact 不引用任何 Apple 开发者 Secrets。

后续正式认证阶段：

- 使用 Developer ID Application 证书签名驱动、卸载工具和 DMG。
- 使用 Developer ID Installer 证书签名 PKG。
- 使用 App Store Connect Team API Key 调用 Apple 公证服务。
- 公证成功后将票据 staple 到 DMG。
- 运行 `codesign`、`pkgutil`、`spctl`、`stapler` 和 DMG 完整性验证。
- 任一步骤失败都停止 Pre-release 创建。

计划使用的 GitHub Secrets：

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

证书、私钥和密码不得进入仓库、日志或源码归档。

### 手动 Artifact

每个架构的 Artifact 名称包含版本、架构和运行编号，避免不同运行之间混淆。

arm64 Artifact 包含：

- arm64 DMG。
- arm64 PKG。
- 包含 DMG 与 PKG 的 `SHA256SUMS.txt`。

x86_64 Artifact 包含：

- x86_64 DMG。
- x86_64 PKG。
- 包含 DMG 与 PKG 的 `SHA256SUMS.txt`。

手动 Artifact 保留期设为 14 天。手动入口不生成公开源码归档。

### Tag Pre-release

两个架构全部通过后，最终任务：

1. 下载两个架构的 Artifact。
2. 再次核对架构、版本、构建号和散列。
3. 生成一份对应源码归档。
4. 生成仅覆盖公开资产的 `SHA256SUMS.txt`。
5. 检查所有公开资产存在且非空。
6. 检查同名 Release 不存在。
7. 使用 `GITHUB_TOKEN` 创建 Pre-release。
8. 上传双架构 DMG、源码归档和总校验文件。

公开 Pre-release 资产固定为：

```text
TapSayAudio-2ch-<版本>-arm64.dmg
TapSayAudio-2ch-<版本>-x86_64.dmg
TapSayAudio-2ch-<版本>-source.tar.gz
SHA256SUMS.txt
```

不公开或单独上传 PKG，不上传 `BUILD-RESULT.json`。

### 失败语义

以下情况必须导致工作流失败：

- Tag 格式无效。
- 产品版本无法从 Tag 生成。
- 构建号无效。
- 目标架构不在产品配置中。
- Runner 架构与任务架构不一致。
- 驱动、原生工具或 PKG 出现错误架构。
- Mach-O 最低系统不是 macOS 14.0。
- 源码审计、HAL 合同或隔离安装事务测试失败。
- DMG 无法验证或缺少必需文件。
- Artifact 缺失、为空或散列不符。
- 任一架构失败。
- Tag 发布缺少 Developer ID 或公证凭据。
- 签名、公证、staple 或系统策略验证失败。
- 同名 Release 已存在。

失败时保留 Actions 日志和内部诊断文件，但不创建不完整的公开 Release。

### 权限与并发

- 手动工作流只需要读取仓库内容和上传 Artifact 的权限。
- Tag 工作流在构建阶段只需要读取权限，发布阶段使用 `contents: write`。
- 同一 Tag 的发布工作流启用并发保护，防止重复创建 Release。
- 使用 GitHub 官方 Actions，发布命令通过 `gh` 和 `GITHUB_TOKEN` 执行。

## Testing Decisions

测试重点是可观察的发布行为，不绑定内部实现细节。

### 配置与版本

- 严格合法的 Tag 能生成预期产品版本。
- 非法 Tag 全部被拒绝。
- 构建号来自运行编号并能进入 PKG、驱动和发布信息。
- 临时有效配置与源码归档中的配置一致。
- 双架构配置只接受 `arm64` 与 `x86_64`。

### 架构产物

- arm64 构建产物的所有 Mach-O 恰好包含 arm64。
- x86_64 构建产物的所有 Mach-O 恰好包含 x86_64。
- PKG 内驱动和事务工具架构与任务架构一致。
- DMG 内安装包、卸载工具和说明完整。
- 所有 Mach-O 的最低系统均为 macOS 14.0。
- 错误架构和错误最低版本会使测试失败。

### 打包与发布

- 缺失 PKG、DMG、源码归档或校验文件时失败。
- 修改任意公开资产后，总 `SHA256SUMS.txt` 校验失败。
- 单架构失败时不创建 Pre-release。
- 同名 Release 存在时拒绝覆盖。
- 公开资产集合严格为双架构 DMG、源码归档和校验文件。
- 手动入口始终不创建 Release。

### 原生测试

- 每个架构在对应原生 Runner 上执行驱动源码审计、补丁散列、HAL 合同签收和隔离安装事务测试。
- 测试继续验证安装、覆盖、失败回滚、卸载和结果协议。
- 不在 GitHub Runner 上实际安装 PKG 或加载系统音频驱动。

### 正式签名

- 凭据缺失时 Tag 工作流失败。
- 驱动、卸载工具和 DMG 的 Developer ID Application 签名有效。
- PKG 的 Developer ID Installer 签名有效。
- 公证提交成功，DMG 完成 stapling。
- 证书、私钥或 API Key 不出现在日志和源码归档中。

## Detailed Implementation Handoff

本节面向实际执行编码的模型。必须按本节执行，不得自行简化、合并或改变已确认的行为。若现有脚本接口与本节不一致，应先调整接口和调用方，再继续后续工作。

### 实施顺序

必须按以下顺序实施和验证，不能先编写发布工作流再补构建能力：

1. 扩展产品配置与版本注入能力。
2. 将驱动和原生工具构建改为显式架构参数。
3. 将 PKG、DMG、卸载工具和校验逻辑改为架构感知。
4. 增加双架构发布汇总能力。
5. 新增手动 Artifact 工作流。
6. 新增 Tag 认证发布工作流和签名占位阶段。
7. 更新单元测试、源码归档清单和验收文档。
8. 在本地完成 arm64 全链路验证。
9. 在 GitHub 手动运行一次，确认 arm64 与 x86_64 Artifact 均生成且不产生 Release。
10. 证书配置完成前不得推送发布 Tag 做正式验证。

### 文件级修改范围

必须检查和修改以下文件或新增对应职责的文件：

| 范围 | 必须完成的修改 |
| --- | --- |
| 产品配置 | 将架构列表改为同时包含 `arm64` 和 `x86_64`，保留当前版本与构建号作为本地和手动构建默认值 |
| 产品配置校验 | 只接受 `arm64`、`x86_64`，拒绝缺失、重复、未知或 universal 架构 |
| 驱动构建脚本 | 接受显式架构参数，生成该架构驱动、构建记录和产物散列 |
| 原生工具脚本 | 接受显式架构参数，输出到按架构隔离的目录 |
| PKG 构建脚本 | 接受显式架构和输出目录，只生成一个架构的 PKG、DMG 和校验文件 |
| 卸载工具渲染 | 复制对应架构的事务工具，并检查卸载 APP 中所有 Mach-O 的架构 |
| 驱动产物检查 | 从构建记录读取预期架构，不再固定 arm64 |
| PKG 内容检查 | 接受预期架构参数，检查驱动和事务工具的架构与 macOS 14.0 最低版本 |
| 发布内容检查 | 支持单架构内部 Artifact 和双架构公开 Release 两种资产集合 |
| 源码归档 | 包含新增版本脚本、发布汇总脚本、工作流文件及必要测试文件 |
| 打包说明 | 根据架构生成正确的平台说明，不再固定写 arm64 |
| 现有测试 | 更新 arm64 固定断言，增加 x86_64 和非法输入边界 |
| GitHub Actions | 新增手动 Artifact 入口、Tag 发布入口和共享架构构建工作流 |

### 版本注入接口

新增一个使用 Python 标准库实现的构建元数据脚本。建议接口：

```text
python3 scripts/prepare-build-metadata.py \
  --mode manual|tag \
  --tag vX.Y.Z \
  --build-number N \
  --config config/product.json \
  --output-json .build/build-metadata.json
```

行为要求：

1. `manual` 模式继续使用配置文件中的版本。
2. `tag` 模式要求提供 Tag，并删除前缀 `v` 后作为产品版本。
3. 两种模式都要求正整数构建号。
4. 两种模式都以原子方式更新传入的产品配置。
5. 输出 JSON 至少包含 `version`、`build_number`、`tag`、`source_sha`。
6. 如果存在 `GITHUB_OUTPUT`，将 `version`、`build_number`、`tag` 写入 Step Output。
7. 不允许直接修改调用者之外的配置路径。
8. 不允许在日志中输出 Secrets。
9. 脚本必须可在临时目录配合临时配置运行。

Tag 校验规则必须与以下正则完全一致：

```text
^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$
```

有效示例：

```text
v0.1.1
v1.0.0
```

无效示例：

```text
0.1.1
v01.0.0
v1.0
v1.0.0-beta.1
v1.0.0.1
```

不要通过字符串替换随意删除所有 `v` 字符，只允许去除开头唯一的 `v`。

### 架构参数接口

脚本必须使用显式参数，不得依赖隐含的 `uname -m` 决定安装包架构。

必须形成以下调用约定：

```text
bash scripts/build-driver.sh --arch arm64
bash scripts/build-driver.sh --arch x86_64

bash scripts/build-native-tools.sh --arch arm64
bash scripts/build-native-tools.sh --arch x86_64

bash scripts/build-packages.sh \
  --arch arm64 \
  --output /path/to/arm64-artifact

python3 scripts/check-driver-artifact.py BUNDLE arm64
python3 scripts/check-package.py PACKAGE.pkg x86_64
python3 scripts/check-uninstaller.py APP x86_64
```

通用要求：

- 未知架构立即返回非零状态。
- 不能接受空架构、`universal2`、`arm64e` 或逗号分隔架构列表。
- 每个架构使用独立工作目录，禁止共享 `.build/latest-*` 文件。
- 驱动构建记录必须写入实际 `architecture` 字段。
- 后续检查必须从构建记录或显式参数获得预期架构。
- `lipo -archs` 输出必须恰好等于一个预期架构。
- shell 脚本比较架构时先按空白分词，再判断元素数量和值，不能只做子串判断。

### 驱动构建细节

驱动构建必须继续以固定上游源码和现有补丁为输入。

修改要求：

1. 将 `ARCHS` 设置为传入架构。
2. 保持 `ONLY_ACTIVE_ARCH=NO`。
3. 保持 `MACOSX_DEPLOYMENT_TARGET=14.0`。
4. 保持 `CODE_SIGNING_ALLOWED=NO` 的 Xcode 构建方式，之后由脚本手动签名。
5. ad hoc 模式使用 `codesign --sign -`。
6. Developer ID 模式使用由环境传入的 Application 身份，并增加安全时间戳。
7. 构建图标辅助程序是 Runner 上执行的构建工具，应按 Runner 主机架构编译，不能继续固定编译 arm64。
8. 驱动本体必须按目标架构编译，不能使用 Runner 主机架构替代目标架构。
9. 构建结果文件名必须按架构区分，例如 `.build/latest-driver-arm64.json` 和 `.build/latest-driver-x86_64.json`。
10. 构建记录中的架构、版本、构建号、驱动散列和补丁散列必须来自同一次构建。
11. 不得修改驱动音频算法、采样率、缓冲或对象布局。

### 原生工具细节

必须构建以下对应架构的工具：

- `TapSayAudioTransaction`
- `TapSayAudioUninstaller`
- `TapSayAudioDiagnose`
- `TapSayAudioLoopback`

要求：

- 输出目录必须为 `.build/native/<arch>`。
- 最低编译目标必须是 `<arch>-apple-macosx14.0`。
- 每种二进制构建后使用 `lipo -archs` 校验。
- 使用 `vtool -show-build` 校验 macOS 14.0。
- 不允许在 x86_64 包中混入 arm64 二进制。
- 不允许为形成 universal binary 而同时编译两个架构。

### 卸载工具打包细节

打包函数必须显式接收架构，并完成以下动作：

1. 从 `.build/native/<arch>` 复制卸载工具和事务工具。
2. APP 中驱动、卸载工具、事务工具的架构必须一致。
3. 卸载 APP 的版本与产品配置一致。
4. 卸载 APP 的 Bundle ID 保持现有稳定标识。
5. ad hoc 模式使用临时签名。
6. Developer ID 模式使用 Application 证书和有效时间戳。
7. 签名后执行严格验证。
8. 检查脚本不得再固定检查 `TapSayAudioTransaction-arm64`。

### PKG 和 DMG 细节

每次单架构打包必须创建独立临时目录，并在所有检查成功后原子发布 DMG。PKG 在该临时目录中生成和校验，只作为 DMG 的内部安装载荷。

输出名称固定为：

```text
TapSayAudio-2ch-<版本>-<架构>.dmg
SHA256SUMS.txt
```

内部 Artifact 的 `SHA256SUMS.txt` 只列出该架构的 DMG。

PKG 要求：

- 使用空根载荷和脚本事务安装方式，保持当前安装架构不变。
- `pkgbuild --min-os-version` 必须来自产品配置的 `14.0`。
- 版本来自有效配置。
- 收据标识保持 `com.leafney.tapsay.audio.pkg`。
- PKG 内的驱动和事务工具必须匹配目标架构。
- Developer ID 模式必须使用 Developer ID Installer 证书重新签名 PKG。
- 签名后使用 `pkgutil --check-signature` 验证。
- PKG 不复制到单架构发布目录，也不进入 Actions Artifact 的顶层文件列表。

DMG 要求：

- 卷名包含目标架构。
- 包含 PKG、对应架构卸载 APP、中文说明、GPL 和第三方许可说明。
- 创建后使用 `hdiutil verify` 验证。
- 挂载后必须对内部 PKG 执行架构、载荷、事务脚本和签名状态检查。
- Developer ID 模式必须先签名 DMG，再公证和 staple。
- 不将 PKG 作为本地输出、Actions Artifact 或公开 Release 的独立资产。

### 中文打包说明

当前 DMG 说明固定写 Apple Silicon arm64，必须改为架构感知。

- arm64 说明明确适用于 Apple Silicon。
- x86_64 说明明确适用于 Intel Mac。
- 两种说明都注明 macOS 14 及以上。
- 不应把未认证测试说明永久写死在正式认证产物中。
- 可以传入构建模式，生成“未认证内部测试包”或“Developer ID 已签名并公证”说明。

### Artifact 汇总

新增发布汇总脚本，建议接口：

```text
python3 scripts/assemble-release.py \
  --arm64-dir DIR \
  --x86_64-dir DIR \
  --output DIR \
  --version VERSION \
  --minimum-macos 14.0
```

行为：

1. 从两个输入目录寻找架构对应的 DMG。
2. 验证两个目录中的版本和架构一致。
3. 分别执行 DMG 完整性检查，并通过挂载内容检查内部 PKG。
4. 验证输入目录提供的单架构校验文件。
5. 只复制两个 DMG 到公开输出目录。
6. 生成一份源码归档。
7. 生成一份只覆盖源码归档和两个 DMG 的 `SHA256SUMS.txt`。
8. 不得复制 PKG、构建记录或任何未列出的临时文件到公开输出。
9. 所有文件存在且非空后才原子发布输出目录。

### 工作流文件结构

必须新增三个工作流职责：

1. 手动 Artifact 入口。
2. Tag 认证发布入口。
3. 可被两者调用的单架构构建工作流。

推荐文件名：

```text
.github/workflows/build-artifacts.yml
.github/workflows/release.yml
.github/workflows/package-arch.yml
```

#### 手动 Artifact 入口

- 只使用 `workflow_dispatch`。
- 不响应普通 push、Pull Request、Tag 或定时任务。
- 读取当前产品配置版本。
- 构建号使用 `github.run_number`。
- 分别调用两次共享工作流：arm64 和 x86_64。
- 调用时签名模式固定为 `adhoc`。
- 不向共享工作流传入任何 Apple Secrets。
- 工作流中不得出现 `gh release create`、Release 上传或修改 Release 的步骤。
- 两个架构任务都成功时工作流成功；任一失败时工作流失败。

#### Tag 认证发布入口

- 只使用 Tag Push，目标是 `v*`；工作流第一步再用正则严格校验。
- 不响应 `workflow_dispatch`。
- 不检查 Tag 是否位于 `main` 历史。
- 从 Tag 生成版本，构建号使用 `github.run_number`。
- 分别调用两次共享工作流：arm64 和 x86_64。
- 调用时签名模式固定为 `developer-id`。
- 任一架构失败时，汇总和 Release 任务不得运行。
- 汇总任务下载两个架构 Artifact。
- 汇总任务再次校验版本、架构、签名和散列。
- 只有全部通过后创建 Pre-release。

#### 共享单架构工作流

- 只使用 `workflow_call`。
- 输入至少包含架构、Runner 标签、版本、构建号和签名模式。
- 在正确 Checkout SHA 上执行。
- 在临时配置中写入传入版本和构建号。
- 调用统一构包脚本。
- 在对应原生 Runner 上执行驱动、HAL、PKG 和隔离安装事务测试。
- 上传一个架构的 DMG 和 `SHA256SUMS.txt`。
- Artifact 名称包含版本、架构和运行编号。
- Artifact 保留期为 14 天。
- 签名模式为 `adhoc` 时不得访问开发者 Secrets。
- 签名模式为 `developer-id` 时，任一证书或公证密钥缺失都必须立即失败。

### GitHub Actions 环境

Runner 固定为：

```text
arm64  → macos-15
x86_64 → macos-15-intel
```

Action 权限：

- 手动工作流：`contents: read`。
- 共享构建工作流：`contents: read`。
- Tag 发布工作流：构建阶段只读，最终发布任务使用 `contents: write`。
- 使用 `GITHUB_TOKEN` 和 `gh` 创建 Pre-release。

Action 使用要求：

- Checkout、上传和下载 Artifact 使用 GitHub 官方 Action。
- 使用当前稳定的 v4 版本及其兼容更新版。
- 上传 Artifact 时设置 `if-no-files-found: error`。
- 下载 Artifact 时指定架构名称，避免两个架构覆盖。
- 同名 Tag 重复运行或 Release 已存在时必须失败，不覆盖现有 Release。

### Developer ID 签名阶段

签名阶段必须在单架构构建工作流内、上传 Artifact 前完成。

具体顺序：

1. 创建 Runner 临时 Keychain。
2. 导入两个 `.p12` 文件。
3. 验证 Application 与 Installer 身份均可读取。
4. 使用 Developer ID Application 签名驱动。
5. 构建 PKG。
6. 使用 Developer ID Installer 签名 PKG。
7. 构建包含已签名 PKG 和已签名卸载 APP 的 DMG。
8. 使用 Developer ID Application 签名 DMG。
9. 使用 Team API Key 调用 `notarytool`。
10. 等待公证成功。
11. 对 DMG 执行 `stapler staple`。
12. 执行 `stapler validate`。
13. 执行 `spctl --assess`。
14. 执行 `codesign --verify` 和 `pkgutil --check-signature`。
15. 清理临时 Keychain 和证书文件。

失败保护：

- 任一步骤失败立即退出。
- 禁止在签名失败后降级为 ad hoc。
- 禁止上传未认证 DMG 到 Tag 工作流的 Artifact。
- 禁止打印证书内容、私钥内容或 API Key 内容。
- 公证日志可以上传为内部故障诊断，但必须先确认其中不含秘密。

### 现有测试必须修改的位置

现有 release tools 测试中的固定 arm64 文件名、架构和发布资产集合必须更新。

至少增加以下测试：

1. `manual` 模式保留配置版本。
2. `tag` 模式正确从 Tag 生成版本。
3. 所有非法 Tag 均被拒绝。
4. 构建号进入有效配置和构建记录。
5. arm64 和 x86_64 分别生成正确文件名称。
6. 错误架构在驱动检查中失败。
7. 错误架构在 PKG 检查中失败。
8. 错误架构在卸载 APP 检查中失败。
9. 低于 macOS 14.0 的 Mach-O 被拒绝。
10. 单架构 Artifact 校验文件只包含 DMG。
11. 公开 Release 校验文件包含两个 DMG 与源码归档。
12. 缺失任一架构产物时不生成公开目录。
13. 错误散列阻止汇总发布。
14. 现有隔离安装事务测试能使用构建记录中的架构。
15. Tag 工作流在签名模式缺少 Secrets 时明确失败。

测试文件可以使用临时目录和现有 Python `unittest` 风格。不要启动真实音频服务，不要安装 PKG，不要修改 Runner 的系统音频设置。

### 源码归档细节

源码归档必须至少加入：

- 新增构建元数据脚本。
- 新增发布汇总脚本。
- 新增签名与公证脚本。
- 三个 GitHub Actions 工作流。
- 更新后的测试。
- 有效产品配置。
- 包含 Tag、源码 SHA、产品版本和构建号的构建来源文件。

源码归档不得包含：

- `.build/` 缓存。
- 证书或 Keychain。
- GitHub Secrets。
- 公证 API Key。
- PKG 或 DMG 二进制。
- 公开 Release 的临时目录。

### 验收步骤

#### 本地 arm64

依次执行并全部通过：

```text
python3 scripts/check-metadata.py
python3 Tests/ReleaseToolsTests.py
python3 Tests/DriverSourceTests.py
bash scripts/build-packages.sh \
  --arch arm64 \
  --output /private/tmp/tapsay-audio-arm64-test
```

检查：

- 只发布 arm64 DMG；PKG 仅存在于 DMG 内。
- `lipo -archs` 全部为 arm64。
- `vtool -show-build` 最低系统为 14.0。
- `hdiutil verify` 通过。
- `SHA256SUMS.txt` 校验通过。

#### GitHub 手动 Artifact

手动运行 `build-artifacts.yml` 后检查：

- arm64 与 x86_64 两个任务均成功。
- 两个 Artifact 都能下载。
- 每个 Artifact 只包含 DMG 和校验文件。
- DMG 内部的 PKG 内容、架构和签名检查通过。
- 两个架构的 Mach-O 没有混入。
- 所有产物最低系统为 macOS 14.0。
- GitHub Releases 没有任何新增内容。

#### GitHub Tag 发布

证书尚未配置时，不应实际推送发布 Tag。完成 Secrets 后再验证：

- 合法 Tag 生成对应版本。
- 两个架构均完成签名和公证。
- 任一架构失败时没有 Release。
- 成功时只创建一个 Pre-release。
- Release 恰好包含两个 DMG、源码归档和 `SHA256SUMS.txt`。
- Release 不包含独立 PKG 或 `BUILD-RESULT.json`。

### 明确禁止事项

执行模型不得：

- 使用单一 arm64 Runner 交叉生成 x86_64 包并跳过原生事务测试。
- 生成 universal2 产物代替双架构安装包。
- 让手动工作流创建 GitHub Release。
- 让 Tag 工作流生成 ad hoc 签名的公开包。
- 从 Secrets 是否完整推断工作流触发方式。
- 将证书或私钥写入仓库。
- 删除现有驱动源码审计或 HAL 合同检查。
- 删除 GPL 源码归档。
- 在公开 Release 上传 PKG 或 `BUILD-RESULT.json`。
- 实际安装 PKG 到 GitHub Runner 的系统 HAL。
- 修改 TapSay 主程序仓库。
- 修改音频算法、设备身份、默认 48 kHz 或采样率表。

## Out of Scope

- 本阶段不生成正式认证安装包。
- 本阶段不配置 Apple 证书、App Store Connect API Key 或公证账户。
- 不实现自动修改 Git Tag 或自动提交产品版本。
- 不限制 Tag 来源分支。
- 不在 GitHub Runner 上执行真实音频录音、遥控器连接或第三方输入法验收。
- 不在本地输出目录、Actions Artifact 或公开 Release 中发布独立 PKG。
- 不生成 GitHub Stable Release；Tag 发布统一为 Pre-release。
- 不处理 Windows 或其他非 macOS 平台。

## Further Notes

- 当前仓库没有既有 Actions 工作流，需要新增入口和共享构建逻辑。
- 当前构包链中的 arm64 硬编码不仅存在于产品配置，还存在于驱动、原生工具、PKG 校验、卸载工具和发布检查中。
- x86_64 必须使用原生 Intel Runner 完成测试，避免依赖 Rosetta。
- 正式证书接入时再详细确认证书导出、Team API Key、GitHub Environment 和 Secrets 的具体操作。
- 只有 PRD 获得用户批准后，才修改工作流、构建脚本、测试和文档。
