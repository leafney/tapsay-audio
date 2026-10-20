# 阶段二：参考配置驱动基线

日期：2026-10-20
对应规格：`docs/plan/2026-10-20-driver-reference-baseline.md`
状态：自动检查及双架构构建通过；尚未安装或进行真实设备验收。

## 实现内容

- 新增 `config/driver-profiles.json`，定义 `reference-48k` 与 `reference-16k`。
  两者共用同一组声道、设备身份、设备枚举、运输类型、缓冲区和采样率列表；
  两 profile 对象只含各自的默认率。
- 配置生成器支持 profile 输出目录，生成隔离的 C 头文件、插件 plist 和 profile 清单。
  构建 profile 不覆盖正式源码目录中的生成头文件或 plist。
- 构建和合同测试脚本接受明确的 profile 名，并使用各自的构建/测试目录。
  未知 profile 在构建前拒绝。
- 实验 plist 写入 profile、默认采样率和完整采样率列表；
  产物检查器逐项回读并写入架构身份报告。
- `TapSayAudio.c` 在实验 profile 下暴露上游隐藏第二设备的 UID、名称、流和控制对象，
  补齐插件与 Box 的设备列表及 UID 翻译，并允许第二对象经过属性、设备客户端、
  采样率变更、IO 启停、时间戳及 PCM 回调入口。第二设备仍报告隐藏。
- 主设备 transport 为 USB；实验 Box transport 为 Virtual。
  profile 未启用时，旧正式配置仍保留单设备列表、USB Box transport、
  16 kHz 默认率及原三种采样率合同。
- 保留 TapSay 自有产品身份及插件工厂 UUID，并保留插件 `OwnedObjects`
  第二项写到索引 1 的安全修复。
- README 新增实验构建命令、输出目录及“只构建、不安装、不用于正式发行”的边界说明。

## 自动测试

通过的命令：

- `python3 scripts/check-metadata.py`
- `python3 scripts/check-metadata.py --profile reference-48k`
- `python3 scripts/check-metadata.py --profile reference-16k`
- `python3 scripts/check-metadata.py --profile invalid`：按预期拒绝未知配置。
- `bash scripts/run-driver-contract-tests.sh legacy`
- `bash scripts/run-driver-contract-tests.sh reference-48k`
- `bash scripts/run-driver-contract-tests.sh reference-16k`
- `bash -n scripts/build-driver.sh scripts/run-driver-contract-tests.sh`
- `PYTHONPYCACHEPREFIX=.build/pycache python3 -m py_compile scripts/check-metadata.py scripts/generate-driver-config.py scripts/check-driver-artifact.py`
- `git diff --check`

profile 合同测试覆盖：

- 初始率分别为 48000 与 16000 Hz。
- 精确且有序的 13 个上游采样率；列表外 32000 Hz 不被接受。
- 两条流均声明完整率表的双声道 Float32 格式。
- 插件及 Box 设备列表的零、一、两个元素容量行为。
- 插件拥有对象在零、一、两个及过量容量下返回与写入数量相等。
- 隐藏设备 UID、名称、隐藏属性和 UID 翻译。
- 隐藏设备输入/输出流和控制对象列表。
- 主设备 USB 与 Box Virtual 分别读取。
- 主设备及隐藏设备分别执行 `StartIO`、PCM 写入/读取和 `StopIO` 回调。
- 旧正式 profile 的单设备、USB Box、三种采样率合同没有回归。

这些测试直接调用本项目 HAL 回调，不安装驱动，也不证明 CoreAudio 服务已加载实验产物。

## 构建产物核对

执行：

- `bash scripts/build-driver.sh reference-48k`
- `bash scripts/build-driver.sh reference-16k`
- `bash scripts/build-driver.sh legacy`

两个实验 profile 均完成 arm64、x86_64 Release 构建和产物身份检查。首次构建后复核发现
构建脚本曾传入 `ONLY_ACTIVE_ARCH=YES`，与 PRD 固定的参考值 `NO` 不一致；
已修正脚本并重新执行两种 profile 的完整双架构构建，四条 xcodebuild 命令均显示
`ONLY_ACTIVE_ARCH=NO`，产物身份检查通过。重建后的二进制散列与先前记录相同。
Xcode 日志中有
CoreSimulator 服务无法连接的主机诊断，但 macOS 驱动目标的 `BUILD SUCCEEDED`、
架构检查和身份报告均通过；没有 TapSay C 编译错误。

| Profile | 架构 | 默认率 | 支持率数量 | 二进制 SHA-256 |
| --- | --- | ---: | ---: | --- |
| reference-48k | arm64 | 48000 | 13 | `00cb6816826cf7ba68a3cca23b95a9c1ba5db4a7bcbdf44179484c2c4620c590` |
| reference-48k | x86_64 | 48000 | 13 | `9ee095ee5342bc3707e5f4f3acf154aa1efb7e4cc8c0479e8ef0b829c2a25f5d` |
| reference-16k | arm64 | 16000 | 13 | `bf888706fc05106d01b508c6b7c0c060fdbf1d557d28fa11ea0aca8b754f6018` |
| reference-16k | x86_64 | 16000 | 13 | `decf08e374a53f600be86711442abaa24cb30c03dbf77ed1bcc86463d831db56` |

16 kHz profile 构建后重新计算 48 kHz arm64/x86_64 二进制散列，均与构建前相同。
四份 Info.plist 的嵌入 profile、默认率和采样率数组与相应 profile 清单相符。
正式 legacy 构建的两个架构也通过产物身份检查。

身份报告中的 `installed_device_check`、`audio_chain_check` 和 `intel_hardware_check`
仍为 `not_run`，不属于构建通过的部分。

## 尚未完成

- 没有安装或替换系统 HAL 驱动。
- 没有重载 CoreAudio 服务或改变系统音频路由。
- 没有检查运行中的驱动 Bundle ID、散列或实际采样率。
- 没有用 RC003、MiRemoteV 实际切回、第三方输入法或长时间运行矩阵验收。
- x86_64 只有交叉构建，不代表 Intel 真机通过。
- 隔离实验 PKG 曾在发现构建参数偏差前构建；该包仅用于校验包构建链路，
  不作为阶段三实测候选。阶段三须从修正后的配置重新构建唯一标识的新包。

## 阶段结论

两种 profile 的配置、驱动回调合同、正式配置回归和修正后的双架构 Release 构建通过，
满足阶段二自动门槛。该结论不表示声卡的真实系统音频链路已通过；
阶段三必须先构建并检查隔离实验包，再按 PRD 完成 MiRemoteV 对照及真实设备矩阵。
