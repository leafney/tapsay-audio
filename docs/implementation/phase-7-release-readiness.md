# 阶段 7：发行准备与放行审计

日期：2026-10-19
对应规格：`docs/plan/2026-10-18-audio-driver-distribution.md`

## 已完成

- `scripts/check-release-readiness.py` 审计分架构 PKG/DMG、对应源码归档、SHA-256 清单、PKG 签名状态及 DMG 完整性。
- 生成 `dist/RELEASE-READINESS.md`，逐项列出资产散列和未满足门槛。
- `--formal` 模式在存在未满足门槛时以非零状态退出，避免开发包被误标为正式发行。
- 本阶段不创建 GitHub Release、不调用外部工单或 GitHub CLI，不设置虚构下载地址。

## 当前发行结论

当前开发资产可本地复核，但**不具备正式放行条件**：

- Developer ID 签名与公证未完成。
- arm64 已完成用户启动安装、同版覆盖、系统收据生成、旧驱动备份核对、CoreAudio 属性和三种采样率合成 PCM 环回；升级、降级、卸载等其余生命周期仍待真机验收。
- TapSay 正式 UID 尚未接入主程序，遥控器真实音频链路未完成。
- 豆包、微信输入法和 QuickTime 的对应软件版本及端到端验收未完成。
- Intel 真机验收未完成。
- GitHub Release 尚未发布，因此不存在真实下载 URL。

最终资产大小和散列由构建后的 `dist/RELEASE-READINESS.md` 与 `dist/SHA256SUMS.txt` 记录。`dist/` 不纳入 Git。

## 后续放行

用户已完成首轮 arm64 安装及修正包同版覆盖，系统收据和备份复测通过；继续补完阶段 6 的其余生命周期和第三方软件验收。主程序需审批接入已交付 UID；桌面操作服务恢复或用户执行验收后，才能补录软件列表与实际录音结果。取得 Developer ID 账号和证书后，分别完成架构签名、公证和成品复核。Intel 包须另在原生 Intel 主机验收。所有门槛通过后才可发布 Release 并将真实发行页配置给主程序。
