# TapSay Audio

TapSay 配套独立虚拟声卡，系统设备名为 **TapSay Audio 2ch**。

当前驱动沿用已完成一天多用户实测的参考实现。正在改进仓库、构建和安装卸载外围；驱动属性修复等待本轮人工测试后再开始。当前规范见 [外围改进计划](docs/plan/2026-10-22-peripheral-improvements.md)，分析见 [稳定版审阅](docs/discuss/2026-10-22-stable-version-review.md)。

## 支持范围

| 项目 | 范围 |
| --- | --- |
| 系统与处理器 | macOS 14 起，Apple Silicon arm64；Intel 暂不支持 |
| 设备名称 | TapSay Audio 2ch |
| 音频格式 | 双声道 Float32 PCM，默认 48 kHz |
| 可用采样率 | 8、16、24、44.1、48、88.2、96、176.4、192、352.8、384、705.6、768 kHz |
| 设备类型 | 软件虚拟声卡，CoreAudio 上报 USB；无需 USB 硬件 |

遥控器音频源仍是 16 kHz 单声道。格式列表表示驱动能力，不等于所有软件及采样率均已完成真机验收。已有用户报告当前版本日常使用稳定，其他环境需按软件和版本验证。

## 安装与卸载

打开 DMG，双击其中的安装 PKG。卸载时双击“卸载 TapSay Audio.app”。支持升级、同版重装及降级覆盖；只操作本产品，不替换 MiRemoteV 或 BlackHole，不主动修改默认输入输出设备。

卸载提示会区分设备已消失、需要重启、无法确认及历史材料部分保留。工具不会自动重启 Mac。当前产物用于本地人工测试，尚未签名、公证或公开发行，没有正式下载地址。TapSay 主程序的 `TapSayAudioDownloadURL` 需在正式发布后配置。

安装后只读等待设备枚举约五秒，结果写入安装日志及 `/Library/Application Support/TapSay Audio/install-state.json`。设备未出现时提示重启或待确认，不因枚举延迟回滚已部署文件；设备出现也不表示真实音频链路已通过。

开发排查时，可导出只读诊断报告：

```sh
.build/native/arm64/TapSayAudioDiagnose > /tmp/tapsay-audio-diagnose.json
```

报告包含系统、设备名义采样率、输入输出物理/虚拟格式、磁盘驱动版本与散列；不改控件、采样率或路由。`null` 表示无法读取。磁盘散列不能证明系统当前加载的实例相同。合成环回工具独立运行，默认 48 kHz，构包和普通诊断不会启动它。

## 构建与验证

版本号及构建号只在 `config/product.json` 配置。构建仅使用 `third_party/blackhole/upstream`、固定 USB 补丁和身份补丁，不接受实验 profile。

```sh
python3 scripts/check-metadata.py
python3 Tests/ReleaseToolsTests.py
bash scripts/build-packages.sh
```

构包自动运行同一驱动产物的源码/格式合同检查、安装卸载隔离测试、PKG 和 DMG 内容检查。所有检查通过后整体替换 `dist/`；失败保留之前的产物。构建可能需要系统工具运行权限，不会安装声卡或重载音频服务。

单独构建驱动后，可指定其构建记录验证：

```sh
bash scripts/build-driver.sh
bash scripts/run-driver-contract-tests.sh --build-result .build/latest-driver.json
```

产物为 `TapSayAudio-2ch-版本.pkg`、`TapSayAudio-2ch-版本-arm64.dmg`、对应源码包、校验值及 `BUILD-RESULT.json`。旧驱动、实验入口及过期文档已从当前工作树移除，历史可通过 Git 查询。本机故障证据及恢复材料仍保留。

## 稳定基线与许可

上一版交付及用户手动部署记录见 [参考部署记录](docs/implementation/2026-10-21-reference-only-deployment.md)。当前默认 48 kHz、采样率表、缓冲和 IO 算法保持该基线。

本项目采用 [GNU GPL 第 3 版](LICENSE)。固定上游版权及来源见 [第三方说明](THIRD_PARTY_NOTICES.md) 和 [上游来源](third_party/blackhole/UPSTREAM.md)。安装包同步提供对应源码及必要构建、安装脚本。
