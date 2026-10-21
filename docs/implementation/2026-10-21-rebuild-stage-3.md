# 重建阶段三：TapSay 最小适配

更正（2026-10-21）：本记录只证明构建和静态身份检查通过，阶段三尚未通过完整 HAL 合同。后续 AddressSanitizer 查询主设备控制列表触发越界，冻结参考也能复现。见 `2026-10-21-hal-control-list-blocker.md`；本记录不得作为可安装或稳定性结论。

依据：`docs/plan/2026-10-21-reference-driver-cleanup.md`。本阶段从固定 BlackHole v0.7.1 源码和无线麦 USB 补丁重新生成，不从旧 `Driver/TapSayAudio/` 派生。

## 交付

- `third_party/blackhole/upstream/` 保存构建需要的固定上游源码、工程、许可证和版本文件；上游 C SHA-256 为 `5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6`，工程 SHA-256 为 `8346211852797b491245302d6ad5d3e6b855d3d07bf37e4d4d5b0e64656a6c88`。
- `third_party/blackhole/tapsay-identity.patch`：只记录 TapSay 身份、产品名、UID、工厂入口、版本、工程 Bundle ID 和三项批准的正确性修复；不复制 BlackHole 图标或品牌资源。
- `scripts/build-driver.sh`：唯一新驱动构建入口，固定 arm64/macOS 14/Release，核对输入散列，隔离构建、元数据检查、签名检查；不再接受 `legacy`、`reference-48k` 或 `reference-16k` 参数。
- `config/product.json`：产品架构改为仅 `arm64`，默认率改为 `48000`，恢复完整 13 项采样率和隐藏设备 UID。

## 身份核验

隔离产物目录：`.build/tapsay-driver-arm64.0S77kU/TapSayAudio.driver`。驱动可执行文件 SHA-256：`85d66afd094a97690f3227d081a56605d2fa56fa5f7f64f85561c4925259db8c`。

产物读回结果：

- Bundle ID：`com.leafney.tapsay.audio.driver`；显示名：`TapSayAudio`；设备显示名字符串：`TapSay Audio 2ch`；版本：`0.1.0`/构建 `1`。
- 主设备 UID：`com.leafney.tapsay.audio.device.2ch`；Box UID：`com.leafney.tapsay.audio.box`；Model UID：`com.leafney.tapsay.audio.model.2ch`；隐藏设备 UID：`com.leafney.tapsay.audio.device.2ch.2`。
- 工厂 UUID：`CC1226D1-A123-47B7-B113-5228AB089AA8`；入口：`TapSayAudio_Create`；插件类型 UUID 保留 CoreAudio 标准值。
- 主设备 transport：USB；Box transport：Virtual；二进制仅 `arm64`；最低系统 `14.0`；`codesign --verify --deep --strict` 通过。

## 参考一致性与正确性修复

- C 源码保留双声道 Float32、13 项有序采样率、初始 `48000.0`、16384 帧设备缓冲、65536 帧环形缓存、物理/虚拟流格式和参考 IO 逻辑。
- 插件 OwnedObjects 第二项写入索引 1，避免把设备对象覆盖到索引 0。
- UID 翻译 qualifier 只有“不等于 `sizeof(CFStringRef)`”才报告大小错误；正常大小不再错误拒绝。
- 隐藏设备控制列表按 `kDevice2_ObjectList` 自身筛选，不读取主设备列表的索引。
- 静态检查确认输入/输出都保留，设备可声明完整采样率；尚未安装到 HAL，未执行真实 CoreAudio 枚举或遥控器音频链路验收。

## 验证

执行并通过：

```text
bash scripts/build-driver.sh
python3 读取 config/product.json 并核对 arm64、48000、13 项采样率和隐藏 UID
plutil / lipo / xcrun vtool / codesign / strings
git diff --check
```

Xcode 输出的 CoreSimulator 服务拒绝连接警告不影响 macOS 驱动构建；构建退出码为 0。没有写入 `/Library/Audio/Plug-Ins/HAL/`，没有重载音频服务，也没有改变已安装 MiRemoteV 或 BlackHole。

下一阶段门槛：重写独立 PKG、DMG、卸载入口和事务状态；不得把旧安装工具直接当作新实现。
