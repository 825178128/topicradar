# topicradar · 自媒体选题雷达（学习项目）

> 12 周路线的代码仓库（对应 [[02-学习路线]] 的 W0–W12）。目标是：输入领域 → 检索 → 5 张选题卡 → 脚本。

## 当前阶段

- **W00 准备期**（2026-11-12 → 11-15）：环境 + 三条通路
- 已搭好：`w0/hello_llm.py`、`w1/llm_ping.py`、`w1/mock_server.py`、`w1/selftest.py`
- 待你补：`.env` 里的 API key（真实调用需要）

## 快速开始

```powershell
# 1) 建虚拟环境（本机 Python 3.13 在 conda 里，且不在 PATH）
#    注意：不要用 python -m venv 默认参数——本机 ensurepip 会失败（沙箱临时目录权限）
C:\Users\lee\miniconda3\python.exe -m venv --without-pip --system-site-packages .venv
.\.venv\Scripts\python.exe -c "import httpx;print(httpx.__version__)"   # 应输出 0.28.1

# 2) 配置 key（把 .env.example 复制成 .env，填 API_KEY）
Copy-Item .env.example .env

# 3) 不需要 key 的自检
.\.venv\Scripts\python.exe w1\selftest.py

# 4) 真实调用（需要第 2 步）
.\.venv\Scripts\python.exe w1\llm_ping.py "用一句话解释什么是 agent" --stream
```

> 如需装新包：`C:\Users\lee\miniconda3\python.exe -m pip --python .venv\Scripts\python.exe install <pkg>`。
> 若报临时目录 `PermissionError`，说明被沙箱拦了，直接用 conda base 的 python 运行即可（httpx 已自带）。

## 目录

```
w0/          准备期：最小调用
w1/          第一周：调用封装 + 重试 + 成本
notes/       环境结论与踩坑
```

## 安全

- `API_KEY` 只放 `.env`，`.env` 已被 `.gitignore` 忽略。
- 不要把 key 贴进聊天、日志、截图；`llm_ping` 只打印 token，不打印 key。

## 技术选择说明

脚手架用 **标准库 urllib** 跑通（零依赖，先看清 HTTP 长什么样）；W1 的任务是用 `httpx` 重写一遍，对比两者差异——这是计划里"先手写、后框架"的同一逻辑。
