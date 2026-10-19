# 阶段 2：双架构 HAL 驱动

日期：2026-10-19
对应规格：`docs/plan/2026-10-18-audio-driver-distribution.md`

## 交付及验证

- 固定 BlackHole 提交派生源码和工程、上游完整许可证及修改记录已纳入仓库。
- `bash scripts/run-driver-contract-tests.sh`：通过。直接调用驱动属性回调，检查插件与 Box 只枚举一个设备、精确 UID/名称/制造商、USB transport、16 kHz 默认值、两个流的三种 Float32 双声道格式及初始音量/静音。
- `bash scripts/build-driver.sh`：arm64、x86_64 分别构建成功，两个成品静态身份检查通过。产物位于 `.build/driver/<arch>/Build/Products/Release/TapSayAudio.driver`。
- 每个架构同目录输出 `identity-report.json`，明确区分静态检查和未执行的安装、真实音频与 Intel 真机检查。
- 上游品牌图标、安装脚本、Team ID 不参与本项目构建；完整版权、许可和来源仍保留。
- 修复上游 OwnedObjects 第二项写错位置、UID 翻译参数大小校验反向的问题；工厂 UUID 使用生成后的 plist 字面键，避免 Xcode 不展开字典键导致注册错误。

## 未覆盖

尚未安装进系统 HAL；尚未完成系统枚举、真实声音、环回稳定性及第三方软件验证。属性回调测试不代替真实链路验收。Intel 当前仅交叉构建成功，不代表 Intel 真机通过。当前为未正式签名的开发产物。
