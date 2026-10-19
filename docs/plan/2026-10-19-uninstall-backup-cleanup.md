Related discussion: [docs/discuss/2026-10-19-uninstall-backup-cleanup.md](../discuss/2026-10-19-uninstall-backup-cleanup.md)

# 安装临时回滚与卸载残留清理补充 PRD

日期：2026-10-19

状态：产品方向已确认，本实施规格待用户批准；当前禁止修改安装卸载行为或删除系统文件。

适用仓库：`tapsay-audio`。主程序正由另一会话开发，本规格不要求读取、修改、提交或回退主程序并行改动。

关联原规格：[声卡发行 PRD](2026-10-18-audio-driver-distribution.md)。批准后，本文只覆盖长期历史备份、安装临时回滚、历史残留清理和相应验收；其他边界继续有效。

## 1. 问题与已确认方案

用户已实测修复版卸载成功，但窗口仍显示历史 `backup.driver`。用户确认普通用户不需要长期备份，并能接受安装失败时下载历史版本；为减少失败重装，保留安装事务内的临时旧驱动，只要求正常结束后自动清理。

已确认规则：

1. 不再创建或长期保留历史 `backup.driver`。
2. 覆盖安装修改原驱动前，临时保留旧驱动，失败时自动恢复。
3. 安装成功或失败恢复成功后，清理本次临时材料；清理失败要如实报告。
4. 仅安装失败且恢复也失败时，保留唯一可用恢复来源。
5. 新版卸载自动清理可确认属于本产品的旧版历史，不增加备份复选框或管理界面。
6. 已卸载用户运行新版卸载工具即可清理旧历史，不再要求重装声卡。

用户已在当前机器实测一次正常卸载。2026-10-19 只读复查时，本项目历史事务目录已为空；这台机器不需要额外迁移或清理旧备份。该事实不能替代其他旧版本、异常目录和 Intel 环境测试。

## 2. 用户故事

1. 作为普通用户，我希望安装成功后不看到备份目录，也不管理备份文件。
2. 作为覆盖安装的用户，我希望新版本安装失败时，原有可用版本自动恢复。
3. 作为首装失败的用户，我希望只清理本次未完成的安装，不破坏其他内容。
4. 作为卸载用户，我希望一次确认完成设备移除和正常历史清理。
5. 作为已卸载用户，我希望再次运行新版工具时能清理旧版留下的事务材料，不必重装声卡。
6. 作为遇到异常的用户，我希望看到卸载、清理和待恢复材料各自的真实状态。
7. 作为维护者，我希望异常中断、恢复失败或清理部分失败时绝不误删唯一旧版。
8. 作为其他声卡用户，我希望 MiRemoteV、BlackHole 及其配置不受影响。

## 3. 现状基线与不可回退项

- 现有安装会额外复制长期 `backup.driver`，部署时又用原子移动保存一份临时 `.previous`。失败恢复使用 `.previous`，成功时只清理 `.previous`，所以长期副本残留。
- 现有卸载修复基线为 `cc8b6ee`：正确传递卸载命令和配置路径，解析结构化结果，检查目标设备 UID。用户已实测正常卸载。
- 当前安装状态 `Library/Application Support/TapSay Audio/install-state.json` 只由本项目安装事务和测试读写；本次不要求主程序读取新事务字段。
- 当前锁是 `Library/.TapSayAudio.lock`。工具以管理员身份运行时，父目录是该锁的创建和写入边界；用户级 `Library` 可在工具之外变化，不能作为事务材料的强制保护来源。因此保护检查针对固定父目录，不递归检查锁的每一级父目录。
- 历史备份可能来自其他架构的同一本产品。清理验证必须允许这种合法历史，不能套用“必须与当前主机和包版本一致”。

固定路径及命名：

| 对象 | 固定路径或格式 |
| --- | --- |
| 应用支持根目录 | `Library/Application Support/TapSay Audio` |
| 卸载状态 | 根目录下 `install-state.json` |
| 事务根目录 | 根目录下 `transactions` |
| 本次事务目录 | `transactions/<UUID>`，UUID 由 Foundation 标准大写格式产生 |
| 本次事务记录 | 事务目录内 `transaction.json` |
| 旧版状态副本 | 事务目录内 `previous-state.json` |
| 旧版长期副本 | 事务目录内 `backup.driver`，只允许旧版遗留，新版禁止创建 |
| HAL 临时旧驱动 | 固定 HAL 目录下 `.TapSayAudio-<UUID>.previous` |
| HAL 临时新载荷 | 固定 HAL 目录下 `.TapSayAudio-<UUID>.driver` |

