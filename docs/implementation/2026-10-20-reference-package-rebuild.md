# 清空发行目录并重建参考安装包

日期：2026-10-20
依据：`docs/plan/2026-10-20-driver-reference-baseline.md`
用户要求：删除 `dist` 中旧文件，重新编译当前安装包。

## 构建范围

从干净提交 `9a8481d3dcce` 构建 `reference-48k`，默认 48000 Hz、双声道。
显式选择参考配置，避免不带参数的普通入口使用 legacy 的 16000 Hz 默认值。
没有修改驱动、主程序、系统音频配置或安装脚本，也没有执行安装。

删除 `dist` 中原有 10 个文件，包括旧 PKG、DMG、源码归档及说明文件。
原有 `.build/experiments` 实验包、安装备份和真实测试证据保留。
对 reference-48k 的 arm64、x86_64 分别执行 Xcode clean 后重新编译，
原生安装工具也重新构建，未直接复制旧安装包。

## 验证

- `bash scripts/run-driver-contract-tests.sh reference-48k`：通过。
- `bash scripts/build-native-tools.sh`：两个架构构建通过。
- `bash scripts/build-driver.sh reference-48k`：两个架构编译及产物身份检查通过。
- 对固定上游源码和工程校验散列，分别运行 `audit-reference-build.py`：
  两个架构的完整构建设置和音频宏核对通过。
- 两次 `build-experiment-package.sh reference-48k <架构>`：成功；
  脚本内嵌的安装包内容检查均通过。
- 复制到 `dist` 后重新计算散列，与原包和构包记录一致；
  清单均为默认 48000 Hz、双声道、来源工作区干净。

重新编译的驱动与此前实测的 b98419af1016 版本散列一致：

| 架构 | 驱动 SHA-256 |
| --- | --- |
| arm64 | `fc4e0d9966c960685de77863708d59fe4f06de02af77f208c36aa1b0b6e4bddd` |
| x86_64 | `0b29917753dede17cd5e864545bf0fd0e20e4e180de91585e68d65d254366d18` |

## 交付

`dist` 目前只包含以下两个本地参考实验安装包及 `SHA256SUMS.txt`：

| 文件 | PKG SHA-256 |
| --- | --- |
| `TapSayAudio-Reference-reference-48k-arm64-9a8481d3dcce.pkg` | `c542d40c9bd0d5fab3e3124caced3749070eda5c2c6936b88da4ae2a59dcf8ab` |
| `TapSayAudio-Reference-reference-48k-x86_64-9a8481d3dcce.pkg` | `10875d2cc96c5b2a0f3cc12ffccac908a48d6ea646260ff911bea04bde9fe045` |

本地包未签名；沿用既有参考实验安装事务，不把本机历史配置清理加入安装脚本。
默认值是编译期配置，安装后的实际率仍应读取确认。
arm64 为本机架构；x86_64 完成构建和静态检查，未进行 Intel 真机验收。
此前的真实语音及切回结果见 `2026-10-20-reference-runtime-alignment.md`；
重新构包不补齐长时间测试或整机重启验收，也不表示阶段三完整通过。

构建、清理和合同测试日志：`.build/rebuild-48k-9a8481d/`。
完整构建证据及参考核对：`.build/driver/profiles/reference-48k/<架构>/Build/Products/Release/`。
各架构实验清单与构包记录：`.build/experiments/reference-48k/<架构>/9a8481d3dcce/`。
