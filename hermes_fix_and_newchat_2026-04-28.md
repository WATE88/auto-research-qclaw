# Hermes Agent 修复 + 新对话系统搭建

**时间**: 2026-04-28  
**目标**: 全都要 —— 修复现有 Hermes Agent + 按新设计搭建简洁对话系统

---

## 一、Hermes Agent 修复记录

### 问题1: `gateway.py` wmic 编码错误
- **现象**: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xcf` + `AttributeError: 'NoneType' object has no attribute 'split'`
- **原因**: `subprocess.run(..., text=True)` 在中文 Windows 上用系统默认编码（GBK）解码 wmic 输出，但输出含特殊字符
- **修复**: 改为 `text=False` 获取 bytes，尝试多种编码解码（utf-8 → gbk → cp936 → latin-1）
- **文件**: `C:\Users\wate\hermes-agent\hermes_cli\gateway.py`（行221-238）

### 问题2: `status.py` `os.kill(pid, 0)` WinError 87
- **现象**: Status API 返回 500，`OSError: [WinError 87]`
- **原因**: `os.kill(pid, 0)` 在 Windows 上不兼容（Unix 信号机制）
- **修复**: 在 except 中添加 `OSError`（Windows 抛 WinError 87 而非 ProcessLookupError）
- **文件**: `C:\Users\wate\hermes-agent\gateway\status.py`（行598）

### 问题3: Gateway 启动后立即退出（KeyboardInterrupt）
- **现象**: `asyncio.exceptions.CancelledError` → `KeyboardInterrupt`
- **原因**: `Start-Process` 重定向输出导致进程收到中断信号
- **解决**: 改用独立 PowerShell 窗口运行（`Start-Process powershell -ArgumentList "-Command", "..."`）
- **状态**: 待验证稳定

### 配置补充
- 在 `C:\Users\wate\AppData\Local\hermes\.env` 中添加：
  ```
  GATEWAY_ALLOW_ALL_USERS=true
  HERMES_ACCEPT_HOOKS=1
  ```

### 当前状态
| 组件 | 端口 | 状态 |
|------|------|------|
| Web UI Server (Uvicorn) | 9119 | ✅ 运行中 |
| Gateway | - | ⚠️ 调试中 |
| Status API | - | ✅ 正常（返回 gateway_running: false）|

---

## 二、新对话系统（Simple Chat）✅ 完成

### 设计理念
- **简化架构**: 去掉 Hermes 的 gateway/web_server 分离，合并为单文件后端
- **直接调用**: 通过 OpenRouter API 直接调用 LLM，无需复杂消息平台
- **零构建**: 前端纯 HTML+CSS+JS，无需 React/Node.js 构建

### 文件结构
```
C:\Users\wate\simple-chat\
├── backend.py          # FastAPI 后端（调用 OpenRouter）
├── index.html          # 前端对话界面
├── .env                # API Key（从 Hermes 复制）
├── backend.log         # 后端日志
└── backend_err.log     # 后端错误日志
```

### 技术栈
| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + Uvicorn + httpx |
| 前端 | 原生 HTML + CSS + JavaScript |
| LLM | OpenRouter (anthropic/claude-opus-4.6) |
| 依赖 | python-dotenv, httpx |

### 访问地址
- **前端**: http://127.0.0.1:8080
- **后端 API**: http://127.0.0.1:9222
- **状态检查**: http://127.0.0.1:9222/api/status

### 使用方法
1. 打开浏览器访问 http://127.0.0.1:8080
2. 在输入框输入消息，按 Enter 发送
3. 对话通过 OpenRouter 调用 claude-opus-4.6

---

## 三、下一步

### Hermes Agent
- [ ] 验证 Gateway 是否稳定运行
- [ ] 测试 Hermes Web UI 聊天功能（http://127.0.0.1:9119）
- [ ] 如 Gateway 仍有问题，考虑同样用简化方案替换

### 新对话系统
- [ ] 增加 streaming 响应（WebSocket）
- [ ] 增加会话历史持久化（SQLite）
- [ ] 增加模型切换功能
- [ ] 美化界面（参考 ChatGPT 风格）

---

**总结**: Hermes 修复完成80%，新对话系统100%完成可用。用户可立即使用 http://127.0.0.1:8080 进行对话。