新版安装不得再创建一个名为 `backup.driver` 的对象。旧版遗留的该文件只能由第 6 节的历史清理程序处理。

## 4. 实施前需要抽取的模块

为了便于低上下文开发者执行，将以下职责放入独立 Swift 文件；不要把大段状态判断继续塞入入口程序：

| 建议文件 | 只负责 |
| --- | --- |
| `Tools/Transaction/TransactionRecord.swift` | 事务 JSON、阶段枚举、写入及严格解码 |
| `Tools/Transaction/TransactionRecovery.swift` | 安装前检查异常事务、判断可恢复或受保护、执行实际恢复 |
| `Tools/Transaction/HistoricalCleanup.swift` | 枚举旧历史、验证身份、分类、删除允许的单个对象及生成清理结果 |
| 现有 `UninstallResult.swift` | 扩展卸载和历史清理的独立结果码；不承担目录枚举 |
| 现有 `UninstallDeviceCheck.swift` | 只负责实际设备 UID 查询，不假设“查询不到”是“不存在” |
| 现有 `main.swift` | 参数、命令编排、加锁及调用上述模块，不复制判定逻辑 |
| 现有 `Uninstaller.swift` | 显示确认、最终结果；不枚举或删除文件 |

这是建议文件划分，不是要求保留既有单体文件中所有旧函数。若拆分，两个架构构建脚本必须同步加入新文件。不要建立新进程、后台服务或第二套安装器。

## 5. 新版安装事务

### 5.1 入口检查和加锁

按顺序执行；任一步失败均停止且不能继续部署：

1. 读取并验证固定 product.json 中的本产品身份。保留当前身份精确比较。
2. 验证载荷、当前状态和固定路径；拒绝链接、身份不符或记录路径越界。
3. 验证主机操作系统版本和当前包架构，拒绝不兼容安装包；不因目标版本较低而拒绝降级。
4. 取得唯一事务锁。锁忙时停止，并说明另一个安装、卸载或清理正在进行。
5. 在持锁状态重新做一次安装预检，防止两次预检之间发生变化。
6. 枚举事务根目录以及 HAL 目录中本产品的临时对象，调用异常事务检查。发现 `recovery_required`、未完成的可恢复事务或证据矛盾时，停止新安装；提示需要处理的固定路径，不覆盖其唯一恢复材料。

在 `committed` 后仅遗留无效临时材料的状态，可先按第 5.4 节清理，再继续本次新安装；清理失败则停止新安装并报告 `cleanup_pending`，不能将新载荷部署到混乱状态上。

HAL 中的 `.TapSayAudio-*.previous` 可能属于另一个正在进行的进程或异常事务。只通过事务记录和锁判断，不凭“看起来旧”删除。

### 5.2 固定事务记录

在修改现有驱动前创建事务目录并原子写入 `transaction.json`。至少使用以下字段；字段名和值固定，不要自创缩写：

```json
{
  "schema_version": 1,
  "product": "TapSay Audio",
  "transaction_id": "FOUNDATION-UUID-UPPERCASE",
  "device_uid": "com.leafney.tapsay.audio.device.2ch",
  "bundle_identifier": "com.leafney.tapsay.audio.driver",
  "receipt": "com.leafney.tapsay.audio.pkg",
  "target": "/Library/Audio/Plug-Ins/HAL/TapSayAudio.driver",
  "state": "/Library/Application Support/TapSay Audio/install-state.json",
  "previous": "/Library/Audio/Plug-Ins/HAL/.TapSayAudio-UUID.previous",
  "staged": "/Library/Audio/Plug-Ins/HAL/.TapSayAudio-UUID.driver",
  "previous_state": "/Library/Application Support/TapSay Audio/transactions/UUID/previous-state.json",
  "had_target": true,
  "phase": "prepared",
  "terminal": "active",
  "terminal_result": "none",
  "cleanup": "none",
  "updated_at": "ISO8601"
}
```

字段含义：

- `phase` 只能是 `prepared`、`replacing`、`validating`、`committed`、`rolled_back`、`recovery_required`。
- `terminal` 为 `active`、`success`、`rolled_back`、`recovery_required`、`cleanup_pending`。
- 保留 `phase`，避免 `cleanup_pending` 覆盖“部署已提交”或“已回滚”的事实；`terminal_result` 为 `deployed`、`rolled_back` 或 `none`。
- `cleanup` 为 `none`、`pending`、`partial`、`complete`。
- `had_target=false` 时清空 `previous`、`previous_state`，不得伪造旧版路径。
- 若实际没有旧状态文件，`previous_state` 可为空字符串，安装失败时按“原先没有状态”恢复。

