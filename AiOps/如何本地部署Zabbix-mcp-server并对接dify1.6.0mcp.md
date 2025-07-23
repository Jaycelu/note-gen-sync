# 如何本地部署 Zabbix MCP Server 并对接dify1.6mcp服务

以下是基于mcp.so上zabbix官方的mcp-server，结合我的实际本地部署实践，总结了本地部署 Zabbix MCP Server 并对接最新dify1.6.0mcp服务的清晰步骤。这些步骤涵盖了环境准备、依赖安装、配置、启动，以及将服务设置为 HTTP 协议并实现开机自启动的方法。

---

## 前提条件

根据zabbix官方mcp-server代码中 README 建议要求，以下是部署 Zabbix MCP Server 的必要条件：

* **操作系统**：Linux（如 Ubuntu、CentOS）或其他支持 Python 的系统。
* **Python 版本**：3.10 或更高版本。
* **包管理器**：推荐使用 `uv`（更快），但 `pip` 也可以。
* **Zabbix 服务器**：确保 Zabbix 服务器 API 已启用，且你有访问权限（URL、Token 或用户名/密码）。
* **网络**：确保服务器网络通畅，能访问 PyPI 或国内镜像源。![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/be5788b1-cb5b-4e68-9a46-2f0b8ef9c910.png)

---

## 部署步骤

以下是本地部署 Zabbix MCP Server 的详细步骤，结合了排错过程中解决的关键问题。

### 1. 克隆代码仓库

克隆 Zabbix MCP Server 的代码到本地：

```bash
git clone https://github.com/mpeirone/zabbix-mcp-server.git
cd zabbix-mcp-server
```

**排错提示**：

* 确保 `git` 已安装。如果网络问题导致克隆失败，可以尝试使用代理或国内镜像（如 Gitee）。

### 2. 安装依赖

使用 `uv` 安装依赖（推荐），或使用 `pip`：

```bash
# 使用 uv
uv sync
# 或者使用 pip
pip install -r requirements.txt
```

**排错经验**：

* 如果遇到 `pip` 下载超时（如 `incomplete-download` 错误），切换到国内镜像源：
  ```bash
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```
* 确保虚拟环境已激活（如果使用虚拟环境）：
  ```bash
  source venv/bin/activate
  ```
* 检查是否缺少 `fastmcp` 或 `zabbix_utils` 模块。如果这些模块不是 PyPI 包，确认 `src/` 目录下有对应源码文件（如 `fastmcp.py`）。

### 3. 配置环境变量

复制环境变量模板并编辑：

```bash
cp config/.env.example .env
```

用文本编辑器（如 `nano` 或 `vim`）编辑 `.env` 文件，填写以下必填项：

```
ZABBIX_URL=http://<你的 Zabbix 服务器地址>/api_jsonrpc.php
# 选择一种认证方式：
# 方法 1：使用 API Token（推荐）
ZABBIX_TOKEN=<你的 Zabbix API Token>
# 方法 2：使用用户名和密码
ZABBIX_USER=<你的 Zabbix 用户名>
ZABBIX_PASSWORD=<你的密码>
# 可选：设置只读模式
READ_ONLY=false
```

**排错提示**：

* 确保 `ZABBIX_URL` 格式正确，包含 `/api_jsonrpc.php`。
* 如果未设置 `ZABBIX_TOKEN` 或 `ZABBIX_USER` 和 `ZABBIX_PASSWORD`，启动时会报错：
  ```
  Missing required environment variables: ZABBIX_URL
  ```
* 使用 `ZABBIX_TOKEN` 更安全，推荐优先配置。

### 4. 测试安装

运行测试脚本以验证环境和依赖是否正确：

```bash
uv run python scripts/test_server.py
```

**预期输出**：

```
🎉 All 5 tests passed!
✅ The Zabbix MCP Server is ready to use
```

**排错经验**：

* 如果测试失败，检查日志中是否有模块缺失（如 `ModuleNotFoundError: No module named 'fastmcp'`）。可能需要确认 `src/` 目录是否包含所需模块，或手动安装：
  ```bash
  pip install python-dotenv
  ```
* 如果遇到类型检查报错（如 `Argument of type "List[str]" cannot be assigned`），可以忽略，或在代码中添加类型注解：
  ```python
  params: Dict[str, Any] = {"output": output}
  ```

### 5. 启动 MCP 服务（STDIO 模式）

使用以下命令启动服务（默认使用 STDIO 通信）：

```bash
uv run python scripts/start_server.py
```

或直接运行主程序：

```bash
uv run python src/zabbix_mcp_server.py
```

