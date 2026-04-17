"""
AutoResearch MCP 工具服务器
============================
通过 MCP（Model Context Protocol）将 AutoResearch 的能力暴露给 WorkBuddy AI。

AI 可以直接调用：
  - get_status         → 查看系统当前状态
  - get_evolve_summary → 进化系统摘要 + 最优解
  - get_autorun_summary→ 自动运行任务概览
  - get_best_config    → 获取当前最优超参数配置
  - get_recommendations→ AI 决策推荐（最优策略+下一步建议）
  - run_benchmark      → 触发基准测试
  - get_strategy_ranking → 策略排行榜
  - get_round_history  → 跨轮次历史数据
  - get_logs           → 获取最新日志

启动方式（stdio，WorkBuddy mcp.json 使用）：
  python autoresearch_mcp_server.py
"""

import os, sys, io, json, urllib.request, urllib.error

# ── 编码修复 ─────────────────────────────────────────────────────────────────
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if hasattr(sys.stdin, 'buffer'):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

# ── AutoResearch 服务地址 ──────────────────────────────────────────────────
AR_BASE = os.environ.get("AUTORESEARCH_URL", "http://localhost:8899")

# ─────────────────────────────────────────────────────────────────────────────
# 辅助：HTTP GET
# ─────────────────────────────────────────────────────────────────────────────

def _get(path: str, timeout: int = 8) -> dict:
    url = f"{AR_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.URLError as e:
        return {"error": f"无法连接 AutoResearch 服务（{AR_BASE}）: {e.reason}",
                "hint": "请先启动 AutoResearch：双击 launch.bat 或运行 python autoresearch_unified_server.py"}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 工具实现
# ─────────────────────────────────────────────────────────────────────────────

def tool_get_status(_args: dict) -> dict:
    """获取 AutoResearch 服务当前状态"""
    data = _get("/api/status")
    if "error" in data:
        return data
    return {
        "service": "online",
        "evolve_running": data.get("evolve_running", False),
        "autorun_running": data.get("autorun_running", False),
        "server_time": data.get("server_time"),
        "dashboard_url": f"{AR_BASE}/",
        "message": "AutoResearch 服务运行正常" if not data.get("error") else data["error"]
    }


def tool_get_evolve_summary(_args: dict) -> dict:
    """获取自主进化系统摘要：当前代数、最优分数、候选解分布"""
    snap = _get("/api/evolve")
    if "error" in snap:
        return snap

    summary = snap.get("summary", {})
    live = snap.get("live", {})
    strategy_dist = snap.get("strategy_dist", [])[:5]
    best_curve = snap.get("best_curve", [])[-10:]  # 最近10代曲线

    return {
        "status": snap.get("status", "unknown"),
        "current_generation": summary.get("current_gen") or live.get("current_gen", 0),
        "global_best_score": summary.get("global_best") or live.get("best_score", 0),
        "total_candidates_evaluated": summary.get("total_candidates") or live.get("total_candidates", 0),
        "total_improvements": live.get("total_improvements", 0),
        "top_strategies": strategy_dist,
        "active_genome": live.get("active_genome"),
        "recent_trend": best_curve,
        "dashboard_url": f"{AR_BASE}/#evolve"
    }


def tool_get_autorun_summary(_args: dict) -> dict:
    """获取自动运行引擎任务概览：任务列表、完成数、当前学习分数"""
    snap = _get("/api/autorun")
    if "error" in snap:
        return snap

    summary = snap.get("summary", {})
    tasks = snap.get("tasks", [])
    strategy_counts = snap.get("strategy_counts", {})

    # 找出最优任务
    best_task = None
    best_score = -1
    for t in tasks:
        if t.get("best_score", 0) > best_score:
            best_score = t["best_score"]
            best_task = t

    return {
        "status": snap.get("status", "unknown"),
        "running_tasks": summary.get("running", 0),
        "completed_tasks": summary.get("completed_count", 0),
        "total_tasks": summary.get("total", 0),
        "learning_score": summary.get("learning_score", 0),
        "current_genome_tag": summary.get("current_genome_tag", "default"),
        "cpu_usage": summary.get("cpu", 0),
        "memory_usage": summary.get("mem", 0),
        "strategy_distribution": strategy_counts,
        "best_task": best_task,
        "dashboard_url": f"{AR_BASE}/#autorun"
    }


