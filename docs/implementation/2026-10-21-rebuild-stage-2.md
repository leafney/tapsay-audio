# 重建阶段二：无线麦参考原样复现

依据：`docs/plan/2026-10-21-reference-driver-cleanup.md`。固定无线麦提交 `c9fabd1ef53e1a311dab4518a70693494631368b`；上游归档对应 BlackHole `e2b22aaaba4e507a097131704bf96dabc004d9cf`。新建 `scripts/build-reference-driver.sh`，引入固定 USB 补丁；不安装产物。

## 构建与可复核结果

运行 `bash scripts/build-reference-driver.sh`，退出码 0。脚本先核对归档、上游 C、工程和补丁 SHA-256，解压到 `.build/reference-arm64.XXXXXX/`；使用 `patch -p1` 应用 USB/工厂补丁并读回。随后以固定参数执行 Xcode Release/macOS SDK 构建，复制、strip 并作本地 ad hoc 签名。日志及完整 `-showBuildSettings` 在该隔离目录中。

有效设置：`ARCHS=arm64`、`ONLY_ACTIVE_ARCH=NO`、`MACOSX_DEPLOYMENT_TARGET=14.0`、`CODE_SIGNING_ALLOWED=NO`、`PRODUCT_NAME=MiRemoteV2ch`、`PRODUCT_BUNDLE_IDENTIFIER=com.hd838a.MiRemoteV2ch`、`kDriver_Name=MiRemoteV`、`kPlugIn_BundleID=com.hd838a.MiRemoteV2ch`、`kNumber_Of_Channels=2`。与参考脚本的本地未签名路径一致。

本次隔离目录 `.build/reference-arm64.ocPiNe`。签名后的可执行文件 SHA-256 为 `064159fd96e838239a1934c72df10756032b8b969015fde8cc9ad4704c6585f0`。`plutil` 读回 Bundle ID、工厂 `4a91361d-19af-4ba0-a87a-0a6242ed6ae4` 与 `BlackHole_Create`；`lipo -archs` 仅 `arm64`；`vtool` 最低 `14.0`；`codesign --verify --deep --strict` 通过。源文件静态核对 13 项有序采样率、初始 `48000.0`、16384 帧设备缓冲，以及物理/虚拟流格式处理；二进制字符串保留 `MiRemoteV %ich` 和主 UID 模板。完整输入输出 HAL 回调验证安排在阶段三，不以静态文本替代运行时验收。

最初试用 `git apply` 时，归档解压在父仓库 `.build/` 下，命令退出 0 却未更改嵌套源码。脚本现用 `patch` 并确认工厂 UUID 已出现在解压文件和成品 plist。早先失败的临时构建留在忽略目录以供诊断，可重建，不涉及已装 MiRemoteV。

参考产物与本机已装 MiRemoteV 可执行文件的 SHA-256 不同；本机已装文件由其他 Xcode/SDK 构建，不能声称二进制逐字节同源。参考原样保留上游图标只在本地隔离产物，不用于 TapSay 分发。下一阶段从已校验上游源和固定补丁开始生成独立 TapSay 驱动。
