# VerMan 数据目录

这个目录用于存储VerMan应用程序的数据文件。

## 文件说明

### vip_records.json
- VIP激活码记录文件
- 记录所有生成的激活码及其使用状态
- 包含激活码、用户邮箱、生成时间、使用时间等信息

### 使用方式

该目录下的文件由VerMan应用程序自动管理：
- 激活码生成工具会自动创建和更新 `vip_records.json`
- 程序运行时会读取这些文件
- 请不要手动修改文件内容

## 安全提示

- `vip_records.json` 包含敏感的激活码信息
- 请妥善保管此目录
- 不要将此目录分享给他人
- 建议定期备份重要的激活码记录

## 数据格式示例

```json
[
  {
    "activation_code": "VMN-VIP-A4B8-C9D2",
    "user_email": "user@example.com",
    "plan_type": "vip",
    "generated_at": "2024-01-15T10:30:25",
    "status": "unused",
    "notes": "微信订单202401151030",
    "machine_id": null,
    "activated_at": null,
    "activated_by": null
  }
]
```

## 备份建议

建议定期备份 `vip_records.json` 文件，以防止意外丢失激活码记录。