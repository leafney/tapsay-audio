# TapSay Audio

TapSay 的独立虚拟声卡项目，设备显示名称为 `TapSay Audio 2ch`。

需求已整理并获批，当前按阶段实现，详见 [PRD](docs/plan/2026-10-18-audio-driver-distribution.md)。
完整交接和问答见 [讨论记录](docs/discuss/2026-10-18-audio-driver-distribution.md)。当前尚无可下载的安装包。

## 项目命名

| 项目 | 名称或文案 |
| --- | --- |
| 项目名称 | `TapSay Audio` |
| GitHub 仓库 | `tapsay-audio` |
| 系统设备名称 | `TapSay Audio 2ch` |
| PKG 文件名示例 | `TapSayAudio-2ch-0.1.0.pkg` |
| 引导页中文说明 | 安装 TapSay 配套虚拟声卡 |

## 首版支持范围

驱动、分架构 PKG/DMG 和源码归档已可构建；正式发行仍受签名、公证和各架构真机验收约束。
用户理解支持范围时，以本节及发布说明为准：

| 项目 | 首版范围 |
| --- | --- |
| 系统 | macOS 14 及以上；当前在 macOS 14.1.2 Apple Silicon 验证设备属性与合成 PCM 环回 |
| 处理器 | Intel（x86_64）、Apple Silicon（arm64），分别提供独立安装包 |
| 设备显示名称 | `TapSay Audio 2ch` |
| 声道数 | 固定双声道 |
| 采样率 | 16、44.1、48 kHz |
| 默认采样率 | 16 kHz |
| 声道格式 | 双声道、32-bit Float PCM |
| 传输类型 | CoreAudio 上报 USB，仅用于应用兼容，不需要 USB 硬件 |
| 分发文件 | 每个架构独立 DMG，内含同名 PKG、卸载 APP 和中文说明 |

首版范围不包含 96 kHz 或更高采样率。

首次安装后的声卡默认采样率设为 16 kHz，与 TapSay 当前音频来源一致。
44.1、48 kHz 作为对接其他常用软件的兼容格式保留；默认值不代表运行期间设备采样率不会变化。
具体软件兼容性以发布时列出的实测软件、版本和结果为准，不保证仅凭采样率匹配即可兼容所有软件。

已有社区报告指出，部分版本豆包输入法会隐藏特定类型的虚拟设备。当前驱动已按已批准 PRD
将 CoreAudio transport type 上报为 USB，已核实本机实际属性；应用兼容仍需实测。
本项目实际仍是软件虚拟声卡，无需额外 USB 硬件。
验收不仅检查系统能否发现设备，也检查目标软件中能否选用并实际收到声音。

TapSay 主程序当前产生的是 16 kHz 单声道浮点音频，这与虚拟声卡支持的双声道、
多采样率能力不同。目标是用户选择声卡后即可使用，无需手动调整采样率。
主程序现有直连输出图已在本机默认 16 kHz 下完成生产代码合成音实测，左右声道均正常接收。
主程序在 44.1/48 kHz 设备格式下的转换、真实遥控器及第三方软件接收效果仍需验证；
仅看到设备名称或成功启动音频引擎不算完整验收。

## 参考配置实验

`reference-48k` 和 `reference-16k` 是无线麦驱动配置对照实验，不属于正式发行配置。
两者使用完整上游采样率列表和隐藏第二设备；TapSay 的正式身份保持独立。
16 kHz profile 仅将驱动初始采样率从 48 kHz 改为 16 kHz。

```sh
bash scripts/run-driver-contract-tests.sh reference-48k
bash scripts/build-driver.sh reference-48k
bash scripts/run-driver-contract-tests.sh reference-16k
bash scripts/build-driver.sh reference-16k
```

构建输出分别位于 `.build/driver/profiles/reference-48k/` 和
`.build/driver/profiles/reference-16k/`，架构再分为 `arm64/` 与 `x86_64/`。
实验驱动的嵌入清单和 `identity-report.json` 用于确认 profile、初始采样率和架构。
这些命令只构建驱动，不安装到系统；不得将实验产物复制进正式发行包。
profile 构建必须使用命令中明确指定的名称，不支持的名称会报错退出。

## 设备与发行标识

以下为已确认且已写入驱动、安装包和卸载工具的标识合同；arm64 已核实实际设备 UID、名称和驱动版本，
主程序源码已接入正式 UID；真实遥控器和第三方软件验收仍待完成：

| 用途 | 标识 |
| --- | --- |
| 设备 UID | `com.leafney.tapsay.audio.device.2ch` |
| 驱动 Bundle ID | `com.leafney.tapsay.audio.driver` |
| 安装包收据标识 | `com.leafney.tapsay.audio.pkg` |
| 卸载工具 Bundle ID | `com.leafney.tapsay.audio.uninstaller` |

