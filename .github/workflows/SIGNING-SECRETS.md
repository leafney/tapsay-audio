# TapSay Audio 签名与公证 Secrets 配置指南

本文用于配置 [package-arch.yml](package-arch.yml) 中的 Developer ID 签名与 Apple 公证流程，供后续正式 Tag 发布使用。

当前手动构建固定使用 ad hoc 签名，不读取本文中的 Secrets。只有 Tag 发布工作流固定使用 `developer-id` 模式，并会一次性要求以下 8 个 Secrets。缺少任意一项时，工作流会在 `Validate Developer ID secrets` 步骤直接失败，不会降级发布未认证包。

## 1. 所需 Secrets 总览

| Secret 名称 | 内容 | 格式 |
| --- | --- | --- |
| `DEVELOPER_ID_APPLICATION_P12_BASE64` | Developer ID Application 证书与私钥导出的 `.p12` 文件，经 Base64 编码 | 单行 Base64 文本 |
| `DEVELOPER_ID_APPLICATION_P12_PASSWORD` | 导出上述 `.p12` 时设置的密码 | 普通文本 |
| `DEVELOPER_ID_INSTALLER_P12_BASE64` | Developer ID Installer 证书与私钥导出的 `.p12` 文件，经 Base64 编码 | 单行 Base64 文本 |
| `DEVELOPER_ID_INSTALLER_P12_PASSWORD` | 导出上述 `.p12` 时设置的密码 | 普通文本 |
| `APPLE_TEAM_ID` | Apple Developer Program 团队的 Team ID | 10 位大写字母或数字 |
| `APP_STORE_CONNECT_ISSUER_ID` | App Store Connect 团队 API Key 的 Issuer ID | UUID 格式 |
| `APP_STORE_CONNECT_KEY_ID` | App Store Connect 团队 API Key 的 Key ID | 通常为 10 位大写字母或数字 |
| `APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64` | App Store Connect 团队 API Key 下载的 `.p8` 私钥文件，经 Base64 编码 | 单行 Base64 文本 |

两类凭据用途不同：

- Developer ID Application 证书用于签名驱动、卸载 App 和最终 DMG。
- Developer ID Installer 证书用于签名 DMG 内部的 PKG。
- App Store Connect API Key 用于向 Apple 公证服务提交 DMG。
- Team ID、Issuer ID 和 Key ID 都是标识信息，不能混用。

## 2. 开始前的账号与权限条件

正式签名和公证需要付费的 Apple Developer Program 会员资格。

操作账号需要满足：

- 已接受 Apple Developer Program 当前有效的协议。
- 可以由 Account Holder 创建 Developer ID Application 和 Developer ID Installer 证书。
- 可以访问 App Store Connect 中的“用户和访问权限”。
- 首次使用 App Store Connect API 时，需要 Account Holder 申请 API 访问权限。
- 团队 API Key 需要 Account Holder 或 Admin 创建。

建议为本项目准备独立、可长期维护的团队账号权限。不要把 Apple ID 密码、双重认证验证码或 App Store Connect 登录密码填写到 GitHub Secrets。

## 3. 获取 `APPLE_TEAM_ID`

Team ID 是 Apple Developer Program 会员资格的团队标识。

1. 登录 <https://developer.apple.com/account>。
2. 打开左侧的“Membership details”（会员资格详细信息）。
3. 在团队名称附近找到“Team ID”。
4. 复制完整的 10 位字符串。

注意：

- 工作流要求 Team ID 严格匹配 `^[A-Z0-9]{10}$`。
- Team ID 不是 App Store Connect 的 Issuer ID。
- 导出的 Developer ID 证书身份名称末尾必须带有与 Team ID 一致的括号，例如身份名称最后的括号内容应为该 10 位 Team ID。

Apple 官方说明：<https://developer.apple.com/help/glossary/team-id/>

## 4. 创建 Developer ID 证书

需要分别创建两张证书：

| 证书类型 | 用途 | 对应 Secrets |
| --- | --- | --- |
| Developer ID Application | 签名驱动、卸载 App 和 DMG | `DEVELOPER_ID_APPLICATION_*` |
| Developer ID Installer | 签名 PKG 安装包 | `DEVELOPER_ID_INSTALLER_*` |

建议两张证书分别创建 CSR、分别导出 `.p12`，不要让两类证书共用同一个私钥文件。

### 4.1 创建证书签名请求 CSR

证书必须在生成 CSR 的同一台 Mac 上导出，否则无法取得对应私钥。

