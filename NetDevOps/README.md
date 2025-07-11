# Syslog 批量配置工具

这是一个用于批量配置网络设备syslog的Python工具，支持图形界面操作。

## 功能特性

- 支持多种网络设备类型（华为、H3C、锐捷、思科、Juniper、Fortinet等）
- 图形化界面，操作简单
- 多线程并发处理，提高配置效率
- 实时显示配置进度和结果
- 支持结果导出
- 详细的日志记录

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 准备设备信息文件 `Sinfo.csv`，包含以下字段：
   - Type: 设备类型（huawei、h3c、ruijie、cisco等）
   - IP: 设备IP地址
   - ssh_type: SSH连接类型
   - User: 用户名
   - Passwd: 密码

2. 运行脚本：
   ```bash
   python 批量下发syslog配置.py
   ```

3. 在图形界面中：
   - 选择Sinfo.csv文件路径
   - 输入日志服务器地址
   - 设置最大线程数
   - 点击"运行配置"开始批量配置

## 支持的设备类型

- 华为设备 (huawei)
- H3C设备 (h3c)
- 锐捷设备 (ruijie)
- 思科设备 (cisco, cisco_ios, cisco_xe)
- Juniper设备 (juniper)
- Fortinet设备 (fortinet)

## 注意事项

- 确保网络连接正常
- 设备登录凭据正确
- 建议先用少量设备测试
- 配置过程中请勿关闭程序

## 日志文件

程序运行时会生成日志文件：`syslog_config_YYYYMMDD_HHMMSS.log` 