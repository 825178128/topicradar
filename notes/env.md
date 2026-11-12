# 环境验证记录（2026-11-12）

> 由 DSH 实际执行，命令与结果如下。结论先行：**三条通路都通，只差真实 key**。

## 本机事实

| 项 | 结果 |
|---|---|
| Python | 3.13.12，位于 `C:\Users\lee\miniconda3\python.exe`（**不在 PATH**，`python` 命令指向 Microsoft Store 存根） |
| pip | 26.0.1（conda base 可用；venv 内因沙箱临时目录权限装不上，见下） |
| httpx | 0.28.1（conda base 已自带，venv 通过 `--system-site-packages` 继承） |
| Git | 2.53.0；**未配置 user.name / user.email** |
| Node | v24.15.0（备用，本项目不用） |
| VS Code | `D:\vscode\bin\code.cmd` 可用 |
| gh | 未安装（GitHub 仓库需网页创建或装 gh） |
| 代理 | `127.0.0.1:7897` 端口开放 |

## 三条通路

| 通路 | 命令 | 结果 |
|---|---|---|
| DeepSeek 直连 | `llm_ping.py --key sk-bogus --no-proxy` | **HTTP 401** → 网络与 TLS 正常，仅 key 无效 |
| OpenAI 经代理 | `HTTPS_PROXY=http://127.0.0.1:7897` + `--base https://api.openai.com/v1` | **HTTP 401** → 代理链路正常 |
| 公网页面抓取 | 直连 `https://www.bilibili.com` | **200**（返回为公开页） |

## 客户端自检

`python w1/selftest.py` → **4/4 通过**

- 流式 + 首次 500 自动重试 + usage 统计
- 非流式 + usage
- 401 错误提示可读
- 费用计算

## venv 的坑（重要）

`python -m venv .venv` 在本机失败：`ensurepip` 退出码 1，`pip` 装不进 venv（沙箱对 `%TEMP%\dsh-*` 目录 chmod 拒绝访问，`PermissionError WinError 5`）。

**可用做法**：

```powershell
C:\Users\lee\miniconda3\python.exe -m venv --without-pip --system-site-packages .venv
.\.venv\Scripts\python.exe w1\selftest.py
```

venv 继承 base 的 httpx，零安装即可跑。真要装包时用：

```powershell
C:\Users\lee\miniconda3\python.exe -m pip --python .venv\Scripts\python.exe install <pkg>
```

（若仍报临时目录权限错，说明沙箱拦了 pip 的临时目录；此时直接用 conda base python 运行。）

## 待办（需要你）

1. 把 `.env.example` 复制为 `.env`，填 `API_KEY`（DeepSeek 控制台申请）→ 我跑一次真实调用验证。
2. 配 Git 身份：`git config --global user.name "..."` / `user.email "..."` → 然后首次提交。
3. GitHub 建仓库 `topicradar`（网页即可），再 `git remote add origin ...`。
