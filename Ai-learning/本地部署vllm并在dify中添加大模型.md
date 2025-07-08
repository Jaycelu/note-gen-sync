# 本地部署 vLLM 并在 Dify 中集成大模型

本文档提供在 Ubuntu 22.04 服务器（Python 3.12 环境）上部署 vLLM 并运行大模型（如 Qwen3-32B 4bit 量化版本）的详细步骤，并指导如何将其集成到 Dify 平台。建议使用 AWQ 量化方式以优化 GPU 显存占用（32B 非量化模型需约 64GB 显存，4bit 量化可显著降低需求）。

---

## 1. 创建模型存储目录

在服务器上创建用于存储大模型的目录：

```bash
mkdir -p /home/user/vllm
cd /home/user/vllm
```

---

## 2. 设置虚拟环境

为避免依赖冲突，创建并激活虚拟环境：

```bash
python3.12 -m venv vllm_env
source vllm_env/bin/activate
```

> **注意**：所有后续命令需在虚拟环境中执行。

---

## 3. 安装 vLLM

使用清华源加速安装 vLLM：

```bash
pip install vllm -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 4. 安装 Hugging Face Hub

使用清华源安装 Hugging Face Hub：

```bash
pip install huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 5. 配置 Hugging Face 代理

由于国内网络限制，设置 Hugging Face 镜像代理：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

> **提示**：每次拉取模型前需执行此命令，或将其添加到 `~/.bashrc` 中以永久生效。

---

## 6. 下载大模型

在目标目录下拉取 Qwen3-32B 模型（可替换为其他模型）：

```bash
huggingface-cli download Qwen/Qwen3-32B --local-dir ./models/qwen3-32b
```

> **注意**：下载时间取决于网络速度和模型大小，确保磁盘空间充足。

---

## 7. 运行 vLLM 服务

进入模型目录并启动 vLLM 的 OpenAI 兼容 API 服务器：

```bash
cd /home/user/vllm/models/qwen3-32b
python3 -m vllm.entrypoints.openai.api_server \
  --model /home/user/vllm/models/qwen3-32b \
  --served-model-name Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --host 0.0.0.0 \
  --port 8000 \
  --enable-chunked-prefill \
  --enforce-eager \
  --trust-remote-code \
  --load-format safetensors \
  --quantization awq_marlin \
  --max-model-len 26624 \
  --gpu-memory-utilization 0.95 \
  --dtype half \
  --disable-custom-all-reduce
```

### 参数说明

- `--model`: 模型路径。
- `--served-model-name`: 模型对外名称，Dify 将使用此名称。
- `--tensor-parallel-size 2`: 使用两块 GPU 进行分布式推理。
- `--host 0.0.0.0`: 监听所有网络接口，允许外部访问。
- `--port 8000`: 服务端口。
- `--enable-chunked-prefill`: 启用分块预填充，提升长序列性能。
- `--enforce-eager`: 强制使用 PyTorch eager 模式，禁用 CUDA 图优化。
- `--trust-remote-code`: 允许加载模型自定义代码。
- `--load-format safetensors`: 使用高效、安全的 safetensors 格式。
- `--quantization awq_marlin`: 使用 AWQ Marlin 量化，优化推理性能。
- `--max-model-len 26624`: 设置最大序列长度，适配 16GB 显存。
- `--gpu-memory-utilization 0.95`: 设置 GPU 显存利用率 95%。
- `--dtype half`: 使用半精度计算，降低显存需求。
- `--disable-custom-all-reduce`: 禁用自定义 all-reduce，解决 GPU P2P 问题。

---

## 8. 配置后台运行与开机自启动

退出虚拟环境并创建 systemd 服务文件：

```bash
deactivate
sudo nano /etc/systemd/system/qwen3-32b.service
```

输入以下内容（根据实际路径调整）：