每次改变文件位置或阶段前，先将计划阶段原子写入记录，再执行文件移动；执行后重新读取并校验。不能用只存在于内存的 `previous` 位置决定删除。更新 `updated_at`，但不以文件时间代替阶段。

### 5.3 正常安装流程

1. 验证新载荷完全通过现有身份、版本、架构、路径和 Mach-O 检查。
2. 创建本次事务目录，写入 `prepared` 记录。记录必须在移动旧驱动之前存在。
3. 把旧状态（如果有）原子复制到 `previous-state.json`，回读验证。若旧状态存在、复制或读取失败，停止，旧安装不变。
4. 把 `phase` 原子更新为 `replacing`。若旧驱动存在，将旧驱动原子移动到固定 `.previous` 路径；将新载荷移动到固定正式目标。每一步后记录已完成的真实移动状态。
5. 把 `phase` 更新为 `validating`，执行既有正式目标身份检查、版本检查、状态写入和启动刷新。设备待核验、待重启和音频链路未验证的展示继续保留。
6. 完成安装状态写入后，原子写 `phase=committed, terminal=success, terminal_result=deployed`。此时新版本已是本次提交结果，后续临时清理失败不能自动回滚新版本。
7. 调用本次临时清理；清理成功后记录 `cleanup=complete`。若清理失败，保留已提交状态，记录 `terminal=cleanup_pending, cleanup=partial`、残留固定路径和原因，并在安装结果中显示残留，不得只打印一句“成功”。
8. 安装状态 JSON 不再记录已完成事务的 `backup.driver` 路径。`transaction` 可记录事务目录用于诊断；已完成清理后不要把它描述为用户可恢复的备份。

`activate()` 或刷新 CoreAudio 的退出码不是“设备已就绪”的证明，也不阻断部署提交。是否需重启必须继续按实际枚举状态报告。

### 5.4 清理范围和成功定义

安装成功、恢复成功后，只清理以下本次材料：

1. 该事务的 `.previous` 旧驱动（若存在且还归属本事务）。
2. 同一事务的 `.driver` 暂存新载荷（若存在）。
3. `previous-state.json`。
4. `transaction.json` 可在写入 `cleanup=complete` 后删除，或保留最小归档；若保留，必须不含可恢复旧驱动副本且不得让卸载或安装误认为仍在进行。推荐删除本次事务目录。

只有当前事务的固定对象可删；禁止遍历后删除任意同前缀文件。删除前重新验证：事务 UUID、目标 UID/Bundle ID 和路径。若对象已经不存在，记为已经清理，不报错。

“安装成功无备份残留”指：本次事务目录及本次 HAL 临时对象都没有残留。锁文件不属于备份，不清除。

### 5.5 失败与回滚

失败分支必须依据真实文件存在状态，不能只依据刚执行到哪一行：

| 失败时状态 | 必须动作 |
| --- | --- |
| 尚未移动旧驱动 | 删除本次 staged 和本次记录，旧驱动/状态不变 |
| 旧驱动已移动，但新驱动未部署 | 将 `.previous` 移回正式目标；恢复旧状态；成功后清理本次记录 |
| 新驱动已部署，验证/状态写入失败 | 删除本次新驱动，将 `.previous` 移回；恢复旧状态；成功后清理 |
| 首装失败，无旧驱动 | 删除本次新驱动、暂存和状态；不创建伪造备份 |
| 回滚本身失败 | 记录 `recovery_required`；保留唯一可用旧驱动、旧状态副本和记录；不得删除任何可能的恢复来源 |

注入失败测试必须分别覆盖：复制旧状态前、移动前、移动旧驱动后、部署后验证失败、状态写入失败、恢复移动失败、清理失败。测试注入开关只允许在 `--test-root` 隔离根目录使用；不允许在生产目标通过隐藏参数绕过确认。

回滚成功不等于系统收据也已恢复。系统收据由 PKG 流程管理；结果必须分别记录驱动/状态/收据的当前事实，不得宣称全部恢复。

### 5.6 异常中断与后续启动

进程或在任意步骤被终止后，下一次安装、卸载或清理先取得锁并读取事务记录：

