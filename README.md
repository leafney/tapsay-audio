# TapSay Audio

> 小声点（TapSay）的专属虚拟声卡

TapSay Audio 是「[小声点（TapSay）](https://github.com/leafney/xiaoshengdian)」的配套虚拟声卡。它接收「小声点」采集的遥控器语音，并以 **TapSay Audio 2ch** 提供给 macOS，供微信输入法、豆包输入法、会议及录音软件使用。

用户无需额外购买 USB 声卡，即可完成遥控器语音采集、软件识别和文字输入。

## 项目说明

```text
兼容的小米蓝牙遥控器
        ↓
小声点（TapSay）
        ↓
TapSay Audio 2ch
        ↓
微信输入法 / 豆包输入法 / 会议与录音软件
```

TapSay Audio 可独立安装和卸载，也能与 `MiRemoteV 2ch`、`BlackHole 2ch` 等其他兼容虚拟声卡共存。安装和卸载不会替换其他虚拟声卡。


## 功能特性

- 设备名为 `TapSay Audio 2ch`，无需实体 USB 音频设备。
- 提供双声道 Float32 PCM 音频输入与输出，默认采样率为 48 kHz。
- 支持 8、16、24、44.1、48、88.2、96、176.4、192、352.8、384、705.6、768 kHz。
- 兼容遥控器原始 16 kHz 单声道语音链路。
- 可与其他受支持的虚拟声卡同时安装和使用。
- 安装和卸载不会主动修改 Mac 的默认输入、输出或提示音设备。
- 提供独立卸载工具，支持覆盖安装和版本回退。

## 兼容范围

| 项目 | 支持情况 |
| --- | --- |
| 操作系统 | macOS 14 及以上 |
| Apple Silicon | 提供 arm64 安装包 |
| Intel | 提供 x86_64 安装包 |
| 签名与公证 | 后续正式发布将完成 Apple Developer ID 签名与公证 |

实际发布版本、可用架构及签名状态以 [GitHub Releases](https://github.com/leafney/tapsay-audio/releases) 页面为准。

## 安装方法

1. 打开 [TapSay Audio Releases](https://github.com/leafney/tapsay-audio/releases)，根据 Mac 芯片下载 arm64 或 x86_64 的 `.dmg` 文件。
2. 打开 DMG，双击其中的 `.pkg` 安装包。
3. 完成管理员授权，等待安装和声卡注册完成。
4. 如果系统要求重启，请保存工作，再重新启动 Mac。
5. 打开“系统设置 → 声音”，确认列表中显示 `TapSay Audio 2ch`。

## 在小声点中启用

### 首次启动小声点

1. 打开「小声点」，按使用引导完成权限授权并连接遥控器。
2. 进入“选择虚拟声卡”步骤；必要时点击“重新检测”，选择 `TapSay Audio 2ch` 并继续。
3. 进入语音测试，长按遥控器语音键，确认输入法或目标软件能够正常显示文字。

### 已经完成首次引导

1. 打开「小声点」，点击左侧导航中的“语音”。
2. 切换到“遥控器麦克风”模式。
3. 在“输入设备”菜单中选择 `TapSay Audio 2ch`。
4. 保持“自动配置虚拟声卡”开启，并点击“播放测试音”确认声卡可用。
5. 长按遥控器语音键，在目标软件中测试文字输入。

“自动配置虚拟声卡”会取消当前虚拟声卡的静音并调整音量，不会修改 MacBook 扬声器、耳机或其他真实输出设备。

## 卸载方法

1. 打开「小声点」，切换到“系统麦克风”或选择其他可用的虚拟声卡，然后退出「小声点」。
2. 重新打开 TapSay Audio 的 `.dmg`，双击“卸载 TapSay Audio.app”。
3. 确认卸载并完成管理员授权，等待清理结束。
4. 如果工具提示需要重启，请保存工作，再重新启动 Mac。
5. 打开“系统设置 → 声音”，确认 `TapSay Audio 2ch` 已消失。

卸载工具不会自动重启 Mac，也不会影响其他虚拟声卡或删除未确认归属 TapSay Audio 的用户文件。

## 致谢

- 感谢「小声点（TapSay）」主项目提供遥控器连接、语音采集与设备选择能力。
- 感谢 [无线麦 remote-mic-app](https://github.com/HD838A/remote-mic-app) 为驱动实现提供重要参考。
- 感谢 [BlackHole](https://github.com/ExistentialAudio/BlackHole) 提供 macOS 虚拟音频驱动基础。
- 感谢所有参与安装测试、真机验证和问题反馈的用户。

## 许可

本项目采用 [GNU General Public License v3.0](LICENSE)。

第三方代码来源、版权与许可信息请参阅 [第三方说明](THIRD_PARTY_NOTICES.md) 和 [BlackHole 上游来源](third_party/blackhole/UPSTREAM.md)。
