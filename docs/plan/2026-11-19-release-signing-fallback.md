Related discussion: [docs/discuss/2026-11-19-release-signing-fallback.md](../discuss/2026-11-19-release-signing-fallback.md)

# Tag 发布签名自动切换规划

## 问题与目标

目前 Tag 发布固定要求全部苹果签名和公证凭据，缺少凭据时无法发布。需要支持未认证版本，并在凭据补齐后自动切换到认证版本，无需再次修改流程。

## 发布规则

1. 严格格式 `vX.Y.Z` Tag 触发发布，继续创建 GitHub Pre-release。
2. 在构建前统一判断现有 8 项 Apple Secrets：全部为空选择 `adhoc`；全部非空选择 `developer-id`；其他情况报错终止。空白值按未填写处理；日志不得输出凭据。
3. 两个架构使用同一次判断得到的模式。已选择认证模式后，凭据无效、签名或公证失败均终止发布，不降级。
4. 未认证公开 DMG 使用 `TapSayAudio-2ch-<版本>-<架构>-Unverified.dmg`；认证 DMG 保持现有名称。源码归档名称不变；汇总校验文件使用实际资产名。
5. Release 说明明确标注认证状态；未认证版本说明可能遇到 macOS 安全提示。名称中的标识不代表系统认证。
6. 手动工作流固定使用 `adhoc`，只生成 Actions Artifact，不创建 Release，也不依赖 Apple Secrets。保留现有手动产物命名，避免扩大变更范围。
7. 保留第三方分发审查、严格版本、版本一致性、双架构成功和禁止覆盖同名 Release 的要求。补齐凭据后使用新版本 Tag 发布认证包。

## 实施顺序

1. 调整 Tag 工作流：在准备阶段判断凭据完整性，输出非敏感签名模式，传给两个架构和发布阶段。
2. 调整发布汇总及资产校验：按模式验证两个架构内容；未认证模式仍验证架构、内容、资产集合及散列；认证模式额外保留签名、公证票据和系统策略检查。公开文件重命名后重新生成校验文件。
3. 调整 Release 发布说明，使状态与实际验证模式一致；任何验证失败均不创建 Release。
4. 更新签名 Secrets 指南和发布说明，解释两种模式、部分配置失败及新 Tag 规则。
5. 增补有意义的边界测试，覆盖 Secrets 全空、部分填写、全部填写，双架构模式一致、文件名及校验文件、认证失败不降级和发布前失败处理。复用现有发布工具测试，避免测试实现细节。
6. 运行相关发布工具测试、配置及工作流检查；条件允许时验证手动构建。实际 Tag 发布需要真实 GitHub 环境；认证端到端验证还需要有效苹果凭据，不能以模拟结果声称通过。

## 验收条件

- 无 Secrets 时 Tag 生成双架构 `Unverified` DMG、源码归档及正确的 `SHA256SUMS.txt`，并创建标明状态的 Pre-release。
- 部分 Secrets 或认证流程失败时不创建 Release；全部凭据有效时只发布通过完整认证验证、名称不带 `Unverified` 的 DMG。
- 手动运行只生成未认证 Actions Artifact，不读取认证凭据、不创建 Release。
- 任一架构失败、资产不一致、分发审查未通过或同名 Release 已存在时均不发布。
- 不修改既有 Release；认证版本使用新 Tag。

## 范围外

- 配置或获取苹果凭据、绕过 macOS 安全机制、自动完成第三方许可审查。
- 将手动构建发布到 Release，或覆盖现有 Release。

## 实施约束

本文件获用户明确批准后才开始代码修改。实施按任务进行，每次主要文件修改后等待用户确认；若需变更本规划，先更新并取得用户批准。

## 给编码人员的详细实现说明

### 现状和不可忽略的依赖

- `.github/workflows/release.yml` 的两个架构目前都硬编码 `developer-id`，汇总阶段固定传 `--formal`。
- `.github/workflows/package-arch.yml` 已支持 `adhoc` 和 `developer-id`；手动工作流已固定使用 `adhoc`。不要为手动工作流增加 Secrets 判断。
- 单架构构建目前输出不带 `Unverified` 的 DMG 和对应校验文件。保持这些内部产物名称不变；只在汇总为公开资产时给未认证 DMG 改名。
- `scripts/check-dmg.py` 严格检查 DMG 文件名，且 DMG 内 PKG 名称不带 `Unverified`。必须明确支持公开的未认证 DMG 文件名，同时保持内部 PKG 和卷内内容名称不变；不能通过去掉文件名验证来解决。
- `scripts/assemble-release.py`、`scripts/release_checks.py` 和 `scripts/publish-github-release.py` 都硬编码公开资产名；三处必须一起调整。
- `scripts/prepare-build-metadata.py` 的 Tag 模式和 `assemble-release.py` 的正式审查均检查上游分发状态。未认证发布也必须保留该检查，不能简单去掉 `--formal` 后忽略它。