1. 打开“钥匙串访问”（Keychain Access）。
2. 选择“钥匙串访问” → “证书助理” → “从证书颁发机构请求证书”。
3. 输入 Apple 账号关联的邮箱。
4. “常用名称”填写容易识别的名称，例如 `TapSay Audio Developer ID Application`。
5. “CA 电子邮件地址”留空。
6. 选择“存储到磁盘”。
7. 保存 `.certSigningRequest` 文件。
8. 为 Developer ID Installer 再创建一份单独的 CSR，并使用不同的常用名称。

Apple 官方 CSR 说明：<https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/>

### 4.2 申请 Developer ID Application 证书

1. 登录 <https://developer.apple.com/account>。
2. 打开“Certificates, Identifiers & Profiles”。
3. 在左侧选择“Certificates”。
4. 点击左上角的添加按钮 `+`。
5. 在“Software”下选择“Developer ID”，点击“Continue”。
6. 选择“Developer ID Application”。
7. 上传刚才创建的 Application 对应 `.certSigningRequest` 文件。
8. 点击“Continue”。
9. 下载生成的 `.cer` 文件。
10. 双击 `.cer` 文件，将它导入当前 Mac 的登录钥匙串。

Apple 官方说明：<https://developer.apple.com/help/account/certificates/create-developer-id-certificates/>

### 4.3 申请 Developer ID Installer 证书

重复上一节流程，但选择：

```text
Developer ID Installer
```

上传 Installer 对应的 `.certSigningRequest`，下载并双击安装生成的 `.cer` 文件。

### 4.4 检查证书是否包含私钥

1. 打开“钥匙串访问”。
2. 左侧选择“登录”钥匙串。
3. 选择“我的证书”类别。
4. 分别找到 Developer ID Application 和 Developer ID Installer。
5. 展开证书后应能看到对应的私钥。
6. 核对证书名称末尾括号内的 Team ID 与 `APPLE_TEAM_ID` 一致。

如果只有证书、没有私钥，该证书不能导出可用的 `.p12`，也不能用于 CI 签名。此时应回到生成 CSR 的 Mac 上操作，或重新创建证书。

### 4.5 检查证书签发机构

Apple 当前要求使用最新的 Developer ID G2 证书。G2 Developer ID 证书有效期为一年，需要按年续签。

在“钥匙串访问”中查看证书的“签发者名称”，展开“Organizational Unit”：

- 显示 G2 时，表示使用的是当前 Developer ID Certification Authority。
- 显示旧 Apple Certification Authority 时，需要按 Apple 的迁移说明重新签发证书。

Apple 官方说明：

- <https://developer.apple.com/help/account/certificates/replace-developer-id-certificates>
- <https://developer.apple.com/help/account/certificates/create-developer-id-certificates/>

## 5. 导出 `.p12` 凭据文件

需要导出两次：

1. Developer ID Application 证书及其私钥。
2. Developer ID Installer 证书及其私钥。

操作步骤：

1. 打开“钥匙串访问”。
2. 左侧选择“登录”，类别选择“我的证书”。
3. 展开目标 Developer ID 证书，同时选中证书和下面的私钥。
4. 右键选择“导出”。
5. 文件格式选择“个人信息交换（.p12）”。
6. 输入文件名并保存到本地安全目录。
7. 设置一个独立、随机且足够长的导出密码。
8. 允许系统读取该私钥时，输入当前 Mac 的登录密码。

建议文件名：

```text
TapSay-DeveloperID-Application.p12
TapSay-DeveloperID-Installer.p12
```

导出密码将分别填写到：

```text
DEVELOPER_ID_APPLICATION_P12_PASSWORD
DEVELOPER_ID_INSTALLER_P12_PASSWORD
```

注意事项：

- `.p12` 密码不是 Apple ID 密码。
- 两个 `.p12` 可以使用不同密码。
- 密码会原样传给 `security import -P`，不要添加额外的引号或换行。
- `.p12` 包含私钥，必须按私密文件处理。
- 不要将 `.p12`、密码或 Base64 内容提交到仓库、Issue、PR 或聊天中。

Apple 官方的 Apple 平台证书导出说明：<https://developer.apple.com/cn/documentation/xcode/sharing-your-teams-signing-certificates>

## 6. 本地确认两张 Developer ID 身份

完成证书导入后，在终端执行：

```bash
security find-identity -v -p codesigning
```

输出中应同时包含：

```text
Developer ID Application: ... (<TEAM_ID>)
Developer ID Installer: ... (<TEAM_ID>)
```

