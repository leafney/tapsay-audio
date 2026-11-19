Related discussion: [docs/discuss/2026-11-19-intel-macos-support.md](../discuss/2026-11-19-intel-macos-support.md)

# Intel 版支持 macOS 13 的实施规划

## 目标

Intel `x86_64` 安装包最低支持 macOS 13.0；Apple Silicon `arm64` 保持 macOS 14.0。先由现有 GitHub Actions 手动工作流生成 Intel 测试包，用户下载后再在 macOS 13 Intel 真机上验证。

## 实施要求

1. 建立按目标架构确定最低系统版本的统一规则：`x86_64` 为 `13.0`，`arm64` 为 `14.0`。拒绝未知架构；避免不同脚本各自维护不一致的值。
2. 调整驱动和原生工具的编译目标及 Mach-O 检查；构建主机使用的工具按主机实际环境处理，不能把目标架构与主机架构混淆。
3. 调整安装包的最低系统要求、卸载程序的系统要求、安装事务运行时判断、生成的元数据与检查脚本。Intel 包必须实际允许 macOS 13；Apple Silicon 包维持 14。检查 API 可用性及相关条件分支。
4. 调整双架构发布汇总、内容审计和构建工作流中的最低版本参数，分别校验各架构，不再假设共用一个最低版本。保留签名、公证、文件完整性及第三方分发审查等现有要求。
5. 更新安装包说明、仓库说明和相关文档，分别写明两个架构的最低系统版本；在 Intel macOS 13 真机验证前明确标记兼容性待验证。
6. 手动 `Build Internal Artifacts` 工作流继续使用 GitHub Actions 的 Intel runner 构建 Intel 包，并上传未认证的 Actions Artifact；不要将当前本机交叉构建作为交付方式。手动构建不创建 Release。

## 验证与交付顺序

1. 完成实现后运行适用的自动测试、打包内容检查和工作流检查。检查应覆盖两个架构的最低版本映射、错误架构和系统版本边界。
2. 通过现有 GitHub Actions 手动工作流构建调试产物，确认 Intel Artifact 含 DMG 与校验文件，并向用户提供运行记录及下载入口。打包不以 macOS 13 真机测试通过为前置条件。
3. 用户下载 Intel 安装包，在 macOS 13 真机检查安装、设备识别、录音和卸载；记录系统版本、机型和结果。构建成功不能替代这些测试。
4. 如 GitHub 访问、工作流触发或产物下载不可用，报告具体阻碍和已完成的验证，不声称已生成可下载产物。

## 范围外与约束

- 不降低 Apple Silicon 的最低系统版本，不擅自推送发布 Tag 或创建 Release。
- 此规划须经用户明确批准后才开始代码修改。实施时遵循本次适用的用户指令；规划需要变更时，先更新并取得批准。

## 给编码人员的详细说明

### 一、先理解现有流程

- `config/product.json` 目前使用单个 `product.minimum_macos` 值 `14.0`；`scripts/product.py` 的 `load_product()` 对此做硬编码校验。
- `.github/workflows/build-artifacts.yml` 手动触发双架构任务；`package-arch.yml` 要求 runner 的 `uname -m` 与目标架构一致。Intel 任务使用 `macos-15-intel`；runner 系统版本是构建环境，与产物的最低支持版本是两回事。
- 每个架构任务运行 `scripts/build-packages.py`，调用驱动和原生工具构建脚本，生成 DMG 和 `SHA256SUMS.txt`，上传 Actions Artifact。该工作流使用 ad hoc 签名，不创建 GitHub Release。
- `release.yml` 的公开发布流程也使用同一组脚本，但汇总阶段硬编码 `--minimum-macos 14.0`。修改不能只修手动构建而破坏 Tag 发布。

### 二、配置与版本规则

1. 将产品配置改成可明确表达 `arm64: 14.0`、`x86_64: 13.0` 的映射，例如 `product.minimum_macos_by_architecture`。在 `scripts/product.py` 提供一个接收配置和架构、返回最低版本的函数，集中校验键和值；未知架构、缺失值或不符合合同的值必须报错，不能回退到 14 或 13。
2. 在仓库中搜索所有 `minimum_macos`、`14.0` 和 `macOS 14` 的实际消费者，逐一判断是目标架构、构建主机还是历史记录。所有实际参与构建、打包、运行时和验证的目标版本，都应使用同一映射。保留历史讨论和历史实施记录，不改写既有事实。
3. `prepare-build-metadata.py` 应继续只更新版本和构建号，保留完整架构映射。包内产品配置、卸载工具资源配置与有效构建配置应一致；不要为了单架构把共享配置改成缺少另一架构的结构。
4. `Uninstaller.app/Contents/Info.plist` 是生成模板；最终产物的 `LSMinimumSystemVersion` 必须由 `render_uninstaller()` 按目标架构覆盖，而不是仅修改模板。