def tool_get_best_config(_args: dict) -> dict:
    """
    获取当前最优超参数配置（genome）。
    返回自主进化系统找到的最佳参数组合及其性能评分。
    """
    snap = _get("/api/snapshot")
    if "error" in snap:
        return snap

    evolve = snap.get("evolve", {})
    live = evolve.get("live", {})
    candidates = evolve.get("candidates", [])
    summary = evolve.get("summary", {})

    # 找最高分候选
    top_candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:5]

    active_genome = live.get("active_genome", {})
    best_score = summary.get("global_best") or live.get("best_score", 0)

    return {
        "best_score": best_score,
        "active_genome": active_genome,
        "top_5_candidates": [
            {
                "generation": c.get("generation"),
                "score": c.get("score"),
                "genome": _safe_json(c.get("genome_json") or c.get("genome")),
                "strategy": c.get("strategy_name"),
            }
            for c in top_candidates
        ],
        "interpretation": _interpret_genome(active_genome, best_score),
        "dashboard_url": f"{AR_BASE}/#candidates"
    }


def _safe_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _interpret_genome(genome: dict, score: float) -> str:
    """将 genome 翻译成人类可读的决策建议"""
    if not genome:
        return "暂无有效基因组数据，请等待进化系统运行更多代次。"

    parts = []
    if "learning_rate" in genome:
        lr = genome["learning_rate"]
        if lr < 0.001:
            parts.append(f"学习率={lr}（偏小，收敛稳定但较慢）")
        elif lr > 0.01:
            parts.append(f"学习率={lr}（偏大，收敛快但可能震荡）")
        else:
            parts.append(f"学习率={lr}（均衡）")

    if "batch_size" in genome:
        bs = genome["batch_size"]
        parts.append(f"批次大小={bs}")

    if "hidden_dim" in genome or "hidden_size" in genome:
        dim = genome.get("hidden_dim") or genome.get("hidden_size")
        parts.append(f"隐层维度={dim}")

    if "dropout" in genome:
        parts.append(f"Dropout={genome['dropout']}")

    if "optimizer" in genome:
        parts.append(f"优化器={genome['optimizer']}")

    score_str = f"当前最优得分 {score:.4f}" if score else "得分未知"
    if not parts:
        return f"{score_str}；基因组参数：{json.dumps(genome, ensure_ascii=False)}"

    return f"{score_str}；推荐配置：" + "，".join(parts)


