# 任务：Windows 音质优化 - 苹果风格 EQ

## 目标
将 Realtek 声卡的音质调校至苹果风格：人声略突出、高频顺滑不刺耳、低频干净有力。

## 环境
- 声卡：Realtek High Definition Audio (Device ID: 10EC0887)
- 驱动：Realtek UAD (Universal Audio Driver)，无传统控制面板 GUI
- 系统：Windows 10/11

## 执行结果

### ✅ 已完成
| 项目 | 状态 | 说明 |
|------|------|------|
| 声音控制面板打开 | ✅ | mmsys.cpl 已打开 |
| 系统采样率 | ✅ | 已写入注册表 24bit/48000Hz |
| 无声方案注册 | ✅ | 控制面板 → 声音 → 选"无声" |
| EQ 配置文件 | ✅ | `apple_eq_config.txt` 已生成 |

### ⬜ 需手动操作
| 项目 | 操作 |
|------|------|
| 禁用音频增强 | 声音控制面板 → 扬声器 → 属性 → 增强 → ☑️ 禁用所有音频增强 |
| 高级格式 | 扬声器 → 属性 → 高级 → 24位 48000Hz + 独占模式 |
| 安装 EQ 软件 | 见下方两个方案 |

## EQ 方案对比

### 方案 A：FxSound（推荐）
- ✅ winget / 国内镜像可安装
- ✅ 现代 UI，操作简单
- ⚠️ 国内下载源可能被限速
- 设置方式：10段图形 EQ，参考配置已准备好

### 方案 B：Equalizer APO（更专业）
- ✅ 系统级音频处理，播放器/游戏全生效
- ⚠️ SourceForge 下载被网络限制
- 设置方式：配置文件路径 `C:\Program Files\EqualizerAPO\config\config.txt`

## EQ 参数（苹果风格）

```
Preamp: -3 dB
32Hz: 0 dB | 64Hz: -1 dB | 125Hz: -2 dB | 250Hz: -1 dB
500Hz: 0 dB | 1kHz: 0 dB | 2kHz: +1 dB | 4kHz: +1 dB
8kHz: +2 dB | 16kHz: 0 dB
```

## 文件输出
- `apple_eq_config.txt` - 完整安装说明和 EQ 参数

## 问题
- SourceForge / GitHub 下载被网络限制
- winget 安装 FxSound 也因 GitHub 下载超时失败
- Realtek UAD 无传统控制面板托盘图标，无法自动化配置
