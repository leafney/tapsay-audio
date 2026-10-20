# 阶段三：48 kHz 实验包准备

日期：2026-10-20
对应规格：`docs/plan/2026-10-20-driver-reference-baseline.md`
状态：包构建工具和静态校验已验证；未安装，真实音频验收未开始。

## 实现内容

- 新增 `scripts/build-experiment-package.sh`，只在 `.build/experiments/<profile>/<架构>/<源码提交>/`
  下创建实验包；不调用会清理 `dist/` 的正式发行脚本。
- 包文件名和输出目录包含 profile、架构及源码提交短号；遇到同名结果或临时路径时拒绝覆盖。
- 复用现有事务安装脚本和事务工具，不更改安装事务、卸载器、安装目录或正式包名。
- 实验清单随驱动保存在 `Contents/Resources/TapSayAudio-experiment-manifest.json`，
  并在构建目录另存一份相同清单。
- 清单记录实验 profile、默认率、完整率表、设备身份、源码提交及脏工作区文件、
  BlackHole 提交与归档散列、冻结记录中的无线麦补丁散列、Xcode/SDK、架构、
  最低系统、有效构建参数、驱动散列和实验包签名状态。
- `scripts/check-package.py` 保持正式包的 `PKG ARCH` 调用方式；
  实验包必须用 `PKG ARCH PROFILE`，并核对 Info.plist、清单、驱动散列、
  架构、隐藏设备 UID 与名称。省略 profile 或 profile 不匹配时拒绝。

## 验证

- `bash -n scripts/build-experiment-package.sh`：通过。
- `PYTHONPYCACHEPREFIX=.build/pycache python3 -m py_compile scripts/check-package.py`：通过。
- `python3 scripts/check-metadata.py --profile reference-48k`：通过。
- `bash scripts/build-native-tools.sh`：通过；构建 arm64 和 x86_64 事务工具。
- `bash scripts/build-experiment-package.sh reference-48k arm64`：通过。
- 包检查器以 `reference-48k` 检查：通过。
- 省略 profile、指定 `reference-16k` 或未知 profile：均按预期拒绝。
- `git diff --check`：通过。

验证用包由提交 `6932bf4fcd1b` 对应的脏工作区构建，清单如实列出当时两项阶段三脚本改动。
该包只证明隔离构包和校验链路可运行，不是实机测试候选包。提交本阶段准备代码后，
需从干净提交重新构建候选包，并按阶段三操作单取得安装授权。

## 系统状态

- 未运行安装器，未覆盖 `/Library/Audio/Plug-Ins/HAL` 中的驱动。
- 未重载 CoreAudio，未切换默认输入、输出或提示音设备，也未改变采样率。
- 未连接或操作 RC003，也未开始 MiRemoteV 对照和 60 分钟验收矩阵。
- 当前只有 arm64 实验包准备流程做过构建检查；x86_64 profile 驱动有交叉构建，
  不代表 Intel 实机验收。

## 当前结论

阶段三的实验包准备工具已通过静态检查和包内容检查；阶段三真实验收仍未完成。
下一步从本次提交构建干净工作区的 `reference-48k` arm64 候选包，记录只读系统快照、
当前安装版本、路由和采样率，再提供具体安装操作单。