**预期输出**：

```
Starting Zabbix MCP Server...
🚀 Starting MCP server...
Starting MCP server 'Zabbix MCP Server' with transport 'stdio'
```

**排错经验**：

* 如果服务启动后看不到进程（`ps aux | grep zabbix_mcp_server.py`），可能是因为 `uv run` 运行的进程名显示为 `python`。可以用以下命令检查：

  ```bash
  ps aux | grep python
  ```
* 如果服务意外退出，检查 `mcp.log` 或终端日志，常见问题包括环境变量未设置或模块导入失败（如 `ModuleNotFoundError: No module named 'fastmcp'`）。
* 为后台运行服务，使用 `nohup`：

  ```bash
  nohup uv run python src/zabbix_mcp_server.py > mcp.log 2>&1 &
  ```

  检查进程：

  ```bash
  ps aux | grep python
  tail -f mcp.log
  ```

### 6. 将服务改为 HTTP 协议通信

默认情况下，服务使用 STDIO 通信，无法通过 `curl` 或 HTTP 客户端访问（dify1.6.0目前支持的mcp服务只支持HTTP协议通信的mcp-server，因此需要修改为 HTTP 模式）。

#### 修改 `src/zabbix_mcp_server.py`

在 `src/zabbix_mcp_server.py` 中添加命令行参数支持 HTTP 通信。以下是修改后的部分代码：

```python
import os
import json
import logging
import argparse
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from zabbix_utils import ZabbixAPI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
```

**保存位置**：`/root/zabbix-mcp-server/src/zabbix_mcp_server.py`

#### 启动 HTTP 服务

使用以下命令启动 HTTP 服务，绑定到端口 19444：

```bash
python src/zabbix_mcp_server.py --transport http --host 0.0.0.0 --port 19444
```

**预期输出**：

```
Starting Zabbix MCP Server
Read-only mode: False
Zabbix URL: http://<你的 Zabbix 服务器地址>/api_jsonrpc.php
Transport: http
Binding to: 0.0.0.0:19444
```

**排错经验**：

* 如果遇到 `address already in use` 错误，说明端口被占用。检查端口占用：

  ```bash
  netstat -lntp | grep 19444
  ```

  终止占用端口的进程：

  ```bash
  kill <进程号>
  ```
* 如果外部无法访问（如 Dify 报 `503 Service Unavailable`），确保使用 `--host 0.0.0.0` 而非 `127.0.0.1`，并检查防火墙设置：

  ```bash
  sudo ufw allow 19444
  ```

### 7. 测试 HTTP 服务

启动 HTTP 服务后，使用 `curl` 测试：

```bash
# 初始化 MCP 会话
curl -X POST http://<服务器IP>:19444/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {"tools": {}},
      "clientInfo": {"name": "curl-test", "version": "1.0.0"}
    }
  }'

# 获取主机列表
curl -X POST http://<服务器IP>:19444/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "host_get",
      "arguments": {}
    }
  }'

# 获取最近 5 个问题
curl -X POST http://<服务器IP>:19444/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "problem_get",
      "arguments": {
        "recent": true,
        "limit": 5
      }
    }
  }'
```

**预期输出**：返回 JSON 格式的响应，包含初始化结果或主机列表、问题列表等数据。

**排错提示**：

* 如果返回 `503 Service Unavailable`，确认服务是否绑定到 `0.0.0.0` 和端口 19444，检查网络和防火墙设置。
* 如果返回 JSON 解析错误（如 `Invalid JSON`），确保 `curl` 请求的 JSON 格式正确。

### 8. 设置开机自启动

为确保服务在服务器重启后自动运行，使用 `systemd` 配置服务：

#### 创建 systemd 服务文件

```bash
sudo nano /etc/systemd/system/zabbix-mcp-server.service
```

添加以下内容：

```
[Unit]
Description=Zabbix MCP Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/zabbix-mcp-server
Environment=PATH=/root/zabbix-mcp-server/venv/bin
ExecStart=/root/zabbix-mcp-server/venv/bin/python /root/zabbix-mcp-server/src/zabbix_mcp_server.py --transport http --host 0.0.0.0 --port 19444
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**保存位置**：`/etc/systemd/system/zabbix-mcp-server.service`

#### 安装和启用服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable zabbix-mcp-server
sudo systemctl start zabbix-mcp-server
```

#### 检查服务状态

```bash
sudo systemctl status zabbix-mcp-server
```

**预期输出**：

```
● zabbix-mcp-server.service - Zabbix MCP Server
     Loaded: loaded (/etc/systemd/system/zabbix-mcp-server.service; enabled; vendor preset: enabled)
     Active: active (running) since ...
```

