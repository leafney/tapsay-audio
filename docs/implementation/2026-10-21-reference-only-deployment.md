# 原样参考版本：构建与真机部署

依据：`docs/plan/2026-10-21-reference-driver-cleanup.md` 第 15 节，用户要求先完整复现、部署，再优化。本记录取代之前将属性修复或工具重写作为本轮前置条件的执行顺序。分支 `feat/61021`。

## 本轮交付边界

固定无线麦 `c9fabd1ef53e1a311dab4518a70693494631368b`、BlackHole `e2b22aaaba4e507a097131704bf96dabc004d9cf` 和无线麦 USB 补丁。TapSay 只改变独立名称、UID/Bundle/工厂、版本、制造商及品牌图标。之前三项属性修复已从身份补丁撤出，第四项候选未进入构建。保留参考属性语义、对象布局、双声道 Float32、完整 13 项率表、初始 48 kHz、缓冲、时钟及 IO。

构建使用仓库内固定原始源码，`SOURCE-SHA256.json` 锁定所有原始文件与补丁字节。`check-reference-source.py` 对 C 中明确允许的身份差异归一化后逐字节比较，输出 `algorithm_changes=0`。其他行任何变化都会失败。上游版权、GPL 与来源原样保留，内部上游静态函数名保留用于来源对照。

构包读取本次构建的独立结果文件并检查驱动 SHA-256，停止按随机目录名选择旧产物。源码归档无 Mach-O、本地缓存和旧 Driver 目录，可离线构建；不再夹带整套旧实施日志。现有独立安装/卸载入口先用于本轮，重构和旧文件清理后置。

## 已运行验证

| 项目 | 结果 |
| --- | --- |
| arm64 Release 驱动构建 | 通过；macOS 14 起，ad hoc 签名验证通过 |
| 参考源 C 身份归一化比较 | 通过，算法差异 0 |
| 13 项有序率表、输入/输出双声道 Float32、初始 48000 Hz | 隔离直接回调通过 |
| 新包内驱动与本次构建结果 SHA-256 | 相同 |
| 安装/卸载事务隔离验证 | 通过，含覆盖、失败恢复、历史材料保护和结果协议 |
| PKG 内容与原生工具架构检查 | 通过，仅 arm64 |
| DMG 创建与校验 | 通过 |
| 对应源码归档 | 57 项源码/必要材料；无本地 Mach-O、旧 Driver 或 profile 目录 |

本轮参考 C SHA-256：`8837db089b7a14ce7c240621e770fd9b54413140e7d6d1633a6aa27a4d53a28e`。驱动可执行文件 SHA-256：`b2bc6d1c074393051b1083ff2398b255cd7289f76bdf4ebee95b3739f762b1a6`。完整构建/包路径及散列记录在本地 `dist/BUILD-RESULT.json`、`dist/SHA256SUMS.txt`；最终安装以实际包读回为准。

## 真机部署状态

部署前只读检查：MiRemoteV 与旧 TapSay 实际名义率均为 48000 Hz，主设备输入输出各一个流。MiRemoteV 二进制 SHA-256 `f3c5f12368af4e80d534c40b6154f94ec09218fc4ba09afbd398103093d32be9`；旧 TapSay 为 `fc4e0d9966c960685de77863708d59fe4f06de02af77f208c36aa1b0b6e4bddd`。

用户最终选择手动安装，自动安装请求已中止，未取得安装成功结果。后续由用户双击 `dist/TapSayAudio-2ch-0.1.0.pkg` 覆盖安装，再记录落地驱动散列、CoreAudio 实际名义率和输入输出流格式，执行 48 kHz 合成 PCM 环回。安装和真实音频测试均仍待执行。证据目录 `.build/experiments/evidence/2026-10-21-reference-only-deploy/`。

## 最终手动安装资产

从提交 `f9f962b0e0bb55b89181960f7944d68ab18eeaf6` 的干净工作树重建，源码归档内保存对应提交及 `working_tree=clean`。最终驱动可执行文件 SHA-256 为 `df3926398fce9633c21c1a202e79272f514a8076bae84b19c31d8f06452e1633`，包内与本次构建结果一致。此值取代前述首次开发构建的二进制散列作为本次安装核对依据。

| 交付文件 | SHA-256 |
| --- | --- |
| `dist/TapSayAudio-2ch-0.1.0.pkg` | `a7af9818862a9d93b6c3f3a47dc7aa7df77468429af5ff5df9f2e5c8b80561b3` |
| `dist/TapSayAudio-2ch-0.1.0-arm64.dmg` | `628e56b76852ae59ecf311d77b23e9c94dc34cae9c908245930f2a67964d9e67` |
| `dist/TapSayAudio-2ch-0.1.0-source.tar.gz` | `3e2c9b044f929b0b62321ea37dbc2efc5be210278abb38e482625c896a700a20` |

交付前再次执行 PKG 内容检查及三个文件的 SHA-256 校验，全部通过。DMG 包含安装 PKG、独立卸载入口与中文说明。支持 Apple Silicon arm64/macOS 14 起，初始 48 kHz；当前为本地未签名、未公证测试包。

真实遥控器切回、长按/释放、第三方文字上屏和长时矩阵仍需实测；自动合成环回不能替代。正式签名、公证、公开下载地址仍未提供，当前产物是本地部署验证包。
