# BlackHole 固定参考来源

- 官方仓库：https://github.com/ExistentialAudio/BlackHole
- 固定版本：v0.7.1，提交 `e2b22aaaba4e507a097131704bf96dabc004d9cf`。
- 原始源码归档 SHA-256：`5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0`。
- `upstream/` 原样保存构建所需文本；`SOURCE-SHA256.json` 固定原始文件与补丁散列。
- 上游完整版权/许可见 `LICENSE`；GPLv3 源码不包含对官方预编译包及品牌素材的额外授权。

## 当前派生方式（2026-10-22）

先应用无线麦固定 USB/工厂补丁，再应用 TapSay 独立身份补丁。保留原始版权。默认 48000 Hz，保留参考完整采样率、隐藏第二设备、Box Virtual、主设备 USB 和音频算法。用户确认前两批人工测试无问题后，已授权第三批属性正确性修复。

2026-10-22 新增修改：`plugin-properties.patch` 修正 OwnedObjects 第二项索引和两种 UID qualifier 大小判断；`control-list-properties.patch` 修正关闭 Pitch 时的控制计数、scope 筛选、数组/容量边界及隐藏设备控制对象选择，并使每次读取持同一状态锁。两补丁位于身份补丁之后，散列固定在 `SOURCE-SHA256.json`。历史 `proposals/` 保留为对照，不参与正式构建。

`scripts/build-driver.sh` 从这些本地源码独立构建；`check-reference-source.py` 保留原样参考对照并应用明确属性补丁，核对除允许身份变化和这些补丁之外 C 逐字节相同。固定 `upstream/` 文件不变。TapSay 图标由本仓库 `Tools/BuildIcon.swift` 生成，不分发上游品牌图标。全部修改通过补丁、本说明及对应源码归档记录。

无线麦参考仓库固定提交：`c9fabd1ef53e1a311dab4518a70693494631368b`。参考补丁 SHA-256：`51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f`。主程序、品牌图片与上游官方二进制不进入独立声卡分发。

实际部署结果见 `docs/implementation/2026-10-21-reference-only-deployment.md`。当前为未签名、未公证的本地验证包；正式发布前仍需核对最终载荷、对应源码与下载字节。
