# 阶段 1：源码基线、许可清单与身份合同

日期：2026-10-19
状态：已完成；已运行本阶段检查并提交
对应 PRD：`docs/plan/2026-10-18-audio-driver-distribution.md`

## 固定上游

- 项目：BlackHole，官方仓库 `ExistentialAudio/BlackHole`
- 标签：`v0.7.1`
- 完整提交：`e2b22aaaba4e507a097131704bf96dabc004d9cf`
- 官方源码归档 SHA-256：`5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0`
- 许可证：GNU GPL 第 3 版；上游 `LICENSE` 在 GPL 正文前还包含品牌及版权声明
- 本次实施只允许从固定提交自行构建，不使用上游预编译驱动、安装包、Team ID、图标或宣传素材
- 本地下载归档位于临时目录；尚未把驱动源码纳入项目构建。阶段 2 逐文件导入、改名并审查实际构建文件

核验命令及结果：

```text
curl -L https://github.com/ExistentialAudio/BlackHole/archive/e2b22aaaba4e507a097131704bf96dabc004d9cf.tar.gz
shasum -a 256 <downloaded-archive>
5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0
```

## 身份合同

所有构建、安装和发行工具读取 `config/product.json`。不要在驱动、安装脚本、卸载工具或发布脚本中另建可独立修改的身份常量。

| 字段 | 阶段 1 固定值 | 说明 |
| --- | --- | --- |
| 项目名 | `TapSay Audio` | 产品名 |
| 驱动 target / bundle / executable | `TapSayAudio` | 三者分开填写，首版值相同 |
| 驱动 Bundle ID | `com.leafney.tapsay.audio.driver` | 用户确认 |
| PKG receipt ID | `com.leafney.tapsay.audio.pkg` | 用户确认 |
| 卸载 APP Bundle ID | `com.leafney.tapsay.audio.uninstaller` | 用户确认 |
| 设备显示名 | `TapSay Audio 2ch` | 用户确认 |
| 设备 UID | `com.leafney.tapsay.audio.device.2ch` | 用户确认 |
| Box UID | `com.leafney.tapsay.audio.box` | 本阶段生成的项目专属标识 |
| Model UID | `com.leafney.tapsay.audio.model.2ch` | 本阶段生成的项目专属标识 |
| 隐藏设备 UID | 无 | 产品只发布一个用户可见设备；阶段 2 必须移除上游隐藏第二设备 |
| 插件工厂 UUID | `CC1226D1-A123-47B7-B113-5228AB089AA8` | 本阶段生成的 UUID v4；不得换成上游值 |
| AudioServerPlugIn 类型 UUID | `443ABAB8-E7B3-491A-B985-BEB9187030DB` | Apple 标准接口类型 UUID，保留原值 |
| 制造商 | `TapSay` | 项目产品标识 |
| transport type | `usb` | PRD 批准的兼容提案；不代表真实 USB 硬件 |
| 系统/架构 | macOS 14+；`arm64`、`x86_64` | 两个架构分别构建 |
| 声道/采样率 | 双声道；16,000 / 44,100 / 48,000 Hz | 初始值 16,000 Hz |
| 首版版本 | `0.1.0` | 与外层及内层资产版本一致 |

阶段 2 已发现的上游风险：

- 上游 C 源码默认还有一个隐藏的第二设备对象。TapSay 不发布隐藏设备，不能仅保留上游默认设置；必须修改枚举及相关对象路径，并用成品枚举检查证明只出现一个设备。
- 上游默认采样率是 48,000 Hz，公开采样率列表还包括本项目不支持的频率。阶段 2 必须将默认值改为 16,000 Hz，并把可协商列表限制为 16,000、44,100、48,000 Hz。
- 上游工程包含开发者 Team ID 和 BlackHole 图标引用。构建配置必须移除上游 Team ID；不把 BlackHole 图标复制到 TapSay 产物。
- 上游默认显示制造商 `Existential Audio Inc.`、BlackHole 产品名和上游 Bundle ID。构建后的设备及 bundle 读取值必须逐项与 `config/product.json` 对照。

## 本阶段验证

- 固定提交源码归档 SHA-256 与既有第三方核查记录完全相同。
- 本地环境为 Apple Silicon（arm64）、Xcode 15.1、Swift 5.9.2；阶段 2 首先验证 arm64 原生构建。
- Intel 真机不可用；仅可执行交叉构建和静态检查，不标记 Intel 真机兼容通过。
- `scripts/check-metadata.py` 检查产品身份、版本、架构、设备能力范围、UUID 合法性、上游提交/散列格式及标识冲突。
