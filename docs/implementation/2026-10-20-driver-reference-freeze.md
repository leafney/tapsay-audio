# 阶段一：无线麦参考配置冻结

日期：2026-10-20
对应规格：`docs/plan/2026-10-20-driver-reference-baseline.md`
状态：阶段一完成；进入阶段二前提交。

## 冻结的来源

| 来源 | 固定值 | 本次检查 |
| --- | --- | --- |
| BlackHole 上游 | v0.7.1，提交 `e2b22aaaba4e507a097131704bf96dabc004d9cf` | 解压目录为临时快照，无 `.git`；因此不以目录名宣称 Git 提交已验证 |
| 上游源码归档 | `/private/tmp/blackhole-e2b22aaaba4e507a097131704bf96dabc004d9cf.tar.gz` | SHA-256 `5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0`，与产品元数据一致 |
| 上游 C 源码 | `BlackHole/BlackHole.c` | SHA-256 `5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6`；与单独保留的参考副本一致 |
| 无线麦仓库 | 提交 `c9fabd1ef53e1a311dab4518a70693494631368b` | 仓库工作区干净 |
| 无线麦构建脚本 | `scripts/build-doubao-driver.sh` | SHA-256 `074db967329028e1e4dd3673f8ef5d6dbbfad150bce306980cf489f97c3875b0` |
| 发布变体脚本 | `scripts/release-variant.sh` | SHA-256 `db201e930e5efc9c6c51df422b33ee679d1fcbbbbf8955f3f3f81879d0ed4a99` |
| 无线麦补丁 | `third_party/blackhole/blackhole-device-usb.patch` | SHA-256 `51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f` |
| TapSay Audio 起始提交 | `3d85a55a6d772a0c3006e139912156ae72712cca` | 阶段开始时当前分支 `feat/61018`；现有未提交内容只有本规划文档 |
| TapSay 主程序测试候选 | `6fa3a6988e1c574f077b265553b2c64df12329d0` | 只用于后续固定版本测试；真实执行的安装应用还须单独记录散列 |

临时源码目录不能单独证明来源。上述归档散列可验证本次发现的压缩包字节内容；
实施脚本仍须自行校验同一上游散列，且不得读取该临时目录作为构建依赖。

## 当前差异清单

| 配置项 | 上游默认 | 无线麦构建后 | 当前 TapSay | 48 kHz 基线目标 |
| --- | --- | --- | --- | --- |
| 初始采样率 | 48000 Hz | 48000 Hz | 16000 Hz | 48000 Hz |
| 支持率表 | 13 个离散率：8000 至 768000 Hz | 未覆盖，沿用 13 个离散率 | 16000、44100、48000 Hz | 完整沿用 13 个离散率 |
| 主设备 | 可见、输入输出均有 | 双声道、可见、输入输出均有 | 双声道、可见、输入输出均有 | 保持 |
| 第二设备 | 隐藏；输入输出均有 | 未覆盖隐藏及流宏，沿用上游隐藏对象 | 存在对象代码，但插件/Box 列表与 UID 翻译收缩到单设备 | 按参考恢复隐藏对象的枚举、Box 归属、UID 翻译和流属性；仍保持隐藏 |
| Device transport | Virtual | USB（无线麦补丁） | USB | USB |
| Box transport | Virtual | 未修改，仍为 Virtual | USB | Virtual |
| 延迟 | 0 帧 | 未覆盖，沿用上游 | 0 帧 | 保持 |
| Device RingBufferSize | 16384 帧 | 未覆盖，沿用上游 | 16384 帧 | 保持 |
| Ring buffer 容量 | 65536 + latency 帧 | 未覆盖，沿用上游 | 65536 + latency 帧 | 保持 |
| 默认设备资格 | 允许默认输入与系统输入 | 未覆盖，沿用上游 | 由现有实现提供 | 阶段二按有效属性逐项验证，不改变 |
| 音量/静音与流控制 | 上游默认能力 | 未覆盖，沿用上游 | 现有实现含控制对象 | 按主设备属性及操作行为对齐；第二设备按上游对象定义 |
| 插件/Box 列表 | 主、隐藏设备均可查询 | 未覆盖，沿用上游 | 当前收缩为一个 TapSay 设备 | 恢复参考列表语义，使用 TapSay 专属第二 UID |
| `OwnedObjects` | 插件第二项存在上游索引写错缺陷 | 未修改上游 C | 插件对象第二项写入索引 1 | 保留 TapSay 修复，不回引越界/未初始化行为 |
| 产品身份 | BlackHole | `MiRemoteV` / `com.hd838a.MiRemoteV2ch` | TapSay 专属名称和身份 | 保留 TapSay 主、隐藏设备身份；不复制无线麦身份 |
| 伪序列号/品牌资源 | 上游包含 | 未由构建脚本改变源码行为 | TapSay 已移除上游图标资源并删除伪序列号 | 保持 TapSay 产品边界，不为行为对齐复制品牌素材 |
| 最低系统版本 | 工程 Release 12.3 | 脚本按 Apple Silicon 14.0 / Intel 13.0 覆盖 | 项目和构建均 14.0 | 保持 TapSay 14.0 产品支持合同 |
| 架构策略 | 工程按配置构建 | 每个发行变体 ARCHS 单架构、`ONLY_ACTIVE_ARCH=NO` | arm64/x86_64 各执行 `-arch`，`ONLY_ACTIVE_ARCH=YES` | 分架构构建；记录并对比有效 build settings，不把发行下限扩大到 13.0 |
| 签名/剥离 | 脚本构建后 `strip -S`，再 ad hoc 或 Developer ID 签名 | 去除上游资源元数据后签名 | 驱动构建 `CODE_SIGNING_ALLOWED=NO` | 保持发行事务；实验产物明确签名状态，必要签名沿项目流程完成 |