1. `committed + cleanup_pending`：只重试清理该事务的本次临时对象；不重新部署、不回滚已提交版本。
2. `recovery_required`：只报告需要恢复固定路径和原因；不自动把可能不完整的旧版当新安装，也不覆盖它。
3. `rolled_back + cleanup_pending`：只重试清理已经无用的临时材料；不再次修改驱动。
4. `phase` 未提交但记录完整，且 `.previous` 和正式目标状态能唯一解释：只做明确需要的恢复，恢复后写 `recovery_required` 或 `rolled_back`，再清理。
5. 记录缺失、多个 previous 与正式目标同时存在、目标身份不明、路径在固定目录之外、链接或不一致时：停止并报告，不自动决定删除。

不要因为进程已退出、文件时间较旧或事务目录名符合 UUID 就自动删除 previous。证据不全时宁可保留。

## 6. 旧版历史残留清理

### 6.1 什么时候开始

只有当本次卸载已经确认：

- 驱动目标不存在；
- 本产品收据不存在；
- 本产品安装状态不存在；
- 设备 UID 实际查询为 `absent`；
- 不存在活动事务或 `recovery_required`；

才允许对历史材料执行清理。设备为 `present`、`unavailable`、`notChecked` 时，记录 `pendingDeviceRemoval`，不删除历史备份；用户重启后可再次打开工具重试。

这里的“驱动目标不存在”必须用固定路径存在性核实；“收据不存在”必须来自成功读取 `pkgutil --pkgs` 后的确认；“设备不存在”必须来自 CoreAudio 实际枚举，不能把查询失败当不存在。

### 6.2 旧版合法记录

对 `transactions/<UUID>/backup.driver` 逐个核验：

1. 目录位于固定的本项目事务根目录下一层。
2. 目录名是标准 UUID；无法解析时保留。
3. `backup.driver` 是普通目录，不能是链接；其 `Contents/Info.plist` 的 Bundle ID、可执行名、工厂 UUID、插件接口类型必须属于本产品。
4. 二进制含本产品名、设备 UID；版本/build 只要求可读，不要求等于当前工具；架构可为 arm64 或 x86_64，不能因此判定其他产品。
5. 若同事务内有 `previous-state.json`，其 JSON 目标必须是固定正式目标、Bundle ID 和设备 UID 必须匹配；不匹配则整体保留。
6. 若目录含 `transaction.json`，按第 5 节格式解码；`recovery_required`、未完成 active 状态或记录与文件矛盾时整体保留并报告，不删其中任何候选。
7. 除 `backup.driver`、`previous-state.json`、`transaction.json`、普通目录元数据外发现未知对象时，保留整目录并报告 `blocked`；不能递归删除未知内容。

旧版历史没有 `transaction.json` 时，不能凭“看起来像旧安装”自动删；只有在确认驱动、状态、收据和设备都消失，并且同目录结构/身份/状态均核验通过时，才可把 `backup.driver` 列为可清理候选。

### 6.3 可以删除什么

对每个合法候选，只删除经过核验的 `backup.driver`、`previous-state.json` 和允许的旧记录文件，然后尝试删除已空的专属事务目录。任何未知子对象、非空异常目录或身份不一致时保留该目录。

不得删除：

- 锁文件；
- 整个 `Application Support`；
- 整个 HAL 目录；
- 其他产品目录或同名但身份不符的备份；
- 任何 activity 或 recovery_required 材料；
- 路径经过链接、越界或无法确认的候选。

### 6.4 清理记录和重试

清理过程中逐步记录结构化结果，而不是只在最后根据文件数推测：

```json
{
  "schema_version": 1,
  "cleanup": "complete|partial|blocked|notNeeded|pendingDeviceRemoval",
  "removed_count": 0,
  "remaining_count": 0,
  "removed_paths": [],
  "remaining_paths": [],
  "reasons": []
}
```

路径只能输出规范化后的固定项目目录；不输出任意系统路径。若删除中途失败，保留已成功记录、剩余候选和原因，下一次重新核验后再处理；不能把本次已删除数量清零或把未删除项宣称为已清理。

清理完成的判定是不能存在本轮可清理且仍存在的合法 backup；未知/受保护项必须列入 remaining。因未知项完整保留目录、但已知 backup 已删除时，结果是 `partial` 或 `blocked`，不是 `complete`。

## 7. 卸载入口与界面