`<TEAM_ID>` 必须与 GitHub Secret `APPLE_TEAM_ID` 完全一致。

当前工作流会读取该命令的输出，并自动选择：

- 名称以 `Developer ID Application:` 开头且 Team ID 匹配的身份。
- 名称以 `Developer ID Installer:` 开头且 Team ID 匹配的身份。

如果这里看不到完整身份，工作流导入后也会在 `Import Developer ID credentials` 步骤失败。

## 7. 开通 App Store Connect API

公证使用 App Store Connect API Key，不使用 Apple ID 密码或 App 专用密码。

### 7.1 首次申请 API 访问权限

1. 登录 <https://appstoreconnect.apple.com>。
2. 打开“用户和访问权限”（Users and Access）。
3. 选择“整合”（Integrations）。
4. 左侧选择“App Store Connect API”。
5. 如果页面显示“Request Access”，由 Account Holder 阅读并接受条款后提交。
6. 等待 Apple 审核通过。

API 权限被批准前，无法创建后续团队 API Key。

### 7.2 创建团队 API Key

必须创建“Team Keys”，不要创建 Individual Key。Apple 明确说明 Individual Key 不能用于 `notaryTool`。

1. 在“用户和访问权限” → “整合” → “App Store Connect API”中打开“Team Keys”。
2. 点击“Generate API Key”或添加按钮 `+`。
3. 输入便于识别的名称，例如 `TapSay Audio GitHub Actions`。
4. 为 Key 选择角色。
5. 点击“Generate”。
6. 页面会显示 Key ID 和 Issuer ID。
7. 下载 `.p8` 私钥文件。

角色建议：

- 优先选择 `Developer`，满足公证用途并限制其他 App Store Connect 管理权限。
- 如果团队策略或 Apple 返回权限错误，可由 Account Holder 或 Admin 改用 `Admin` 角色。
- 不要为日常公证流程长期使用不必要的 Account Holder 个人凭据。

Apple 官方说明：

- <https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api>
- <https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api>

## 8. 获取 Issuer ID、Key ID 和 `.p8`

### 8.1 `APP_STORE_CONNECT_ISSUER_ID`

在“Team Keys”页面上方找到“Issuer ID”。

格式通常类似 UUID，团队内所有 Team Key 共用同一个 Issuer ID。

复制完整值到：

```text
APP_STORE_CONNECT_ISSUER_ID
```

Issuer ID 不是 Team ID。

### 8.2 `APP_STORE_CONNECT_KEY_ID`

在刚创建的 API Key 所在行找到“Key ID”。

复制完整值到：

```text
APP_STORE_CONNECT_KEY_ID
```

下载的私钥文件名通常是：

```text
AuthKey_<KEY_ID>.p8
```

文件名中的 Key ID 必须与 Secret `APP_STORE_CONNECT_KEY_ID` 一致。

### 8.3 `APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64`

`.p8` 私钥只允许下载一次，Apple 不保留可再次下载的副本。

1. 将下载的 `AuthKey_<KEY_ID>.p8` 保存到安全目录。
2. 不要修改文件内容。
3. 不要提交到 Git。
4. 将该文件的 Base64 内容填写到 `APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64`。

如果 `.p8` 丢失，只能回到 App Store Connect 撤销旧 Key，并重新创建和下载新 Key。重新创建后还要同步更新 `APP_STORE_CONNECT_KEY_ID` 和 `APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64`。

## 9. 将文件转换为 Base64

GitHub Secrets 中应保存 Base64 文本本身，不要保存以下包装：

- 不要添加 `NAME=value`。
- 不要添加 Markdown 代码块标记。
- 不要保留 `data:` 前缀。
- 不要添加外层单引号或双引号。
- 不要上传原始 `.p12` 或 `.p8` 文件。

### 9.1 macOS 终端生成并复制

Developer ID Application：

```bash
base64 -i /secure/path/TapSay-DeveloperID-Application.p12 | pbcopy
```

Developer ID Installer：

```bash
base64 -i /secure/path/TapSay-DeveloperID-Installer.p12 | pbcopy
```

App Store Connect API Key：

```bash
base64 -i /secure/path/AuthKey_<KEY_ID>.p8 | pbcopy
```

每次执行后，将剪贴板内容直接粘贴到对应 GitHub Secret。不要把输出粘贴到 Issue、PR、日志或聊天。

### 9.2 生成文件后清理

完成 Secret 配置并保存到团队的密码管理器后，应删除临时导出的 `.p12` 和 `.p8`。后续证书续期时再生成新的安全副本。

