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
- arm64 系统安装、CoreAudio 枚举和真实音频链路未完成。
- 豆包、微信输入法和 QuickTime 的对应软件版本及端到端验收未完成。
- Intel 真机验收未完成。
- GitHub Release 尚未发布，因此不存在真实下载 URL。

最终资产大小和散列由构建后的 `dist/RELEASE-READINESS.md` 与 `dist/SHA256SUMS.txt` 记录。`dist/` 不纳入 Git。

## 后续放行

用户主动启动 arm64 DMG 安装后，补完阶段 6 的本机验收；取得 Developer ID 账号和证书后，分别完成架构签名、公证和成品复核。Intel 包须另在原生 Intel 主机验收。所有门槛通过后才可发布 Release 并将真实发行页配置给主程序。
