# AutoResearch 跨机器部署指南 v3.0

> 本文档说明如何将 AutoResearch 打包并在另一台电脑上正常运行，且不出现乱码。

---

## 一、打包（在当前电脑操作）

### 方法 A：运行打包脚本（推荐）

```bat
python pack.py
```

输出文件在上一级目录的 `dist/` 文件夹中：
```
autoresearch-portable-20260325_1945.zip
```

### 方法 B：手动压缩

直接将整个 `autoresearch-v1.0.0-20260324\` 文件夹压缩成 zip 即可。

**注意排除以下文件（不影响运行，但体积大）：**
- `*.db` — 本机数据库（新机器会自动创建）
- `__pycache__/` — Python 字节码缓存
- `*.log` — 运行日志

---

## 二、在新电脑上部署

### 前提条件

| 要求 | 说明 |
|------|------|
| **操作系统** | Windows 10/11（64位）|
| **Python 版本** | **3.9 或更高**（建议 3.11/3.12）|
| **磁盘空间** | 200MB+（含依赖）|
| **内存** | 2GB+（推荐 4GB）|
| **网络** | 首次安装依赖需要（安装后可离线运行）|

### 步骤 1：安装 Python

1. 访问 https://www.python.org/downloads/
2. 下载 **Python 3.11.x** 或 **3.12.x**（推荐）
3. 安装时 **必须勾选 "Add Python to PATH"**
4. 验证安装：打开 cmd 输入 `python --version`

> **国内镜像（下载更快）：**  
> https://mirrors.huaweicloud.com/python/

### 步骤 2：解压文件

```
将 autoresearch-portable-xxxx.zip 解压到任意目录
推荐路径示例：D:\AutoResearch\
```

> ⚠️ **路径注意事项：**
> - 尽量使用纯英文路径，如 `D:\AutoResearch`
> - 避免含有空格：~~`D:\My Programs\AutoResearch`~~
> - 中文路径也支持，但如果出现异常优先改为英文路径

### 步骤 3：安装依赖（首次运行一次即可）

**方法 A：双击 `install.bat`（推荐）**
- 自动检测 Python
- 自动选择清华/阿里云镜像
- 自动安装所有依赖

**方法 B：手动安装**
```bat
# 在 AutoResearch 目录下打开 cmd
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 步骤 4：启动系统

```
双击 launch.bat
```

系统会自动：
1. 检测 Python 路径（无需手动配置）
2. 启动服务（端口 8899）
3. 打开浏览器监控界面

访问地址：**http://localhost:8899/**

---

## 三、乱码问题排查

系统已内置编码修复（`autoresearch_encoding.py`），以下是额外排查方法：

### 问题 1：cmd 窗口中文乱码

**原因：** Windows 默认代码页是 GBK (936)，Python 输出 UTF-8 导致乱码。

**解决方案（已在 launch.bat 自动处理）：**
```bat
chcp 65001   # 切换为 UTF-8 代码页
```

**手动验证：**
```bat
chcp
# 应显示 "活动代码页: 65001"
```

### 问题 2：浏览器界面乱码

**原因：** HTML 文件编码声明缺失。

**验证：** 浏览器按 F12 → Network → 查看响应头 `Content-Type: text/html; charset=utf-8`

### 问题 3：日志文件乱码

所有日志文件均以 UTF-8 写入。如用记事本打开乱码，请改用 **VS Code** 或 **Notepad++** 打开。

### 问题 4：Python 3.15+ 兼容性

项目已设置 `PYTHONUTF8=1` 环境变量，兼容所有 3.9+ 版本。

---

## 四、依赖清单

| 包名 | 版本要求 | 用途 |
|------|---------|------|
| numpy | >=1.24 | 核心数值计算 |
| scipy | >=1.10 | 贝叶斯优化 |
| pandas | >=2.0 | 数据处理 |
| scikit-learn | >=1.3 | 机器学习算法 |
| psutil | >=5.9 | 系统监控 |
| bayesian-optimization | >=1.4 | 可选：贝叶斯优化库 |
| matplotlib | >=3.7 | 可选：可视化 |

> 核心功能只需 **numpy + scipy**，其余为可选增强。

---

## 五、API 接口一览

| 端点 | 说明 |
|------|------|
| `GET /` | 统一监控 Dashboard |
| `GET /api/status` | 系统状态（用于检测是否就绪）|
| `GET /api/snapshot` | 完整双系统快照 |
| `GET /api/evolve/history` | 进化历史 |
| `GET /api/autorun/tasks` | 自动运行任务列表 |
| `GET /api/experiments/leaderboard` | 实验排行榜 |
| `GET /api/importance/analyze` | 超参数重要性分析 |
| `GET /api/drift/status` | 漂移检测状态 |
| `POST /api/drift/push` | 推送新得分（触发漂移检测）|
| `POST /api/experiments/record` | 提交实验记录 |

---

## 六、常见问题

### Q：找不到 Python，launch.bat 报错？

```
# 手动安装 Python 后重试
# 或直接指定路径运行：
C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe autoresearch_unified_server.py
```

### Q：端口 8899 被占用？

```bat
# 查找占用进程
netstat -ano | findstr :8899

# 方法1：在 launch.bat 里改 PORT=9000
# 方法2：停止占用进程后重试
```

### Q：安装依赖超时？

```bat
# 使用离线安装（需先在有网络的电脑下载 whl 文件）
pip install --no-index --find-links=./offline_packages -r requirements.txt

# 或更换镜像源
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### Q：`scikit-learn` 安装失败？

```bat
# 先安装 Microsoft C++ Build Tools，或使用 conda
conda install scikit-learn
```

---

## 七、文件结构说明

```
autoresearch/
├── launch.bat                    # 主启动器（可移植，无硬编码路径）
├── install.bat                   # 一键安装依赖
├── pack.py                       # 打包工具（打包前在此机器运行）
├── autoresearch_encoding.py      # 编码修复模块（UTF-8 乱码防护）
├── autoresearch_unified_server.py  # 统一服务器（入口）
├── autoresearch_unified_dashboard.html  # Web 监控界面
├── autoresearch_self_evolve.py   # 自主进化引擎
├── autoresearch_autorun.py       # 自动运行引擎
├── autoresearch_drift.py         # 漂移检测
├── autoresearch_version.py       # 实验版本管理
├── autoresearch_importance.py    # 超参数重要性分析
├── autoresearch_sdk.py           # Python REST SDK
├── requirements.txt              # 依赖清单
├── DEPLOY.md                     # 本文档
└── README.md                     # 项目说明
```

---

## 八、版本历史

| 版本 | 日期 | 主要变化 |
|------|------|---------|
| v3.0 | 2026-03-25 | 可移植打包、编码修复、自动探测Python |
| v2.1 | 2026-03-24 | 自我学习系统、漂移检测、版本管理、SDK |
| v2.0 | 2026-03-24 | 完全版：部署监控 CI/CD 分布式训练 |
| v1.0 | 2026-03-24 | 初始版本：贝叶斯优化核心 |