Intel 和 Apple Silicon 版本使用相同的设备身份。标识不包含版本号或处理器架构，
兼容升级保持不变；版本信息单独维护。TapSay 主程序接入提交为 `f3b803c`，
保留 MiRemoteV、BlackHole 支持和已有有效选择；本地构建包尚未自动替换已安装的主程序。

## 安装、升级与卸载

- 每个处理器架构分别提供一个 DMG，内含 PKG 安装包、APP 卸载工具及使用说明。
- 用户双击对应入口操作；项目同时维护安装脚本和卸载脚本。
- 安装不主动更改系统默认输入、输出或提示音设备，也不自动创建聚合设备或多输出设备。
- 允许新版覆盖旧版、同版修复重装及旧版覆盖新版，不因目标版本较低而限制安装，也无需先手动卸载。
- 覆盖安装期间临时保留旧驱动，失败时自动恢复；正常结束后清理本次临时材料，不长期保留 `backup.driver`。
- 安装已提交后，即使临时材料清理失败也不会回滚新版本；工具会报告残留，重新运行新版安装或卸载工具可重试清理。
- 仅当安装失败且自动恢复也失败时，保留唯一可供人工处理的旧驱动、旧状态和事务记录。
- 卸载只清理 TapSay Audio 自身文件和专属配置，保留 TapSay 主程序、用户音频设置和其他声卡。
- 卸载会在设备确认消失后，清理可核验归属本产品的旧版历史安装材料；未知对象、活动事务、待恢复材料和无法确认身份的目录会保留并列出。
- 已卸载用户可直接再次运行新版卸载工具检查并清理旧版遗留材料，不必先重装声卡。
- 卸载只有在驱动、安装状态、收据已清理且实际设备 UID 已消失时才报告完成。文件已清理但系统仍保留设备时，会明确提示手动重启 Mac；无法核实设备状态时不会报告成功。工具不会自动重启。
- 安装与卸载入口使用随包提供的原生程序；用户无需安装 Python 或 Xcode。
- DMG 附有 GPLv3 全文及 BlackHole 上游来源和许可说明。
- 操作可能短暂中断系统音频时提前提示，并允许取消；如需重启，提示用户自行安排，不自动重启。

目前暂无正式发行下载地址。分架构构建、包结构和隔离事务测试已完成。Apple Silicon
已验证安装后设备属性、三种实际采样率的双声道合成 PCM 环回，以及音量/静音写入回读和恢复。
同版覆盖安装已验证系统收据生成与重装后的三种采样率环回；首轮收据缺失问题已修复。
新版安装事务已在隔离目录覆盖成功、各故障注入、回滚、提交后清理失败和异常中断恢复，验证结果不代表真实系统历史材料已删除。
主程序正式 UID 检测及默认 16 kHz 单声道生产图的双声道接收也已通过合成音验收。
新版卸载的历史材料清理、升级/降级失败路径、TapSay 真实遥控器链路、
QuickTime、豆包/微信输入法兼容及 Intel 真机验收仍待执行。详细证据见
[阶段 6 验收记录](docs/implementation/phase-6-acceptance.md)。
正式发布前还需完成签名、公证和最终真机验收。

## 发布计划

正式版本计划通过本仓库的 GitHub Releases 发行，提供分架构 DMG、对应完整源码包、
校验文件及版本说明。各架构安装包分别完成验收后发布。

首版计划版本为 `0.1.0`。DMG 文件名区分 `arm64`、`x86_64`，各自包含
`TapSayAudio-2ch-0.1.0.pkg`、卸载工具及说明；PKG 文件名相同不代表两份文件的处理器架构相同。
运行 `bash scripts/build-packages.sh` 可生成 PKG、DMG、完整源码归档及 `SHA256SUMS.txt`。
构建结束同时生成 `dist/RELEASE-READINESS.md`；资产存在不代表签名、真机验收或正式发布已通过。

TapSay 主程序计划通过 `TapSayAudioDownloadURL` 打开正式发行页，由用户选择对应架构。
真实下载入口须在安装包正式发布并验证可下载后补充；当前没有可用的正式发行下载地址。

## 许可证

本项目采用 GNU GPL 第 3 版，完整条款见 [LICENSE](LICENSE)。

本项目基于 BlackHole 固定提交开发独立品牌的派生驱动。上游来源、许可记录和
引入第三方代码时的处理要求见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
发行包包含 GPLv3 源码归档，最终载荷及品牌材料审查仍作为发布门槛。