### 任务一：确定唯一签名模式

在 Tag 工作流 `prepare` 任务中读取以下 8 项 Secret，按 `value.strip()` 是否为空统计，不打印任何值，也不要把值写入输出、Artifact 或命令参数：

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

- 0 项非空：输出 `signing_mode=adhoc`。
- 8 项非空：输出 `signing_mode=developer-id`。只用去空白后的结果判断完整性；实际凭据不做改写。
- 1 至 7 项非空：返回非零并说明需要全部配置或全部留空；不要输出值。
- 将模式作为 `prepare` 的 job output，分别传给两个可复用架构任务、汇总脚本和发布脚本。不要让各架构独立推断模式。
- 保留共享工作流中认证模式下现有的凭据检查、导入、清理与认证逻辑。Secrets 完整不代表有效，后续错误必须直接失败。

### 任务二：区分签名验证和公开发布检查

- 为汇总及公开资产审计显式传递 `adhoc` 或 `developer-id`，拒绝未知值。不要通过文件名猜测模式。
- 汇总先以现有内部文件名、对应单架构校验文件和明确的签名模式调用 `check-dmg.py` 检查两个输入。确保两个输入都通过才组装公开目录。
- 复制到暂存目录时，`adhoc` 的两个 DMG 才追加 `-Unverified`；`developer-id` 原名不变。复制后生成源码归档和新的 `SHA256SUMS.txt`，校验内容指向实际公开文件名。
- 对公开 DMG 的检查应允许明确指定的 `-Unverified` 外部名称，但卷内 PKG 仍使用原始名称。只在 `adhoc` 公开资产检查上下文允许这个后缀；认证模式不允许后缀。
- 两种模式均检查资产集合、非空、散列、架构、内容、源码归档和第三方分发状态。认证模式继续执行严格的签名、`stapler validate` 和 `spctl` 检查。未认证模式不能假称通过公证检查，也不能把“尚未公证”误判为阻止未认证发布的错误。
- 保留现有独立 `check-release-readiness.py --formal` 的严格认证语义；如需扩展接口，兼容现有调用，不要让无参数的本地检查意外变成公开发布许可。
- 保留暂存、验证后原子替换输出目录的机制。验证失败时不发布、不损坏之前有效输出。

### 任务三：发布和说明

- `publish-github-release.py` 根据显式传入的模式计算预期资产名。先验证本地资产集合，再检查同名 Release；保持草稿上传、远端资产核对、发布为 Pre-release 和失败清理机制。
- 在保留自动生成的发行说明的同时，添加与模式一致的简短说明：`adhoc` 明确未进行苹果开发者签名及公证，macOS 可能阻止打开；`developer-id` 标明已完成签名及公证验证。只有前述验证通过后才能使用认证说明。
- 不向 Release 上传单独 PKG 或内部构建元数据；资产仍为两个 DMG、一个源码归档和一个校验文件。
- 更新 `.github/workflows/SIGNING-SECRETS.md` 及相关发布文档中“缺少任意一项直接失败”和“只有认证版本可发布”等过时描述，同时说明部分填写会失败。

### 任务四：检查与交付

- 在 `Tests/ReleaseToolsTests.py` 更新原先断言两个硬编码 `developer-id` 的测试，并覆盖三类凭据组合；测试只使用虚构值。
- 覆盖两种公开资产名称和校验文件、内部和公开 DMG 文件名规则、错误模式和错误资产、架构失败、分发审查未通过、认证验证失败及禁止覆盖已存在 Release。检查失败时不得调用创建 Release 的操作。
- 保留并运行 `python3 Tests/ReleaseToolsTests.py`，以及项目已有的相关检查；运行 `git diff --check`。报告实际运行结果和未能执行的真实 macOS / GitHub / Apple 认证验证。
- 每完成一个主要文件修改后按本文件的实施约束停下，等待用户确认，再继续下一文件。不要自行推送 Tag 或创建真实 Release。
