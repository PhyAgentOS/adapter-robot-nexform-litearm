# 标定文件

本目录用于存放现场标定结果（例如手眼外参、TCP 偏移），格式以实际使用方为准，
建议每个文件附带来源、日期、单位和校验值。

当前仓库**不包含**任何标定结果：

- LiteGrip 使用 SDK 打包的 factory calibration
  （`litegrip-python/src/litegrip/factory_calibration.json`），本仓不复制、
  不覆盖用户目录下的标定文件。
- VR `t_ee` 已实测（`[-0.0071,-0.0239,0.140]` m，法兰系，见 `docs/validation.md`
  §t_ee 记录）；夹爪堵转阈值已实测，`payload` 仅为 CAD 估算（未动态辨识、未写入固件），
  见 `docs/validation.md` §夹爪 payload 与堵转阈值记录。
- 手眼标定由独立工程生成后再归档到这里。

不要提交设备序列号、内网地址、个人路径或任何密钥。
