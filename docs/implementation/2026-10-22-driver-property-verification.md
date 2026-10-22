# 第三批属性修复验证记录

规范：`docs/plan/2026-10-22-driver-property-fixes.md`。用户已确认前两批人工测试无问题并授权第三批。前两批包及对应构建记录保留在 `.build/pre-third-batch-0.1.0/`。

## 阶段一：插件属性

- 固定上游文件不变，新增独立插件属性补丁：OwnedObjects 第二项索引为 1，两种 UID qualifier 大小判定为不等于。
- 明确补丁顺序、固定散列，参考审计先建立原样参考，再应用属性修复比较源码；未声明的差异仍失败。
- 独立进程 AddressSanitizer 合同通过 158 个用例，覆盖两种 Box 获取状态、对象列表容量 0 到 20 字节、Box/主/隐藏/未知 UID、空 qualifier、错误大小、输出容量及前后哨兵。
- 日志：`.build/third-batch-plugin-tests.log`。不访问运行中的 coreaudiod，不安装驱动。

## 阶段二与三

控制列表修复和集成交付待完成；真实音频验收待用户手动安装本批测试包后进行。
