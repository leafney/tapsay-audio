# 阶段 5：分架构包装与源码归档

日期：2026-10-19
对应规格：`docs/plan/2026-10-18-audio-driver-distribution.md`

## 交付

- arm64、x86_64 分别构建 HAL、原生事务程序、原生卸载界面和 PKG/DMG。
- PKG 使用 `--root` 指向空目录，生成标准空载荷与 Bom，供 Installer 创建系统收据；实际驱动仍放在脚本资源中，由原生事务程序校验身份、主机架构和 Mach-O 载荷后完成备份、替换及失败恢复。空载荷不能含 HAL 或任何普通文件。
- 首轮真机安装发现 `--nopayload` 仅脚本包没有生成预期收据，因此修正为上述空根目录包装；用户主动发起修正包同版覆盖后，系统收据生成及旧驱动备份已实测通过，证据见阶段 6。
- 每个 DMG 含同名 PKG、对应架构的卸载 APP、中文说明、GPLv3 全文和第三方许可说明。
- 卸载界面使用 AppKit 显示清理范围和管理员授权；特权操作只调用独立事务程序，不以管理员权限运行界面。
- 源码归档含驱动、固定上游许可及来源、构建和安装脚本、事务与卸载源码、对应架构开发工具及阶段记录。
- 包文件不是通用二进制；Intel 和 Apple Silicon 必须下载匹配 DMG。

## 验证

- `python3 scripts/check-metadata.py`：通过。
- `bash scripts/run-driver-contract-tests.sh`：通过；检查身份、公开格式、USB 属性、默认 16 kHz，并直接执行 PCM 写入/读取及环形缓冲区回绕。
- `python3 scripts/test-native-transaction.py`：通过；覆盖隔离首装、部署失败恢复、恢复失败保留来源、假身份拒绝、符号链接拒绝、重复卸载和保留备份。
- `python3 scripts/check-uninstaller.py`：通过；核对 Bundle ID、版本、资源和两种架构二进制。
- `python3 scripts/check-package.py dist/TapSayAudio-2ch-0.1.0-arm64.pkg arm64`：通过。
- `python3 scripts/check-package.py dist/TapSayAudio-2ch-0.1.0-x86_64.pkg x86_64`：通过。
- 两个 DMG 均通过 `hdiutil verify`；只读检查目录确认各自含正确架构卸载工具、PKG、说明和许可证。
- `pkgutil --check-signature` 显示两个 PKG 均为 `no signature`；DMG 与卸载 APP 也未签名或公证。
- 隔离 PCM 测试仅验证驱动回调中的环回与回绕；不等同于已加载 CoreAudio 的实际设备传输。

## 资产

文件大小和 SHA-256 以当次构建的 `dist/SHA256SUMS.txt` 和 `dist/RELEASE-READINESS.md` 为准。`dist/` 不纳入 Git；构建命令为 `bash scripts/build-packages.sh`。文档不保留已经被后续构建替代的旧散列。

源码归档的自校验值不能写入归档自身；以同目录 `SHA256SUMS.txt` 及 `RELEASE-READINESS.md` 中记录的最终字节数和 SHA-256 为准。

## 限制

- arm64 已执行用户主动启动的 PKG 安装、同版覆盖、系统收据及备份核对、系统授权和 CoreAudio/合成音频验收；升级、降级、真实卸载和休眠唤醒尚待验证，详见阶段 6。
- 卸载提权入口调用已弃用的 macOS Authorization Execute 接口；当前仅完成编译和静态检查，必须在 macOS 14 真机验证成功、取消和失败反馈，签名发布前应评估迁移到受支持的特权辅助程序机制。
- 真实遥控器、QuickTime、豆包、微信输入法及第三方设备列表兼容尚未验证。
- 当前没有 Intel 真机；x86_64 构建和静态检查不能作为 Intel 真机通过证据。
- 没有 Developer ID 账号与证书；正式签名、公证、GitHub Release 和真实下载地址仍未就绪。