def tool_get_recommendations(_args: dict) -> dict:
    """
    AI 决策推荐：综合分析当前进化状态，给出下一步操作建议。
    包括：最优策略推荐、是否继续优化、收益/风险评估。
    """
    snap = _get("/api/snapshot")
    if "error" in snap:
        return snap

    evolve = snap.get("evolve", {})
    autorun = snap.get("autorun", {})
    live = evolve.get("live", {})
    summary_e = evolve.get("summary", {})
    summary_a = autorun.get("summary", {})
    strategy_dist = evolve.get("strategy_dist", [])
    best_curve = evolve.get("best_curve", [])

    # ── 分析收益趋势 ───────────────────────────────────────────────────────
    trend = "unknown"
    improvement_rate = 0.0
    if len(best_curve) >= 3:
        recent = best_curve[-3:]
        scores = [r.get("best_score", 0) for r in recent]
        if scores[-1] > scores[0]:
            improvement_rate = (scores[-1] - scores[0]) / max(abs(scores[0]), 1e-9) * 100
            trend = "improving"
        elif scores[-1] == scores[0]:
            trend = "plateau"
        else:
            trend = "regressing"

    # ── 最优策略推荐 ───────────────────────────────────────────────────────
    best_strategy = strategy_dist[0] if strategy_dist else {}
    strategy_name = best_strategy.get("strategy_name", "EI")
    strategy_score = best_strategy.get("avg_score", 0)

    # ── 生成建议 ───────────────────────────────────────────────────────────
    current_gen = summary_e.get("current_gen") or live.get("current_gen", 0)
    global_best = summary_e.get("global_best") or live.get("best_score", 0)
    total_improvements = live.get("total_improvements", 0)
    learning_score = summary_a.get("learning_score", 0)

    recommendations = []

    # 建议1：策略选择
    recommendations.append({
        "category": "策略推荐",
        "priority": "高",
        "action": f"使用 {strategy_name} 策略",
        "reason": f"该策略平均得分 {strategy_score:.4f}，在所有策略中表现最佳",
        "confidence": "高" if strategy_score > 0.8 else "中"
    })

    # 建议2：是否继续优化
    if trend == "improving":
        recommendations.append({
            "category": "继续优化",
            "priority": "高",
            "action": "继续运行自主进化",
            "reason": f"最近3代性能提升 {improvement_rate:.1f}%，趋势良好",
            "confidence": "高"
        })
    elif trend == "plateau":
        recommendations.append({
            "category": "突破瓶颈",
            "priority": "中",
            "action": "尝试增大变异率或切换搜索策略",
            "reason": "系统进入平台期，当前策略已收敛，建议引入多样性",
            "confidence": "中"
        })
    else:
        recommendations.append({
            "category": "性能回退",
            "priority": "高",
            "action": "回滚到上一个最优基因组",
            "reason": "检测到性能下降趋势，建议回滚并调整探索/利用平衡",
            "confidence": "中"
        })

    # 建议3：超参数优化
    active_genome = live.get("active_genome", {})
    if active_genome:
        recommendations.append({
            "category": "超参数建议",
            "priority": "中",
            "action": _interpret_genome(active_genome, global_best),
            "reason": "基于当前最优基因组分析",
            "confidence": "中"
        })

    # 建议4：学习系统
    if learning_score > 0.8:
        recommendations.append({
            "category": "自我学习",
            "priority": "低",
            "action": "系统学习状态良好，维持当前配置",
            "reason": f"学习得分 {learning_score:.3f}（优秀）",
            "confidence": "高"
        })
    elif learning_score < 0.5:
        recommendations.append({
            "category": "自我学习",
            "priority": "中",
            "action": "增加训练轮次，积累更多历史数据",
            "reason": f"学习得分 {learning_score:.3f}（偏低），需要更多样本",
            "confidence": "中"
        })

    return {
        "overall_assessment": {
            "current_generation": current_gen,
            "global_best_score": global_best,
            "performance_trend": trend,
            "improvement_rate_pct": round(improvement_rate, 2),
            "total_improvements": total_improvements,
            "learning_score": learning_score,
        },
        "best_strategy": {
            "name": strategy_name,
            "avg_score": round(strategy_score, 4),
        },
        "recommendations": recommendations,
        "summary": f"系统已运行 {current_gen} 代，最优得分 {global_best:.4f}，趋势{'上升' if trend == 'improving' else '平稳' if trend == 'plateau' else '下降'}。"
                   f"推荐策略：{strategy_name}。",
        "dashboard_url": AR_BASE
    }


def tool_get_strategy_ranking(_args: dict) -> dict:
    """获取所有优化策略的排行榜（按平均得分降序）"""
    snap = _get("/api/evolve")
    if "error" in snap:
        return snap

    strategy_dist = snap.get("strategy_dist", [])
    live = snap.get("live", {})
    strategy_weights = live.get("strategy_weights", {})
    strategy_rank = live.get("strategy_rank", [])

    merged = []
    seen = set()
    for item in strategy_dist:
        name = item.get("strategy_name", "")
        seen.add(name)
        merged.append({
            "strategy": name,
            "usage_count": item.get("cnt", 0),
            "avg_score": round(item.get("avg_score", 0), 4),
            "weight": round(strategy_weights.get(name, 0), 4),
        })

    # 补充实时权重数据
    for name, w in strategy_weights.items():
        if name not in seen:
            merged.append({
                "strategy": name,
                "usage_count": 0,
                "avg_score": round(w, 4),
                "weight": round(w, 4),
            })

    merged.sort(key=lambda x: x["avg_score"], reverse=True)

    return {
        "ranking": merged,
        "top_strategy": merged[0]["strategy"] if merged else "N/A",
        "total_strategies": len(merged),
        "live_rank": strategy_rank[:5],
    }


def tool_get_round_history(args: dict) -> dict:
    """
    获取跨轮次优化历史。
    可选参数：task_name（筛选特定任务名）
    """
    task_name = args.get("task_name", "")
    path = "/api/autorun/rounds"
    if task_name:
        path += f"?name={urllib.parse.quote(task_name)}"
    data = _get(path)
    if isinstance(data, list):
        return {
            "rounds": data,
            "total_rounds": len(data),
            "best_round": max(data, key=lambda r: r.get("best_score", 0)) if data else None,
        }
    return data