```ini
[Unit]
Description=Qwen3-32B OpenAI API Server
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/home/user/vllm/models/qwen3-32b
Environment="PATH=/home/user/vllm/vllm_env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0,1"
Environment="OMP_NUM_THREADS=1"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/user/vllm/vllm_env/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model /home/user/vllm/models/qwen3-32b \
  --served-model-name Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --host 0.0.0.0 \
  --port 8000 \
  --enable-chunked-prefill \
  --gpu-memory-utilization 0.95 \
  --max-model-len 26624 \
  --enforce-eager \
  --trust-remote-code \
  --load-format safetensors \
  --quantization awq_marlin \
  --dtype half \
  --disable-custom-all-reduce
Restart=always
RestartSec=10
TimeoutStartSec=900
LimitNOFILE=65535
TasksMax=infinity
MemoryMax=16G
StandardOutput=append:/home/user/vllm/models/qwen3-32b/vllm.log
StandardError=append:/home/user/vllm/models/qwen3-32b/vllm.log

[Install]
WantedBy=multi-user.target
```

### 参数说明

- `After=network.target`: 确保网络可用后再启动。
- `User=root, Group=root`: 以 root 用户运行，确保 GPU 和文件访问权限。
- `CUDA_VISIBLE_DEVICES=0,1`: 指定使用 GPU 0 和 1。
- `OMP_NUM_THREADS=1`: 限制 CPU 线程竞争。
- `PYTHONUNBUFFERED=1`: 确保日志实时输出。
- `Restart=always`: 服务失败时自动重启。
- `TimeoutStartSec=900`: 设置 15 分钟启动超时，适应大模型加载。
- `MemoryMax=16G`: 限制 CPU 内存使用，防止溢出。
- `StandardOutput/StandardError`: 日志输出到指定文件，便于调试。

保存并退出。

---

## 9. 激活 systemd 服务

执行以下命令启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qwen3-32b.service
sudo systemctl start qwen3-32b.service
```

检查服务状态：

```bash
sudo systemctl status qwen3-32b.service
```

正常输出示例：

```bash
● qwen3-32b.service - Qwen3-32B OpenAI API Server
   Loaded: loaded (/etc/systemd/system/qwen3-32b.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2025-06-09 13:52:00 HKT; 10s ago
   Main PID: 12345 (python3)
   Tasks: 10
   Memory: 5.0G
   CPU: 2.500s
   CGroup: /system.slice/qwen3-32b.service
           └─12345 /home/user/vllm/vllm_env/bin/python3 -m vllm.entrypoints.openai.api_server ...
```

---

## 10. 验证 vLLM API

检查 vLLM 服务是否正常运行：

```bash
curl http://localhost:8000/v1/models
```

正常返回示例（包含模型名称 `Qwen3-32B-AWQ`）：

```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen3-32B-AWQ",
      "object": "model",
      "created": 1747804151,
      "owned_by": "vllm",
      "root": "/home/user/vllm/models/qwen3-32b",
      "parent": null,
      "max_model_len": 26624,
      "permission": [
        {
          "id": "modelperm-3e852b8991164fd78f680b0cc46777da",
          "object": "model_permission",
          "created": 1747804151,
          "allow_create_engine": false,
          "allow_sampling": true,
          "allow_logprobs": true,
          "allow_search_indices": false,
          "allow_view": true,
          "allow_fine_tuning": false,
          "organization": "*",
          "group": null,
          "is_blocking": false
        }
      ]
    }
  ]
}
```

---

## 11. 在 Dify 中添加模型

在 Dify 平台配置 vLLM 模型：

进入 **设置 > 模型供应商 > OpenAI**。

填写以下信息：

- **模型名称**: `Qwen3-32B-AWQ`（与 `--served-model-name` 一致）。
- **API Key**: 可留空或填 `EMPTY`。
- **API Endpoint URL**: `http://<服务器IP>:8000/v1`（如 `http://10.128.206.252:8000/v1`）。
- **模型上下文长度**: `26624`（与 `--max-model-len` 一致）。
- **最大 Token 上限**: `26624`。

保存配置后，Dify 即可通过 vLLM 调用 Qwen3-32B 模型。

---

## 12. 注意事项

- **显存需求**：32B 非量化模型需约 64GB GPU 显存，建议使用 AWQ 量化版本以适配 16GB 显存。
- **端口冲突**：确保 8000 端口未被占用。
- **日志调试**：服务启动失败时，检查 `/home/user/vllm/models/qwen3-32b/vllm.log` 日志。
- **网络代理**：Hugging Face 下载需稳定代理，确保 `HF_ENDPOINT` 配置正确。
- **GPU 配置**：`CUDA_VISIBLE_DEVICES` 需与 `--tensor-parallel-size` 匹配。