1. 确认页说明将清理本产品驱动、安装状态、收据以及可安全移除的历史安装材料；删除“恢复备份会保留”的固定文案。
2. 取消或授权拒绝：无文件变化。
3. 获得授权后加锁，先处理已存在事务。不能同时在安装事务进行时清理历史。
4. 正常删除本产品驱动、收据和状态，并重新查询目标设备 UID。
5. 设备确认消失后才处理历史候选；设备待重启或无法确认时不清理候选，显示待复查。
6. 事务工具必须接受“只剩历史”的场景，不能因驱动/状态/收据全不存在就提前返回为“当前未安装”。
7. 重复卸载、重复清理显示真实状态；没有历史和当前产品时显示未安装。
8. 历史清理失败不得重新安装驱动，也不得把已成功的声卡卸载标为整体失败。分别显示：声卡已卸载、历史清理部分未完成。

用户继续通过独立图形卸载 APP 操作，不需要运行 Python、终端命令或手动查找目录。已有 `/Library/Application Support/TapSay Audio/transactions` 当前为空时，工具不应显示无意义警告或创建新备份。

## 8. 结果协议固定契约

现有卸载结果升级为 `schemaVersion=2`；事务与界面必须由同一包构建，不能混用旧二进制和新的结果。保留旧的命令、目标 UID、驱动/收据/状态不存在的字段，并增加：

```json
{
  "schemaVersion": 2,
  "command": "uninstall",
  "deviceUID": "com.leafney.tapsay.audio.device.2ch",
  "status": "removed|notInstalled|restartRequired|unverified|failed",
  "driverAbsent": true,
  "receiptAbsent": true,
  "stateAbsent": true,
  "deviceStatus": "absent|present|unavailable|notChecked",
  "cleanupStatus": "notNeeded|complete|partial|blocked|pendingDeviceRemoval",
  "removedMaterialCount": 0,
  "remainingMaterialCount": 0,
  "remainingPaths": [],
  "message": "简体中文用户可读结果"
}
```

结果一致性要求：

- `status=removed/notInstalled` 必须有文件、收据、状态全部不存在且设备实际 `absent`；`notInstalled` 还要求没有可清理历史。
- `status=restartRequired` 只表示文件/收据/状态已清理，但设备 `present`；`cleanupStatus=pendingDeviceRemoval`。
- `status=unverified` 用于设备查询无法确认；不能表示全部清理完成。
- `cleanupStatus=complete` 必须 `remainingMaterialCount=0` 且没有受保护候选。
- `cleanupStatus=partial/blocked` 必须在 `remainingPaths` 或固定原因中明确说明，不能只显示“清理成功”。
- `status=failed` 用于驱动、收据或状态本身移除失败；此时可保留历史供后续恢复，不能显示卸载完成。

图形界面解码失败时显示“无法确认卸载结果”，不能把空输出、非 JSON、字段缺失或不一致响应当作成功。旧修复版 `schemaVersion=1` 的测试必须更新为迁移测试，不能同时接受两套协议后猜测状态。

界面标题和正文建议：

| 条件 | 标题 |
| --- | --- |
| `removed + complete/notNeeded` | 卸载完成 |
| `notInstalled + complete/notNeeded` | 当前未安装 |
| `restartRequired` | 卸载待重启生效 |
| `unverified` | 卸载生效状态待确认 |
| `failed` | 卸载未完成 |
| `removed + partial/blocked` | 声卡已卸载，部分历史材料未清理 |

所有错误/部分清理正文要告知用户保留固定路径、可重新运行新版卸载工具；不要指导用户用通配符或删除整个 Application Support。

## 9. 测试决策与可执行验收

不采用 TDD。新增测试聚焦事务状态、文件结果和协议边界，复用 `scripts/test-native-transaction.py` 的隔离根目录。测试必须断言真实文件内容和目录清单，不能只看退出码。

### 9.1 隔离安装测试

在临时根目录依次创建：

- 无旧版的首装；
- 有旧驱动和旧状态的覆盖安装；
- 同版重装；
- 目标版本较低但身份合法的降级；
- 前述各场景的成功、每个注入失败点及恢复失败。

每个成功场景断言：正式驱动和状态为本次结果；不存在 `backup.driver`；不存在本次 `.previous`、`.driver` 暂存；不存在未解释的事务目录或非空无用目录。

每个失败场景断言：原驱动二进制逐字节相同；原状态文件等于安装前字节；注入失败返回明确失败；可清理的临时项已清理；恢复失败保留唯一旧版、旧状态和固定记录。

