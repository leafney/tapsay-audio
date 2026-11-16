# TapSay Audio

> 小声点（TapSay）的专属虚拟声卡组件

TapSay Audio 是面向「小声点（TapSay）」语音输入场景设计的 macOS 专属虚拟声卡。它把「小声点」采集到的遥控器语音送入 macOS 音频系统，供微信输入法、豆包输入法、会议软件及其他支持麦克风输入的应用使用。

安装后，系统设备列表中会显示 **TapSay Audio 2ch**。用户无需额外购买 USB 声卡，即可完成遥控器语音采集、软件识别和文字输入。

## 项目说明

「小声点」负责连接兼容的小米蓝牙遥控器、采集语音并处理按键与语音触发。TapSay Audio 负责把采集到的语音作为标准音频输入设备提供给 macOS。

```text
兼容的小米蓝牙遥控器
        ↓
小声点（TapSay）
        ↓
TapSay Audio 2ch
        ↓
微信输入法 / 豆包输入法 / 会议与录音软件
```

TapSay Audio 可独立安装和卸载，也可以与 `MiRemoteV 2ch`、`BlackHole 2ch` 等其他兼容虚拟声卡同时存在。安装和卸载只操作 TapSay Audio 自有组件，不会替换其他虚拟声卡。

主项目：[小声点（TapSay）](https://github.com/leafney/xiaoshengdian)

## 功能特性

- 提供 macOS 软件虚拟声卡，无需实体 USB 音频设备。
- 系统设备名固定为 `TapSay Audio 2ch`。
- 提供双声道 Float32 PCM 音频输入与输出。
- 默认采样率为 48 kHz。
- 支持 8、16、24、44.1、48、88.2、96、176.4、192、352.8、384、705.6、768 kHz。
- 兼容遥控器原始 16 kHz 单声道语音链路。
- 安装后可在 macOS 声音设置和应用麦克风列表中选择。
- 可与其他受支持的虚拟声卡同时安装和使用。
- 安装和卸载不会主动修改 Mac 的默认输入、输出或提示音设备。
- 提供独立卸载工具，便于完整移除驱动及相关安装材料。

## 兼容范围

| 项目 | 支持情况 |
| --- | --- |
| 操作系统 | macOS 14 及以上 |
| Apple Silicon | 提供 arm64 安装包 |
| Intel | x86_64 安装包 |
| 签名与公证 | 后续正式发布将完成 Apple Developer ID 签名与公证 |

Apple Silicon 和 Intel 用户请根据电脑芯片选择对应安装包。实际发布版本、可用架构及签名状态以 [GitHub Releases](https://github.com/leafney/tapsay-audio/releases) 页面为准。

## 安装方法

1. 打开 [TapSay Audio Releases](https://github.com/leafney/tapsay-audio/releases) 页面。
2. 根据自己的 Mac 芯片下载对应版本的 `.dmg` 文件：
   - Apple Silicon 请选择 arm64 版本。
   - Intel 请选择 x86_64 版本。
3. 双击打开下载的 `.dmg` 文件。
4. 双击 DMG 中的 `.pkg` 安装包。
5. 根据 macOS 提示输入管理员密码，并允许安装。
6. 等待安装完成和系统声卡枚举。
7. 如果安装工具提示需要重启，请先保存工作，再重新启动 Mac。
8. 打开“系统设置 → 声音”，在输入或输出设备列表中确认出现 `TapSay Audio 2ch`。

正式发布的安装包计划完成 Apple Developer ID 签名与公证，以减少 macOS 的安全拦截提示。若系统仍显示安全提示，请先确认安装包来自本仓库的 GitHub Releases，再按照当次发布说明操作。

## 在小声点中启用

### 首次启动小声点

1. 打开「小声点」，进入“使用引导”。
2. 完成蓝牙、输入监控和辅助功能权限授权。
3. 将兼容的小米蓝牙遥控器 2 Pro 连接到 Mac。
4. 进入“选择虚拟声卡”步骤。
5. 如果安装 TapSay Audio 前已经打开「小声点」，点击“重新检测”。
6. 选择 `TapSay Audio 2ch`。
7. 点击“确认并继续”。
8. 进入“试用语音输入”，长按遥控器语音键并说一句话，然后松开。
9. 确认输入法或目标软件能够正常显示识别文字后，进入工作台。

### 已经完成首次引导

1. 打开「小声点」。
2. 点击左侧导航中的“语音”。
3. 切换到“遥控器麦克风”模式。
4. 在“输入设备”下拉菜单中选择 `TapSay Audio 2ch`。
5. 建议保持“自动配置虚拟声卡”开关开启。
6. 点击“播放测试音”，确认虚拟声卡能够正常输出。
7. 长按遥控器语音键，在微信输入法、豆包输入法或其他目标软件中测试文字输入。

“自动配置虚拟声卡”会在进入遥控器麦克风模式时取消当前虚拟声卡的静音并调整其音量。该功能不会修改 MacBook 扬声器、耳机或其他真实输出设备。

切换设备后，可以前往“系统设置 → 声音 → 输入”，确认当前输入设备为 `TapSay Audio 2ch`。

## 卸载方法

1. 打开「小声点」，将麦克风模式切换为“系统麦克风”，或选择其他可用的虚拟声卡。
2. 退出「小声点」。
3. 重新打开 TapSay Audio 的 `.dmg` 文件。
4. 双击 DMG 中的“卸载 TapSay Audio.app”。
5. 根据提示确认卸载，并完成 macOS 管理员授权。
6. 等待卸载工具完成清理。
7. 如果工具提示需要重启才能完全移除设备，请保存工作，再重新启动 Mac。
8. 打开“系统设置 → 声音”，确认输入和输出设备列表中不再显示 `TapSay Audio 2ch`。

卸载工具不会自动重启 Mac，也不会删除未确认归属 TapSay Audio 的其他声卡或用户文件。

## 致谢

感谢「小声点（TapSay）」主项目提供遥控器连接、语音采集、设备选择与语音触发能力。

感谢 [无线麦 remote-mic-app](https://github.com/HD838A/remote-mic-app) 为 TapSay Audio 的驱动实现提供重要参考。

感谢 [BlackHole](https://github.com/ExistentialAudio/BlackHole) 提供 macOS 虚拟音频驱动基础。


## 许可

本项目采用 [GNU General Public License v3.0](LICENSE)。

第三方代码来源、版权与许可信息请参阅 [第三方说明](THIRD_PARTY_NOTICES.md) 和 [BlackHole 上游来源](third_party/blackhole/UPSTREAM.md)。
