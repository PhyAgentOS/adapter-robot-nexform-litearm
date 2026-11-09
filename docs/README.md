本目录记录 LiteArm 接入包的安装、参数、关节、硬件、验证证据与 MDH 推导，供接入开发者和验收人员查阅。

# 文档索引

## 开始

- [安装与自检](setup.md)：环境准备、SDK 安装、无硬件自检。
- [参数总表](parameters.md)：软件版本、机械臂、固件、夹爪、VR 参数（单一真源）。
- [关节参数表](joint_table.md)：关节名、限位、零位、正方向与 URDF/MJCF 差异。

## 参考

- [硬件与接线](hardware.md)：通信、供电、急停与现场接线。
- [TCP/JSON 桥](bridge.md)：`forge_bridge` 协议、线程模型、参数与限制。
- [MDH 推导](mdh.md)：由 URDF 反推 MDH 及 FK 对拍结果。
- [厂商手册归档](vendor/litearm-docs/README.md)：产品手册与软件开发手册。
- [资产来源与校验](../assets/README.md)：URDF/MJCF/GLB 来源、转换记录与 SHA-256 台账。

## 验收

- [验收清单与证据](validation.md)：接入手册 §12 的 15 项验收及证据路径。
- [验收报告](acceptance_report.md)：按 `robot-acceptance-validation` 模板生成的 15 项结论
  （路径结构 + 逐项 ✓/✗/○/- + 已执行验证）。