### 9.2 协议与清理测试

至少覆盖：

1. 旧版 `backup.driver` 是合法本产品、身份正确；设备确认消失后清理成功。
2. 旧版备份为另一架构但仍属本产品，允许清理；架构不是身份错误。
3. 旧版目录含未知对象：保留未知目录，不删除整个目录，结果为 partial/blocked。
4. `recovery_required` 或 active 记录：不删除恢复来源；新安装被阻止。
5. 记录没有阶段、被截断、路径越界、链接、身份错误：原样保留。
6. 已卸载且只剩历史：工具进入清理路径，而不是直接报未安装。
7. 文件/收据/状态缺失但设备 `present/unavailable`：不清理历史，返回待重启/待确认，提示重启后重试。
8. 删除第一个候选后第二个失败：第一次的删除计数和剩余候选正确，下一次重试只处理剩余项。
9. 目录已空、无备份、重复卸载：稳定返回 notInstalled/notNeeded，不创建目录。
10. 安装/卸载/清理并发：锁忙一方停止，不出现第二套有效锁；锁文件保留不删除。
11. 清理失败但安装已提交：保持新版本，记录 `cleanup_pending`，不错误回滚。
12. 清理失败但安装已回滚：保持旧版本，记录 `cleanup_pending`，不再次迁移驱动。

### 9.3 结果协议测试

扩展 `Tests/UninstallResultTests.swift`，验证：

- schemaVersion 1 被拒绝；
- 空、纯文本、截断 JSON、未知命令/UID、字段缺失、互相矛盾的状态被拒绝；
- 文件都缺失但设备不是 absent 的状态不能显示完成；
- cleanup partial/blocked 必须保留剩余路径或原因；
- 成功展示和重启文案的映射精确；
- 设备状态轮询的 present/unavailable/瞬间 absent/稳定 absent/截止边界；
- 已卸载历史清理与重复操作的结果。

### 9.4 包与实机验收

每个架构编译新事务、卸载界面及新测试辅助程序。重建 PKG/DMG 后只读检查包内工具、配置、说明和源码材料一致；arm64 包内真实事务程序在临时根目录完成安装、卸载、历史清理和保护用例。

Intel 无真机时只记录构建和静态检查，不写成 Intel 真机通过。

实机运行前先另获用户明确授权；即使 PRD 批准，也不能把授权解释为立即删除当前系统历史。实机验收要求：

- 退出占用本设备的音频程序；
- 运行新版卸载入口，记录最终提示；
- 代理仅读核对 HAL 驱动、收据、设备 UID、事务根目录及相关固定临时对象；
- 若提示待重启，用户保存工作后手动重启，再进行只读复查；
- 真实测试前后都保留清单，不自行删除未知或待恢复材料。

用户不需要靠听感判断本需求；测试依据是结构化结果、文件核验、实际 UID 和受保护项清单。

## 10. 实施阶段

| 阶段 | 必做交付与退出条件 |
| --- | --- |
| 1 | 抽取记录和恢复模块；实现临时保留、提交、回滚、清理及异常恢复；隔离测试覆盖所有失败点 |
| 2 | 历史枚举、身份核验、候选分类、部分失败重试；保护 unknown/recovery_required/越界/链接对象 |
| 3 | 升级卸载结果协议和图形界面；迁移旧 schema 测试；验证待重启和部分清理文案 |
| 4 | 更新 README、包内说明、原规格和验收报告；构建两架构包；通过包内工具、源码归档和完整性检查 |

阶段 1-3 的自动验证通过后再做阶段 4，不得把未完成安装事务当成已完成清理。每个阶段完成后在当前仓库按 Conventional Commits 提交：type/scope 英文、描述使用简体中文，正文关联本文相对路径；提交后继续下一阶段，不逐文件等待确认。

若实现与本文冲突，先修改本文并等批准；不要以“低上下文模型自行决定”为由改变安全边界。

## 11. 范围外事项

不重写驱动、不修改 UID/名称/Bundle ID、默认 16 kHz、支持的 16/44.1/48 kHz、系统默认路由、主程序或首次引导。不新增常驻清理服务、自动下载历史版本、正式签名/公证或真实下载地址。不删除无法识别归属的材料，不承诺所有异常故障都能自动修复。

批准只允许按本文实现和隔离验证。真实系统删除、用户主程序替换、驱动安装或重启仍需在具体操作前获得必要授权；当前未执行任何删除。
