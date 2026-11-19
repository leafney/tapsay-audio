# Intel 版最低系统版本讨论

## 原始需求

将 Intel 架构安装包的最低系统版本从 macOS 14 调整为 macOS 13，Apple Silicon 版本继续要求 macOS 14。

## 问答和澄清

1. **是否有 macOS 13 Intel 真机进行验收？** 用户表示目前尚未进行真机验证。先完成打包，再下载安装包进行真机验证；不要求真机验证先于打包。
2. **通过什么方式构建 Intel 测试包？** 用户明确纠正：使用现有 GitHub Actions 流程构建和打包 Intel 架构，而不是依赖当前 Apple Silicon 机器本地构建。

## 共同理解

- Intel 安装包的目标是 macOS 13 及以上；Apple Silicon 安装包仍为 macOS 14 及以上。
- 更新实际编译目标、安装限制、运行时检查、验证和用户说明，不能只修改显示文字。
- 使用现有手动 GitHub Actions 工作流生成未认证的调试 Artifact；下载 Intel DMG 后再进行 macOS 13 真机验证。
- 真机验证完成前应明确标注其待验证状态，不把构建成功当作兼容性测试通过。
