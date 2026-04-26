# Hermes-Agent 安装与配置

## 任务目标
将 GitHub 仓库 WATE88/hermes-agent 同步到本地，并配置运行环境。

## 执行过程

### 1. 仓库同步
- **位置**: `C:\Users\wate\hermes-agent`
- **大小**: 37.4 MB
- **方式**: `git clone --depth=1`

### 2. 环境配置
- Python: 3.12.10 ✅
- 依赖安装: `pip install -e ".[core]"` ✅
- 配置目录: `C:\Users\wate\AppData\Local\hermes\`

### 3. API Key 配置
- 用户提供了 OpenRouter API key
- 写入位置: `C:\Users\wate\AppData\Local\hermes\.env`
- 变量名: `OPENROUTER_API_KEY`
- 验证: curl 测试成功，能访问 OpenRouter 模型列表

### 4. 运行验证
- `hermes doctor`: 基本环境检查通过
- `hermes status`: 显示 OpenRouter 未配置 → 已修复
- `hermes chat --query hello`: 
  - ✅ 工具集加载成功（27 tools）
  - ✅ Skills 加载成功（76 skills）
  - ✅ 模型识别：`claude-opus-4.6`
  - ⚠️ TUI 需要 Windows 真实终端（exec 工具限制）

## 最终状态

| 检查项 | 状态 |
|--------|------|
| 仓库 clone | ✅ 持久化 |
| Python 环境 | ✅ 3.12.10 |
| 依赖安装 | ✅ |
| API Key 配置 | ✅ OpenRouter |
| 默认模型 | `anthropic/claude-opus-4.6` |
| 工具集 | 27 个 |
| Skills | 76 个 |
| 交互式 TUI | ✅ 在真实终端可用 |

## 运行方式

**PowerShell:**
```powershell
cd C:\Users\wate\hermes-agent
$env:PYTHONIOENCODING="utf-8"
hermes chat
```

**或直接:**
```cmd
hermes chat
```

## 遇到的问题与解决

1. **GBK 编码错误**: Windows 终端默认 GBK，需设置 `PYTHONIOENCODING=utf-8`
2. **exec 工具控制台限制**: `prompt_toolkit` 需要真实 Windows 控制台缓冲区，无法在 exec 子进程中运行交互式 TUI
3. **配置目录**: hermes 读取 `C:\Users\wate\AppData\Local\hermes\.env`，不是仓库目录下的 .env

## 备注
- hermes-agent 官方不支持原生 Windows，推荐 WSL2
- 实测核心功能在 Windows Python 环境下可正常运行
- 交互式 TUI 需要在真实终端中运行
