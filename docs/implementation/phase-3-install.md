# 阶段 3：安装、覆盖、回滚与卸载事务

日期：2026-10-19

交付：`scripts/install.py`、`scripts/uninstall.py`、`scripts/test-install-transaction.py`。

实现规则：安装工具先验证 Bundle ID、版本、载荷结构和架构，再复制到临时目录；覆盖前备份当前驱动；部署异常删除新载荷并恢复备份；锁目录阻止并发安装。默认没有系统目标路径，测试使用临时目录。卸载必须提供 `--yes`，且状态中的目标路径必须精确匹配，避免清理相似目录。

验证：`python3 scripts/test-install-transaction.py` 通过，覆盖错误架构拒绝且原文件不变，部署故障注入后原文件恢复，未确认卸载拒绝，确认卸载只删除目标。

未覆盖：PKG 图形授权、真实 `/Library/Audio/Plug-Ins/HAL` 安装、CoreAudio 重枚举、系统重启和真实音频链路。下一阶段包装器会调用这些受限脚本；正式系统操作仍需 Apple Silicon 真机人工验收。