## 10. 在 GitHub 中创建 Repository Secrets

当前 [release.yml](release.yml) 通过 `secrets: inherit` 将 Secrets 传给单架构构建工作流，因此使用仓库级 Secrets 即可。

1. 打开 GitHub 仓库主页。
2. 进入“Settings”。
3. 打开“Secrets and variables” → “Actions”。
4. 选择“Secrets”标签页。
5. 点击“New repository secret”。
6. 输入本文表格中的 Secret 名称。
7. 粘贴对应值。
8. 点击“Add secret”。
9. 按相同方式创建全部 8 个 Secrets。

Secret 名称建议与文档完全一致。GitHub 的 Secret 名称不区分大小写，但工作流会按当前名称引用。

不要在本仓库的 `-secrets.yml` 文件中写入这些值。任何包含明文的文件都不应提交到 Git。

GitHub 官方说明：<https://docs.github.com/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets>

## 11. 当前工作流如何使用这些参数

Tag 发布时，工作流按以下顺序使用 Secrets：

| 阶段 | 使用的 Secrets | 作用 |
| --- | --- | --- |
| 完整性校验 | 全部 8 项 | 任一项为空时立即失败 |
| 导入证书 | 两个 P12、两个 P12 密码 | 创建临时 Keychain 并导入签名身份 |
| 识别签名身份 | `APPLE_TEAM_ID` | 选择 Team ID 匹配的 Application 与 Installer 身份 |
| 准备公证密钥 | Key ID、`.p8` Base64 | 写入 Runner 临时目录 |
| 签名代码 | Developer ID Application | 签名驱动、事务工具和卸载 App |
| 签名安装包 | Developer ID Installer | 使用 `productsign` 签名 PKG |
| 签名 DMG | Developer ID Application | 对最终 DMG 签名 |
| Apple 公证 | Team ID、Issuer ID、Key ID、`.p8` | 使用 `notarytool` 提交公证并等待结果 |
| 完成发布 | 全部相关凭据 | `staple`、`stapler validate`、`spctl` 和 `codesign` 复验 |

Runner 会在构建结束后删除临时 Keychain、P12 和 `.p8` 文件。

## 12. 配置完成后的验证方式

### 12.1 先做不发布包的本地验证

可在有证书和 API Key 的 Mac 上检查：

```bash
security find-identity -v -p codesigning
```

应同时看到 Application 和 Installer 身份，且 Team ID 与 GitHub Secret 一致。

### 12.2 检查 GitHub Secrets 名称

当前工作流要求以下名称全部存在：

```text
DEVELOPER_ID_APPLICATION_P12_BASE64
DEVELOPER_ID_APPLICATION_P12_PASSWORD
DEVELOPER_ID_INSTALLER_P12_BASE64
DEVELOPER_ID_INSTALLER_P12_PASSWORD
APPLE_TEAM_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64
```

### 12.3 触发正式 Tag 发布

当前手动 `Build Internal Artifacts` 工作流固定使用 ad hoc 签名，不会读取 Developer ID Secrets，因此不能用来验证认证流程。

完成 Secrets 后，按现有发布规则推送严格的 `vX.Y.Z` Tag，例如：

```text
v0.2.0
```

发布前应确认：

- `config/product.json` 的上游分发审查状态已满足正式发布要求。
- 代码已经提交。
- Tag 指向预期提交。
- 两个架构所需 Secrets 均已在仓库级配置。
- 当前 Apple 证书未过期或被撤销。

工作流会先完成两个架构的签名和公证，再执行最终 DMG 复验并创建 Pre-release。任一架构失败时不会创建 Release。

## 13. 常见错误与排查

### 13.1 `Developer ID signing requires all configured secrets`

原因：8 个 Secrets 中至少一个为空。

处理：

- 检查 Secret 名称是否拼写错误。
- 检查是否误将 Secret 建在无法被当前工作流访问的环境或组织范围。
- 检查值是否为空或只包含空白。

### 13.2 `A required Developer ID identity was not imported`

常见原因：

- `.p12` 不包含私钥。
- `.p12` 密码错误。
- 证书属于另一个 Team ID。
- 证书已过期或被撤销。
- Application 与 Installer 使用了错误类型的 `.p12`。

处理：

- 在“钥匙串访问”的“我的证书”中确认证书能够展开显示私钥。
- 重新从同一台 Mac 导出 `.p12`。
- 核对证书身份名称末尾的 Team ID。
- 确认 Application 和 Installer 没有互换。

