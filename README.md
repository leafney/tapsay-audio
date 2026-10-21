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
| 处理器 | Apple Silicon（arm64）；Intel（x86_64）暂不支持 |
| 设备显示名称 | `TapSay Audio 2ch` |
| 声道数 | 固定双声道 |
| 采样率 | 8、16、24、44.1、48、88.2、96、176.4、192、352.8、384、705.6、768 kHz |
| 默认采样率 | 48 kHz |
| 声道格式 | 双声道、32-bit Float PCM |
| 传输类型 | CoreAudio 上报 USB，仅用于应用兼容，不需要 USB 硬件 |
| 分发文件 | arm64 DMG，内含 PKG、卸载 APP 和中文说明 |

上述采样率均为双声道 Float32；实际第三方软件兼容性仍需按软件和版本实测。

首次安装后的声卡默认采样率设为 48 kHz。TapSay 遥控器源是 16 kHz 单声道，但驱动保持参考方案的通用输出能力，避免把应用源格式误当作声卡合同。
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

## 构建与验证

正式构建只使用固定参考方案，禁止旧 `legacy`、`reference-16k` 和 `reference-48k` profile。

```sh
python3 scripts/check-metadata.py
bash scripts/build-driver.sh
bash scripts/build-native-tools.sh
bash scripts/build-packages.sh
```

构建产物只面向 Apple Silicon arm64。安装前可使用隔离事务测试；安装到真实系统、重载音频服务和卸载需单独记录。当前没有正式下载地址。

主程序音频源仍是 16 kHz 单声道浮点；驱动默认 48 kHz，并保留完整参考采样率列表。验证必须区分设备可见、PCM 环回、遥控器音频到达、播放探测和第三方文字上屏。

旧阶段记录保留在 Git 历史和 `docs/implementation/`，不再作为正式构建入口。

## 发布计划

正式版本计划通过本仓库的 GitHub Releases 发行，提供 arm64 DMG、对应完整源码包、校验文件及版本说明。

首版计划版本为 `0.1.0`。DMG 文件名为 `TapSayAudio-2ch-0.1.0-arm64.dmg`，包含 `TapSayAudio-2ch-0.1.0.pkg`、卸载工具及说明。
运行 `bash scripts/build-packages.sh` 可生成 PKG、DMG、完整源码归档及 `SHA256SUMS.txt`。

TapSay 主程序计划通过 `TapSayAudioDownloadURL` 打开正式发行页。真实下载入口须在安装包正式发布并验证可下载后补充；当前没有可用的正式发行下载地址。

## 许可证

本项目采用 GNU GPL 第 3 版，完整条款见 [LICENSE](LICENSE)。

本项目基于 BlackHole 固定提交开发独立品牌的派生驱动。上游来源、许可记录和
引入第三方代码时的处理要求见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
发行包包含 GPLv3 源码归档，最终载荷及品牌材料审查仍作为发布门槛。
