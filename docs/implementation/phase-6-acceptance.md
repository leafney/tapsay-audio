# 阶段 6：设备与音频链路验收

日期：2026-10-19
对应规格：`docs/plan/2026-10-18-audio-driver-distribution.md`

## 已完成的隔离验收

- 增加只读 CoreAudio 诊断工具 `Tools/Transaction/Diagnose.swift`，报告系统可见设备的 UID、名称、transport、输入/输出流、当前采样率和离散支持采样率。
- 诊断工具以退出码区分 CoreAudio 查询失败、目标设备缺失和设备属性不符合合同，不修改系统路由或设备。
- HAL 回调测试调用真实 `StartIO`、PCM `WriteMix` 和 `ReadInput` 回调；验证双声道样本保持一致及环形缓冲区末尾回绕。
- `bash scripts/run-driver-contract-tests.sh`：通过。
- `bash scripts/build-native-tools.sh`：arm64、x86_64 诊断工具构建成功。

## 当前机器观测

- 主机：Apple Silicon，`arm64`；系统：macOS 14.1.2。
- 沙箱外执行 `./.build/native/arm64/TapSayAudioDiagnose`：CoreAudio 成功返回当前设备列表，但没有 `com.leafney.tapsay.audio.device.2ch`；工具以退出码 2 报告“CoreAudio 未枚举 TapSay Audio UID”。
- 系统同时枚举到内置麦克风/扬声器、USB 麦克风和其他虚拟设备，说明本次非空设备列表查询成功。
- 尚未安装本项目驱动；缺少 TapSay UID 是当前预期状态，不表示驱动安装失败，也不表示真实音频链路通过。
- 当前没有执行 PKG 安装或卸载。PRD 规定真实系统 HAL 只能在用户主动启动的安装/卸载路径中更改；本次编程与静态验收未触碰系统 HAL。

## 尚待真机验收

必须在用户主动启动 arm64 DMG 安装后继续记录：CoreAudio 实际 UID/名称/USB transport/双向流和三种格式、默认 16 kHz、PCM 输入输出录音、TapSay 真实遥控器声音、QuickTime、豆包、微信输入法、同版修复/升级/降级/卸载、默认音频路由保持及恢复行为。

目标软件列表可见、可选和收到声音仍是独立验收项。Intel 目前只有交叉构建，须另有 Intel 真机。不得把隔离回调测试、系统属性枚举或包构建写成端到端兼容通过。
