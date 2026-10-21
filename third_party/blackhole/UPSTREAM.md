# BlackHole 固定参考来源

- 官方仓库：https://github.com/ExistentialAudio/BlackHole
- 固定版本：v0.7.1，提交 `e2b22aaaba4e507a097131704bf96dabc004d9cf`。
- 原始源码归档 SHA-256：`5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0`。
- `upstream/` 原样保存构建所需文本；`SOURCE-SHA256.json` 固定原始文件与补丁散列。
- 上游完整版权/许可见 `LICENSE`；GPLv3 源码不包含对官方预编译包及品牌素材的额外授权。

## 当前派生方式（2026-10-21）

先应用无线麦固定 USB/工厂补丁，再应用 TapSay 独立身份补丁。只替换产品身份、版本和品牌资源，保留原始版权。默认 48000 Hz，保留参考完整采样率、隐藏第二设备、Box Virtual、主设备 USB 和音频算法。早期三项属性修复及后续控制列表修复均不进入本轮，按用户要求在真机部署后再考虑。

`scripts/build-driver.sh` 从这些本地源码独立构建；`check-reference-source.py` 核对除允许的身份改动之外 C 逐字节相同。TapSay 图标由本仓库 `Tools/BuildIcon.swift` 生成，不分发上游品牌图标。修改通过身份补丁、本说明及对应源码归档记录。

无线麦参考仓库固定提交：`c9fabd1ef53e1a311dab4518a70693494631368b`。参考补丁 SHA-256：`51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f`。主程序、品牌图片与上游官方二进制不进入独立声卡分发。

实际部署结果见 `docs/implementation/2026-10-21-reference-only-deployment.md`。当前为未签名、未公证的本地验证包；正式发布前仍需核对最终载荷、对应源码与下载字节。