def tool_get_logs(args: dict) -> dict:
    """
    获取最新进化日志。
    可选参数：n（条数，默认20）
    """
    n = int(args.get("n", 20))
    snap = _get("/api/evolve")
    if "error" in snap:
        return snap

    logs = snap.get("logs", [])
    live_logs = snap.get("live", {}).get("recent_logs", [])

    # 合并并去重
    all_logs = live_logs + logs
    all_logs = all_logs[:n]

    return {
        "logs": all_logs,
        "count": len(all_logs),
        "status": snap.get("status"),
    }


def tool_run_benchmark(args: dict) -> dict:
    """
    触发基准测试。
    可选参数：benchmark_type（parallel/bohb/pbt/warmstart，默认 parallel）
    """
    btype = args.get("benchmark_type", "parallel")
    path_map = {
        "parallel": "/api/parallel/benchmark",
        "bohb": "/api/bohb/benchmark",
        "pbt": "/api/pbt/benchmark",
        "warmstart": "/api/warmstart/test",
    }
    path = path_map.get(btype, "/api/parallel/benchmark")
    result = _get(path, timeout=180)
    result["benchmark_type"] = btype
    result["note"] = "基准测试已触发，结果见上方。"
    return result


# ─────────────────────────────────────────────────────────────────────────────
# MCP 协议实现（stdio JSON-RPC 2.0）
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = {
    "get_status": {
        "fn": tool_get_status,
        "description": "获取 AutoResearch 服务当前运行状态（是否在线、进化/自动运行引擎是否启动）",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_evolve_summary": {
        "fn": tool_get_evolve_summary,
        "description": "获取自主进化系统摘要：当前代数、全局最优分数、策略分布、进化曲线",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_autorun_summary": {
        "fn": tool_get_autorun_summary,
        "description": "获取自动运行引擎概览：任务列表、完成数、学习分数、资源占用",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_best_config": {
        "fn": tool_get_best_config,
        "description": "获取当前最优超参数配置（genome）及 Top-5 候选方案，含人类可读解释",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_recommendations": {
        "fn": tool_get_recommendations,
        "description": "AI 决策推荐：综合分析进化状态，给出最优策略推荐、是否继续优化、超参数配置建议",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_strategy_ranking": {
        "fn": tool_get_strategy_ranking,
        "description": "获取所有优化策略排行榜（EI/UCB/PI 等），按平均得分降序排列",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "get_round_history": {
        "fn": tool_get_round_history,
        "description": "获取跨轮次优化历史数据，可按任务名筛选",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "筛选特定任务名（可选）"}
            }
        }
    },
    "get_logs": {
        "fn": tool_get_logs,
        "description": "获取最新进化日志，可指定条数",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "返回条数，默认20", "default": 20}
            }
        }
    },
    "run_benchmark": {
        "fn": tool_run_benchmark,
        "description": "触发基准测试。类型：parallel（并行对比）/ bohb（多保真度）/ pbt（早停）/ warmstart（暖启动）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "benchmark_type": {
                    "type": "string",
                    "enum": ["parallel", "bohb", "pbt", "warmstart"],
                    "description": "基准测试类型",
                    "default": "parallel"
                }
            }
        }
    },
}


def _send(obj: dict):
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle(req: dict):
    method = req.get("method", "")
    req_id = req.get("id")

    # ── initialize ────────────────────────────────────────────────────────
    if method == "initialize":
        _send({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "autoresearch-mcp",
                    "version": "1.0.0",
                    "description": "AutoResearch 超参数优化与自主进化系统的 MCP 工具服务器"
                }
            }
        })

    # ── tools/list ────────────────────────────────────────────────────────
    elif method == "tools/list":
        tools_list = []
        for name, meta in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"]
            })
        _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}})

    # ── tools/call ────────────────────────────────────────────────────────
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in TOOLS:
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"工具不存在: {tool_name}"}
            })
            return

        try:
            result = TOOLS[tool_name]["fn"](arguments)
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                    "isError": False
                }
            })
        except Exception as e:
            import traceback
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"工具执行失败: {e}\n{traceback.format_exc()}"}],
                    "isError": True
                }
            })

    # ── notifications（忽略，无需响应）──────────────────────────────────
    elif method.startswith("notifications/"):
        pass

    # ── 未知方法 ──────────────────────────────────────────────────────────
    else:
        if req_id is not None:
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"未知方法: {method}"}
            })


def main():
    print(f"[AutoResearch MCP] 服务器已启动，目标: {AR_BASE}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": f"JSON 解析错误: {e}"}})
            continue
        _handle(req)


if __name__ == "__main__":
    import urllib.parse
    main()
