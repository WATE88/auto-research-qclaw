# 任务完成：Windows 音质优化 - 苹果风格 EQ

## 目标
将 Realtek 声卡音质调校至苹果风格：人声突出、高频顺滑、低频干净。

## 执行结果

### ✅ 已完成（全部自动化）
| 项目 | 状态 |
|------|------|
| FxSound 安装 | ✅ v1.1.31.0 |
| 苹果风格 EQ 预设创建 | ✅ `C:\Users\wate\AppData\Roaming\FxSound\Presets\Apple EQ.fac` |
| FxSound 默认预设设为 Apple EQ | ✅ |
| FxSound 已启动并应用 | ✅ |

### ⬜ 待用户手动确认
| 项目 | 操作 |
|------|------|
| 声音控制面板音频增强 | 打开 mmsys.cpl → 扬声器 → 属性 → 增强 → ☑️ 禁用所有音频增强 |
| 声音控制面板格式设置 | 高级 → 24位 48000Hz + 独占模式 |

## FxSound 苹果 EQ 参数（已应用）

| 频段 | 频率 | 增益 | 效果 |
|------|------|------|------|
| 1 | 62.5 Hz | -1 dB | 削减低频轰鸣 |
| 2 | 121.5 Hz | -2 dB | 削减低频浑浊 |
| 3 | 225 Hz | -1 dB | 削减鼻音 |
| 4 | 416.5 Hz | 0 dB | 保持中性 |
| 5 | 770.5 Hz | 0 dB | 保持中性 |
| 6 | 1425 Hz | +1 dB | 人声临场感 |
| 7 | 2645 Hz | +1 dB | 人声清晰度 |
| 8 | 4895 Hz | +2 dB | 高频顺滑，空气感 |
| 9 | 9060 Hz | 0 dB | 不刺耳 |
| 10 | 13885 Hz | 0 dB | 高频延伸自然 |

## 关键文件
- `C:\Users\wate\AppData\Roaming\FxSound\Presets\Apple EQ.fac` - 苹果风格预设
- `C:\Users\wate\.qclaw\workspace-agent-d29ea948\apple_eq_config.txt` - 完整配置文档

## 技术发现
- FxSound 预设格式：纯文本 INI 类格式（.fac 文件）
- 配置目录：`%APPDATA%\FxSound\Presets\`
- FxSound 使用 Windows APO（音频处理对象）驱动层处理 EQ
- 默认安装路径：`C:\Program Files\FxSound LLC\FxSound\`
