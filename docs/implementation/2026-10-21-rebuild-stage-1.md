# 重建阶段一：冻结与盘点

依据：`docs/plan/2026-10-21-reference-driver-cleanup.md`。当前分支 `feat/61021`，起点提交 `30a56954a94787d24792b37f4e27da9c3917d05b`。阶段一仅执行只读检查；没有写入系统 HAL，也没有删除恢复材料。

## 固定输入

| 输入 | 核验结果 |
| --- | --- |
| 无线麦固定提交 | `c9fabd1ef53e1a311dab4518a70693494631368b`，本地 Git 对象类型为 commit |
| `scripts/build-doubao-driver.sh` | SHA-256 `074db967329028e1e4dd3673f8ef5d6dbbfad150bce306980cf489f97c3875b0` |
| `scripts/release-variant.sh` | SHA-256 `db201e930e5efc9c6c51df422b33ee679d1fcbbbbf8955f3f3f81879d0ed4a99` |
| `third_party/blackhole/blackhole-device-usb.patch` | SHA-256 `51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f` |
| `scripts/verify-doubao-driver.sh` | SHA-256 `856c77cdaa87a667979f6327701ad7744854563afca1132c8dde3ce8c4eea47b` |
| BlackHole v0.7.1 源码归档 | `/private/tmp/blackhole-e2b22aaaba4e507a097131704bf96dabc004d9cf.tar.gz`，SHA-256 `5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0` |
| 归档内 `BlackHole.c` | SHA-256 `5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6` |
| 归档内 Xcode 工程 | SHA-256 `8346211852797b491245302d6ad5d3e6b855d3d07bf37e4d4d5b0e64656a6c88` |
| 归档内 LICENSE | SHA-256 `d5134ba41d942612bdf5ab79b32b3ddc2458f55e16437390bd81be8f2e0811e0`；仓库 `third_party/blackhole/LICENSE` 相同 |

归档目录名不是 Git 对象。上游 GitHub 固定提交页面可访问；归档与文件散列按 PRD 核验。许可文件声明源码 GPLv3，官方二进制、安装包和品牌另有权利声明；保留版权和完整许可，产品使用独立名称。参见 `third_party/blackhole/UPSTREAM.md` 与 `THIRD_PARTY_NOTICES.md`。

## 已装对照与本地材料

只读检查 `/Library/Audio/Plug-Ins/HAL/MiRemoteV2ch.driver`：Bundle ID `com.hd838a.MiRemoteV2ch`，版本 `0.7.1`、构建 `596`，工厂 UUID `4a91361d-19af-4ba0-a87a-0a6242ed6ae4`，Mach-O 仅 `arm64`，签名 Team ID `L3QHLDRPAY`，可执行文件 SHA-256 `f3c5f12368af4e80d534c40b6154f94ec09218fc4ba09afbd398103093d32be9`。这个散列与冻结参考的逐字节对应尚未证明，阶段二只比较属性，不覆盖已装对照。

旧 `dist/` 包：arm64 实验包 `c542d40c9bd0d5fab3e3124caced3749070eda5c2c6936b88da4ae2a59dcf8ab`；x86_64 实验包 `10875d2cc96c5b2a0f3cc12ffccac908a48d6ea646260ff911bea04bde9fe045`；校验文件 `5333ade65d4150f1035bce1afea87f598e31cf724c34d573333bc6822e1db878`。新包重建前保留。

`.build/experiments/evidence` 约 28 MB，含真实故障记录；`.build/experiments/preinstall-backup` 约 80 KB，含旧 TapSay 驱动恢复材料。这两处在真实验收完成前保留。`.build/driver`、`.build/native` 及实验构建缓存可在新实现通过后清理。未清理任何系统文件。

## 旧文件去向

逐文件清单见 `2026-10-21-rebuild-stage-1-inventory.md`。分类含新实现、现行数据与许可、旧历史待删。阶段五之前不删除。

## 验证与门槛

- 已执行：`git rev-parse HEAD`、`git ls-files`、`git status --short`、`git cat-file -t`、固定提交 `git show | shasum -a 256`、`tar -xOf | shasum -a 256`、已装驱动 `plutil`/`lipo`/`codesign`/`shasum`、旧包 `shasum`。退出码均为 0。
- 阶段提交前执行 `git diff --check` 并核对逐文件清单覆盖 `git ls-files`。
- 未解决：已装 MiRemoteV 与固定参考的二进制同源性、真实运行格式和音频链路需后续阶段验证。下一阶段先在隔离目录构建原样参考。