### 三、构建与运行时

1. `scripts/build-driver.sh`：按 `--arch` 获取目标最低版本，传给 `MACOSX_DEPLOYMENT_TARGET`，更新驱动 `vtool` 检查和结果元数据。驱动的 `x86_64` 必须标记 `minos 13.0`，`arm64` 必须标记 `minos 14.0`。
2. `scripts/build-native-tools.sh`：四个 Swift 原生工具的 `-target` 和 `vtool` 检查使用目标架构对应版本。`scripts/build-packages.py` 内 PKG 的 `--min-os-version`、产物元数据和其他用于目标架构的编译参数使用相同值。
3. `Tools/BuildIcon.swift` 的构建和运行涉及构建主机：区分需要在 runner 运行的工具与需要交付的目标二进制。保留当前 Actions 的原生架构 runner 约束，不依赖本机跨架构执行来验证。
4. `Tools/Transaction/main.swift` 当前直接检查系统主版本 `>= 14`。改为根据明确识别的实际架构使用对应门槛；Intel 的 12 拒绝、13 及以上通过；Apple Silicon 的 13 拒绝、14 及以上通过。未知架构要拒绝，不得默认为 Intel。保留已有管理员权限及驱动架构检查，不能为测试绕开生产安全检查。
5. 编译时检查所用 Swift、系统 API 和依赖对 macOS 13 的可用性；不兼容的 API 需适配或使用系统版本判断。不能仅修改部署目标后无视编译器或链接器错误。

### 四、安装包、内容和发布检查

- `scripts/check-driver-artifact.py`、`scripts/check-package.py`、`scripts/check-uninstaller.py` 按被检查产物的目标架构读取预期版本，检查驱动及事务工具 Mach-O、PKG `minimumSystemVersion`、卸载工具 plist 和二进制。不得把版本断言删除，也不得只检查字符串存在而不区分架构。
- `packaging/dmg/README.txt` 使用最低版本占位符；`scripts/build-packages.py` 渲染为对应架构的版本；`scripts/check-dmg.py` 检查占位符已替换且文本与目标架构一致。Intel 的 macOS 13 兼容性在真机验证前标记为待验证。
- `scripts/assemble-release.py` 和 `scripts/release_checks.py` 对两个输入按架构分别验证最低版本。调整 `.github/workflows/release.yml` 中的单一 `--minimum-macos 14.0` 接口及调用；检查全部调用方，不能使 Tag 发布因参数不兼容而失败。
- 保留 `Unverified` 文件名、认证模式及公开发布检查逻辑。macOS 13 兼容性待验证与苹果签名、公证状态是两回事；不要混淆两个状态。
- `scripts/check-release-readiness.py`、`README.md` 等当前说明须按架构列出版本；涉及源码归档的文件清单、配置校验和测试夹具也要同步更新。

### 五、测试场景

优先扩展现有 `Tests/ReleaseToolsTests.py` 和原生事务测试，测试对外行为而不是简单检查源码文本：

1. 产品配置返回 `arm64 → 14.0`、`x86_64 → 13.0`；未知架构、缺项和错误映射被拒绝。
2. 安装事务的版本边界：Intel 12 拒绝、13 接受；Apple Silicon 13 拒绝、14 接受。测试须明确模拟架构及系统版本，不依赖执行测试的机器恰好是什么系统。
3. 两种架构生成的 PKG 最低版本、驱动与事务工具 `minos`、卸载 App 的 plist 和工具 `minos` 均正确；交叉错配必须失败。
4. 两架构说明分别显示正确系统要求；Intel macOS 13 的真机状态明确为待验证。
5. 原有 Tag 发布中认证和未认证模式、双架构汇总、签名和公证检查继续通过。手动构建仍只生成 Artifact。
6. 运行 `python3 Tests/ReleaseToolsTests.py`、项目已有的原生事务测试及相关构建检查，运行 `git diff --check`。报告真实结果，不能将模拟测试写成真机测试。

### 六、GitHub Actions 交付步骤

1. 确保修改提交已推送到用户指定、可供手动工作流选择的分支，再触发 `Build Internal Artifacts`；不得擅自推送 Tag 或创建 Release。若仓库、分支或访问权限不明确，先确认或报告阻碍。
2. 等待工作流实际结束，查看 Intel 任务结果和日志。成功后提供该次 Actions 运行链接、Intel Artifact 名称和下载方式；Artifact 目前保留 14 天。
3. 用户解压 Artifact、核对 `SHA256SUMS.txt`，在 Intel macOS 13 真机执行安装、设备枚举、实际录音和卸载。若受未认证限制，应如实说明包的 ad hoc 签名状态。
4. 若 Intel runner 不可用、Actions 没有访问权限、构建失败或无法触发，说明具体失败及可继续的操作；不得凭本地编译或模拟测试声称远端 Artifact 已生成。