**![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/ef26e5c5-439f-4efe-a1dc-322ece8b13ce.png)排错提示**：

* 如果服务未启动，检查日志：
  ```bash
  journalctl -u zabbix-mcp-server -b
  ```
* 确保 `WorkingDirectory` 和 `ExecStart` 路径正确，虚拟环境中的 Python 可执行文件存在。
* 如果日志显示环境变量错误，确认 `.env` 文件已正确加载。

### 9. 验证服务运行

* 检查进程：
  ```bash
  ps aux | grep python
  ```
* 检查端口监听：
  ```bash
  netstat -lntp | grep 19444
  ```
* 查看日志：
  ```bash
  tail -f mcp.log
  ```

**预期输出**：

* 进程列表中包含运行中的 `python src/zabbix_mcp_server.py`。
* 端口 19444 处于监听状态。
* 日志显示服务正常运行，无错误。![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/f392d078-d0c2-4674-a9a8-d67c52a613bc.png)

---

## 在 Dify 1.6.0 中添加 Zabbix MCP 服务的配置框架

以下是在 Dify 1.6.0 中添加 Zabbix MCP 服务的配置框架，根据实际环境填充具体信息：

### 配置框架

| 字段                   | 说明                                 | 示例值                               |
| ---------------------- | ------------------------------------ | ------------------------------------ |
| **服务端点 URL** | MCP 服务的 HTTP 端点地址             | `http://<你的服务器IP>:19444/mcp/` |
| **名称**         | MCP 服务的显示名称                   | `Zabbix 监控服务`                  |
| **服务器标识符** | 唯一标识符，用于在 Dify 中引用该服务 | `zabbix-mcp-server`                |

### 配置步骤

1. 登录 Dify 1.6.0 管理界面。
2. 进入“工具”页面，选择添加 MCP 服务(HTTP)。
3. 填写以下字段：
   * **服务端点 URL**：`http://<你的服务器IP>:19444/mcp/`
   * **名称**：`<自定义名称，如 Zabbix 监控服务>`
   * **服务器标识符**：`<自定义标识符，如 zabbix-mcp-server>`
4. 保存并测试连接，确保 Dify 能成功访问 MCP 服务。![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/90117a4e-622f-4ec2-82a3-3a02f9800632.png)
5. 添加成功后，可以看到该mcp服务右下角变为绿色，点击该mcp服务可看到已授权和可使用的mcp服务。
   ![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/7b51887a-9afb-427f-930b-bd506f0ef7d5.png)

### 注意事项

* **网络可达性**：确保 Dify 服务器能访问 MCP 服务的 IP 和端口（19444）。如果在不同服务器上，检查防火墙和网络安全组设置：
  ```bash
  sudo ufw allow 19444
  ```
* **HTTPS 支持**：如果需要更高的安全性，可以为 MCP 服务配置 HTTPS（需额外配置反向代理如 Nginx）。
* **认证信息**：确保 `.env` 文件中的 Zabbix 认证信息正确，Dify 调用 MCP 服务时会依赖这些信息与 Zabbix API 通信。

### 测试数据

在 Dify 中保存配置后，我们简单创建一个chatflow工作流，可运行zabbix server某个服务查看是否能够获取到数据：

![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/3f75ae88-d69e-4252-a2e2-de2d13320ef1.png)![image.png](https://cdn.jsdelivr.net/gh/Jaycelu/note-gen-image-sync@main/58bbe742-3ebf-4611-abc6-823e62ab3eb1.png)

---

## 总结

通过以上步骤，你可以成功在本地部署 Zabbix MCP Server，并将其配置为 HTTP 服务，绑定到端口 19444，通过 `systemd` 实现开机自启动。排错过程中，我们部署时遇到并解决了以下问题：

* 依赖安装超时（通过切换国内镜像源解决）。
* 模块缺失（如 `fastmcp`、`zabbix_utils`，通过确认源码或安装解决）。
* 端口占用（通过检查和终止进程解决）。
* 外部访问失败（通过绑定 `0.0.0.0` 和开放防火墙解决）。
* 服务进程不可见（通过 `nohup` 和 `ps aux | grep python` 解决）。

在 Dify 1.6.0 中，你可以根据提供的框架添加 MCP 服务，调用 Zabbix 的功能（如 `host_get`、`problem_get` 等）。以上就是我的全部实践经验，后续对于该功能也会进行深入研究，比如dify的双向mcp服务以及zabbix-mcp-server的深层次利用！
