# TapSay Audio

TapSay 的独立虚拟声卡项目，设备显示名称为 `TapSay Audio 2ch`。

当前实施规范为 [重建 PRD](docs/plan/2026-10-21-reference-driver-cleanup.md)，交接与决策见 [讨论记录](docs/discuss/2026-10-21-reference-driver-cleanup.md)。

当前状态：HAL 回调验证发现参考源码与 TapSay 派生均存在控制列表越界，阶段三尚未验收、阶段四待重写，阶段五清理暂缓。当前 `dist/` 开发包不可用于安装验收或发布；尚无正式下载地址。详见 [阻塞记录及候选修复](docs/implementation/2026-10-21-hal-control-list-blocker.md)。候选补丁仅供审阅，没有加入构建。

## 项目命名

| 项目 | 名称或文案 |
| --- | --- |
| 项目名称 | `TapSay Audio` |
| GitHub 仓库 | `tapsay-audio` |
| 系统设备名称 | `TapSay Audio 2ch` |
| PKG 文件名示例 | `TapSayAudio-2ch-0.1.0.pkg` |
| 引导页中文说明 | 安装 TapSay 配套虚拟声卡 |

## 首版支持范围

arm64 驱动与本地 PKG/DMG 已完成构建，但 HAL 合同尚未通过；旧版验证结果不适用于本次重建。
用户理解支持范围时，以本节及发布说明为准：

| 项目 | 首版范围 |
| --- | --- |
| 系统 | macOS 14 及以上；重建候选尚未完成真机验收 |
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
将 CoreAudio transport type 上报为 USB；重建候选的实际加载属性及应用兼容仍需实测。
本项目实际仍是软件虚拟声卡，无需额外 USB 硬件。
验收不仅检查系统能否发现设备，也检查目标软件中能否选用并实际收到声音。

TapSay 主程序当前产生的是 16 kHz 单声道浮点音频，这与虚拟声卡支持的双声道、
多采样率能力不同。目标是用户选择声卡后即可使用，无需手动调整采样率。
本次重建尚未验证主程序在新驱动下的格式转换、真实遥控器及第三方软件接收效果；
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