### 13.3 `productsign` 失败

原因通常与 Installer 证书有关。

处理：

- 确认导入的是 `Developer ID Installer`。
- 确认证书未过期、未撤销，并且属于 `APPLE_TEAM_ID`。
- 重新导出 Installer `.p12` 并更新两个 Installer Secrets。

### 13.4 `notarytool` 返回认证失败

检查以下映射是否一致：

```text
Issuer ID  → APP_STORE_CONNECT_ISSUER_ID
Key ID     → APP_STORE_CONNECT_KEY_ID
.p8 文件   → APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64
```

同时确认：

- 使用的是 Team Key，不是 Individual Key。
- App Store Connect API 访问权限已获批准。
- Key 未被撤销。
- `.p8` 的 Base64 没有混入其他文本。
- Key 的角色具备公证所需权限。

### 13.5 公证通过但用户端仍提示未认证

检查：

- DMG 是否已经执行 `stapler staple`。
- 是否使用 `stapler validate` 验证公证票据。
- 内部 PKG 是否使用 Developer ID Installer 签名。
- 驱动、卸载 App 和事务工具是否都使用 Developer ID Application 签名。
- 最终 DMG 是否在上传前被重新修改；任何修改都会破坏已有签名和公证票据。

## 14. 更新、撤销与轮换

### 14.1 Team ID 变化

Team ID 通常长期稳定。只有更换 Apple Developer Program 团队时才需要修改。

### 14.2 Developer ID 证书续期

Developer ID G2 证书通常有效期为一年。证书即将过期、撤销或更换私钥时：

1. 在 Apple Developer 账号中创建新证书。
2. 导入包含私钥的 `.cer` 对应身份。
3. 重新导出 `.p12`。
4. 更新对应 P12 Base64 和密码 Secrets。
5. 确认旧证书不再被工作流选中。

### 14.3 App Store Connect API Key 轮换

`.p8` 丢失、泄露或需要周期轮换时：

1. 在 App Store Connect 中撤销旧的 Team Key。
2. 创建新的 Team Key。
3. 保存新的 Key ID 和 Issuer ID。
4. 下载新的 `.p8`。
5. 更新 Key ID 和 `.p8` Base64 Secrets。

同一团队的 Issuer ID 通常不变，但更换团队、撤销权限或 Apple 调整配置时仍应重新核对。

## 15. 安全规则

- 不提交 `.p12`、`.p8`、证书密码或 Base64 内容。
- 不把秘密粘贴到 Issue、PR、构建日志、聊天或截图。
- 不在本地脚本中硬编码 Secret。
- 只给工作流必要的仓库权限。
- 定期检查证书有效期和 App Store Connect API Key 状态。
- 发现私钥泄露时立即撤销证书或 API Key，再重新创建。

## 16. 操作顺序清单

正式配置时按以下顺序执行：

1. 确认付费 Apple Developer Program 会员资格和 Account Holder/Admin 权限。
2. 获取 `APPLE_TEAM_ID`。
3. 分别为 Application 和 Installer 创建 CSR。
4. 在 Apple Developer 账号中创建两张 Developer ID 证书。
5. 将两张 `.cer` 导入生成 CSR 的 Mac。
6. 确认两张证书都带私钥，并来自当前 Developer ID G2 CA。
7. 分别导出 Application 和 Installer 的 `.p12`，设置独立密码。
8. 将三个二进制凭据文件转换为 Base64。
9. 首次开通 App Store Connect API 访问。
10. 创建 Team API Key，记录 Issuer ID、Key ID 并下载 `.p8`。
11. 在 GitHub 仓库创建全部 8 个 Secrets。
12. 本地核对签名身份和 Team ID。
13. 使用正式严格格式 Tag 触发认证发布。
14. 下载最终 DMG，核对签名、公证票据、安装和卸载流程。

## 17. Apple 官方参考

- Developer ID 证书创建：<https://developer.apple.com/help/account/certificates/create-developer-id-certificates/>
- CSR 创建：<https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request/>
- Developer ID 证书迁移与 G2 CA：<https://developer.apple.com/help/account/certificates/replace-developer-id-certificates>
- Team ID：<https://developer.apple.com/help/glossary/team-id/>
- App Store Connect API 开通：<https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api>
- App Store Connect API Key：<https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api>
- API JWT 与 Key ID/Issuer ID：<https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests>
- `notarytool` 迁移与 API Key 参数：<https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool>
- macOS 公证说明：<https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution>
