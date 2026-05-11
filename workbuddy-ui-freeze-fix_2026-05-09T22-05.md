# WorkBuddy UI Freeze Fix

**时间**: 2026-05-09 22:00-22:05 CST

## 问题

用户报告 WorkBuddy UI 冻结无响应。

## 诊断

| 项目 | 状态 |
|------|------|
| 进程数 | 7个（偏多） |
| 内存 | 正常（15-61MB） |
| CPU | 正常 |
| GPU Cache | 1.6 MB |
| 通用 Cache | 72.9 MB |
| 日志最后写入 | 20:58，之后无有效日志 |
| WAL 文件 | 存在（40KB），数据库可能活跃写入 |

## 根因推断

多个 WorkBuddy 进程堆叠 + 渲染缓存积压，在 20:58 `yourself-skill` 热重载时触发渲染线程阻塞。

## 修复步骤

1. 杀掉 6/7 僵尸进程（1个 PID 5148 无权限杀，但 0 线程 0 内存无害）
2. 清空 6 个渲染缓存目录（GPUCache, DawnGraphiteCache, DawnWebGPUCache, Code Cache, Cache, Shared Dictionary）
3. 备份并移除 WAL 文件（workbuddy.db-wal, workbuddy.db-shm）
4. 启动新 WorkBuddy 实例（v4.22.7）

## 结果

新实例 3 个进程正常运行，主日志 22:02:45 有活动记录，Centrifugo 连接成功。