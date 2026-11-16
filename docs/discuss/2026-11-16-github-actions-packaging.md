# GitHub Actions 双架构构包讨论

日期：2026-11-16

## 原始请求

为当前 TapSay Audio 项目实现 GitHub Actions 自动编译和打包流程，生成 macOS 安装包：

- 支持 arm64 和 x86_64。
- 支持 macOS 14 及以上。
- 第一阶段只生成未使用 Apple Developer ID 认证的安装包。
- 后续补充官方证书和公证材料后，能够完成签名与公证。
- 先确认实现方案，不立即修改代码。

## 现状核对

- 当前仓库没有 GitHub Actions 工作流。
- 产品配置、驱动构建、原生工具、PKG、DMG 和发布检查均硬编码为 arm64。
- 当前配置文件同时保存产品版本和构建号。
- 当前安装包采用临时 ad hoc 签名。
- 当前测试包含驱动源码审计、HAL 合同检查、PKG 内容检查和隔离安装事务测试。
- 当前公开 README 已描述 arm64 和 x86_64 安装包。

## 问答记录

### 1. 触发方式和发布位置

**问：** 是否接受手动运行只生成 Actions Artifacts，推送 `vX.Y.Z` Tag 时创建 GitHub Pre-release？

**答：** 确认。

### 2. Actions Artifact 的用途和测试方式

**问：** Actions Artifact 是什么，内部测试如何操作？

**答：** Artifact 是某次工作流运行生成的临时文件，位于 Actions 运行页面，需要登录并具有仓库读取权限。下载后为 ZIP，可解压到对应架构的 Mac 上执行散列校验、安装、设备枚举、小声点配合、语音输入和卸载测试。它不会出现在 GitHub Releases。

**问：** 是否接受分别生成 `TapSayAudio-arm64` 和 `TapSayAudio-x86_64` Artifact，每个包含对应架构的 DMG、PKG 和 `SHA256SUMS.txt`？

**答：** 确认。

### 3. 版本号来源

**问：** 是否接受配置文件作为唯一版本来源，并在 Tag 与配置版本不一致时失败？

**补充问：** 是否每次推送 Tag 都需要先手动修改产品版本？

**最终答：** 不手动修改。Tag 推送时从 `vX.Y.Z` 自动得到产品版本，并在 Runner 临时工作区写入构建配置。源码归档需要记录实际构建使用的配置、Tag 和源码提交。

### 4. 构建号

**问：** 是否希望构建号自动生成？

**答：** 确认。Tag 和手动构建均使用 `github.run_number` 作为构建号。

### 5. 双架构构建 Runner

**问：** 是否使用两个原生 Runner 分别构建和测试对应架构？

**答：** 确认。arm64 使用 `macos-15`，x86_64 使用 `macos-15-intel`。

### 6. 公开 Release 的资产范围

**初步方案：** 同时上传双架构 DMG、PKG、源码归档、总校验文件及 `BUILD-RESULT.json`。

**问：** DMG 和 PKG 是否有必要同时公开？

**结论：** 公开 Release 只提供双架构 DMG、源码归档和 `SHA256SUMS.txt`。DMG 内部已经包含 PKG、卸载工具、说明和许可。内部 Actions Artifact 仍保留 DMG、PKG 和校验文件。

**补充：** 用户进一步确认公开 Release 不提供 `BUILD-RESULT.json`。

### 7. Tag 来源限制

**问：** 是否只允许 `main` 分支历史提交上的 Tag 创建 Release？

**答：** 暂不添加该限制。

### 8. 后续证书材料和签名方式

**问：** 取得 Apple Developer ID 后需要提供什么，如何尽量简化？

**答：** 需要 Developer ID Application、Developer ID Installer、Team ID、App Store Connect Team API Key、Key ID 和 Issuer ID。材料统一放入 GitHub Actions Secrets，不进入仓库或聊天。配置完成后仍只需推送 Tag。

**问：** 是否接受手动构建保持未认证，Tag 发布必须完成 Developer ID 签名、公证和 stapling，缺少凭据时直接失败？

**答：** 确认。具体证书配置留待正式接入时再讨论。

### 9. 手动构建与 Tag 发布的职责边界

**问题：** 使用证书字段是否完整来区分手动构建和 Tag 发布会造成职责混乱。

**最终结论：** 不再用证书字段判断发布路径。触发方式只决定产物位置：

- 手动运行只生成 Actions Artifacts，不创建 Release。
- Tag 推送只创建认证 Pre-release，缺少签名凭据直接失败。

手动构建固定使用 ad hoc 签名；Tag 发布固定要求 Developer ID 签名和公证。

### 10. 模块与测试范围

**问：** 是否接受架构感知构建、架构感知打包校验、工作流编排、认证扩展点四个模块，并测试错误架构、最低系统、缺失产物、错误散列、单架构失败和隔离安装事务？

**答：** 确认。

### 11. 实施交接详细程度

**补充：** PRD 将交给编码能力较弱的模型实施，需要补充文件级修改范围、脚本接口、命令顺序、工作流职责、失败语义和逐步验收标准，避免执行模型自行猜测。

**结论：** 在 PRD 中增加独立的详细实施交接章节。章节中的明确约束优先于执行模型的自行推断。

## 最终共识

1. 手动工作流通过 `workflow_dispatch` 触发，只生成内部 Artifacts。
2. arm64 和 x86_64 分别在原生 macOS Runner 上构建和验证。
3. 所有架构的最低部署目标为 macOS 14.0。
4. 手动 Artifact 包含对应架构的 DMG、PKG 和 `SHA256SUMS.txt`。
5. Tag 必须使用 `vX.Y.Z` 格式，产品版本从 Tag 自动获取。
6. 构建号自动使用 GitHub Actions 运行编号。
7. Tag 构建成功后创建 GitHub Pre-release。
8. 公开 Release 只包含双架构 DMG、源码归档和总校验文件。
9. 不限制 Tag 是否位于 `main` 历史。
10. 当前阶段使用 ad hoc 签名，不配置或引用开发者证书。
11. 后续配置证书后，Tag 发布必须完成 Developer ID 签名、公证和 stapling。
12. 手动工作流和 Tag 工作流共用底层构建与校验逻辑，但使用不同入口。
13. 不在 GitHub Runner 上实际安装并加载系统音频驱动；继续使用隔离安装事务测试。
14. PRD 必须包含面向实施模型的详细文件级和接口级交接说明。

## 相关文档

- PRD：`docs/plan/2026-11-16-github-actions-packaging.md`