无线麦实际宏覆盖只有：

- `kDriver_Name="MiRemoteV"`
- `kPlugIn_BundleID="com.hd838a.MiRemoteV2ch"`
- `kNumber_Of_Channels=2`
- Device transport 补丁将 `kAudioDeviceTransportTypeVirtual` 改为 USB。
- Box transport 未被补丁修改，继续 Virtual。

无线麦脚本还显式传入单架构、`ONLY_ACTIVE_ARCH=NO`、最低系统版本、
目标产品名、Bundle ID、Release、macOS SDK、关闭 Xcode 自动签名；产物经 `strip -S`
后再 ad hoc 或 Developer ID 签名。TapSay 阶段二须对比双方 Xcode 有效 Release
build settings，不能仅以工程文件上的默认值代替脚本覆盖后的设置。

## 阶段一验证

- `python3 scripts/check-metadata.py`：通过。
- 上游归档 SHA-256 与 `config/product.json`：通过。
- 上游源码独立参考副本 SHA-256：通过。
- 无线麦仓库提交及干净状态：通过。
- 无线麦构建脚本、变体脚本、补丁散列记录：通过。
- 插件/Box DeviceList、UID 翻译、隐藏对象和 OwnedObjects 代码对照：已完成。
- 工作区检查：阶段开始前只有获批 PRD 与讨论文档，没有既有用户代码改动。

## 进入阶段二前的实现提醒

1. 当前项目 `check-metadata.py`、配置生成器、驱动构建器及 C 测试均把 16000 Hz、
   三种采样率和单设备合同写死，必须一并改为 profile 感知；只改 C 宏不算完成。
2. 当前 `config/product.json` 是正式产品身份来源。实验率表与默认率应新增独立 profile
   数据文件，不能用实验值覆盖身份元数据。
3. `build-packages.sh` 会清理其 `OUT` 下的旧产物，且以固定发行文件名输出。
   不可直接用它生成实验包；实验包应通过独立输出目录和 profile 文件名隔离。
4. 两 profile 构建不能并行调用当前生成器，因为生成器会写同一构建头和插件 plist。
   实现前先令生成输入及中间产物 profile 隔离，再执行连续构建。
5. 当前 C 测试只支持 3 种率并假设没有第二设备；必须依据 profile 重构预期值，
   增加隐藏设备查询与缓冲容量边界测试。
