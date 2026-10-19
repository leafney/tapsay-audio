# BlackHole 上游源码说明

- 官方仓库：`https://github.com/ExistentialAudio/BlackHole`
- 固定版本：`v0.7.1`
- 完整提交：`e2b22aaaba4e507a097131704bf96dabc004d9cf`
- GitHub 源码归档 SHA-256：`5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0`
- 许可证及上游版权/品牌声明：本目录的 `LICENSE`
- 本项目保留的派生文件：`Driver/TapSayAudio/TapSayAudio.c`、`TapSayAudio.plist`、Xcode 工程和 `Driver/TapSayAudioTests/main.c`

## TapSay 修改记录

2026-10-19 首次派生：

- 将驱动符号及工程目标改为 TapSay Audio 自有名称；保留 C 源文件原始版权行，并在修改过的源码/工程文件中记录修改日期。
- 设备 UID、Box UID、Model UID、驱动 Bundle ID、插件工厂 UUID、显示名、制造商和音频格式由 `config/product.json` 生成或传入构建。
- 移除未经授权的 BlackHole 图标和上游安装资源；驱动不再宣告依赖图标资源。
- 把驱动与 Box 上报的 transport type 改为 USB 类型，遵循获批 PRD。这里仅调整 CoreAudio 属性。
- 将插件/Box 的 DeviceList 和 UID 翻译限制为一个设备；不公布上游隐藏的第二个设备。
- 删除上游伪序列号，避免把虚拟声卡包装成有真实硬件序列号的设备。
- 将默认采样率改为 16,000 Hz，只保留 16,000、44,100、48,000 Hz。
- 修正插件 `OwnedObjects` 数组第二项写入位置，避免返回未初始化对象 ID。

`Driver/TapSayAudio/TapSayAudio.c` 源码仍包含上游开发者的版权声明。后续修改继续保留该声明并追加日期说明。本文件和散列只用于来源追踪，不能替代正式发行前对所有实际载荷文件、许可证及品牌素材的复核。
