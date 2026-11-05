# 标定文件

本目录用于存放现场标定结果（例如手眼外参、TCP 偏移），格式以实际使用方为准，
建议每个文件附带来源、日期、单位和校验值。

当前仓库**不包含**任何标定结果：

- LiteGrip 使用 SDK 打包的 factory calibration
  （`litegrip-python/src/litegrip/factory_calibration.json`），本仓不复制、
  不覆盖用户目录下的标定文件。
- 夹爪 `tcp_offset` / `payload` 与 VR `t_ee` 尚未实测，见 `docs/validation.md`
  阶段 3。
- 手眼标定由独立工程生成后再归档到这里。

不要提交设备序列号、内网地址、个人路径或任何密钥。
