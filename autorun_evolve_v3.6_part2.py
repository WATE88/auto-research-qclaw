#!/usr/bin/env python3
"""
AutoResearch v3.6 — Part 2: 统一引擎 + HTML 仪表盘
"""
import os, sys, json, time, random, asyncio, aiohttp
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List

# ════════════════════════════════════════════════════════════════
# 统一进化引擎 (v3.6 增强版)
# ════════════════════════════════════════════════════════════════

@dataclass
class ResearchConfig:
    """研究配置"""
    sources: list = field(default_factory=lambda: ["prosearch", "hackernews"])
    depth: str = "quick"
    
    def to_dict(self):
        return {'sources': self.sources, 'depth': self.depth}

@dataclass
class ResearchResult:
    """研究结果"""
    round_num: int
    config: ResearchConfig
    total_findings: int
    diversity_score: float
    value: float
    sources_data: Dict[str, List[Dict]] = field(default_factory=dict)
    findings: List[Dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

class UnifiedResearchEngine:
    """统一研究引擎 (v3.6 增强版)"""
    
    def __init__(self, topic, mode="karpathy"):
        self.topic = topic
        self.mode = mode
        self.history = []
        self.best_result = None
        self.stall_count = 0
        
        self.param_space = {
            'num_sources': (2, 6, 'int'),
            'depth_level': (0, 2, 'int'),
        }
        self.optimizer = None  # 从 part1 导入
        self.explorer = None
    
    def suggest_config(self, round_num=1, total_rounds=3):
        if self.mode == "bayesian":
            return self._suggest_bayesian()
        else:
            return self._suggest_karpathy(round_num, total_rounds)
    
    def _suggest_karpathy(self, round_num, total_rounds):
        explore_phase = round_num <= max(1, total_rounds // 2)
        all_sources = ["prosearch", "hackernews", "arxiv", "github", "reddit", "producthunt"]
        
        if explore_phase:
            sources = all_sources[:3]
            depth = "quick" if round_num == 1 else "standard"
        else:
            sources = all_sources[:4]
            depth = "deep"
        
        return ResearchConfig(sources=sources, depth=depth)
    
    def _suggest_bayesian(self):
        # 简化版，实际从 part1 导入
        all_sources = ["prosearch", "hackernews", "arxiv", "github", "reddit", "producthunt"]
        return ResearchConfig(sources=all_sources[:4], depth="standard")
    
    def _calculate_diversity(self, findings: List[Dict]) -> float:
        if not findings:
            return 0.0
        source_counts = {}
        for f in findings:
            src = f.get('source', 'unknown')
            source_counts[src] = source_counts.get(src, 0) + 1
        total = len(findings)
        diversity = 1 - sum((c/total)**2 for c in source_counts.values())
        return diversity
    
    def observe(self, result):
        self.history.append(result)
        if self.best_result is None or result.value > self.best_result.value:
            self.best_result = result
            self.stall_count = 0
        else:
            self.stall_count += 1
    
    def should_stop(self, stall_threshold=2):
        return self.stall_count >= stall_threshold

# ════════════════════════════════════════════════════════════════
# HTML 仪表盘生成器
# ════════════════════════════════════════════════════════════════

class HTMLDashboard:
    """HTML 仪表盘生成器"""
    
    @staticmethod
    def generate(results: List[ResearchResult], topic: str, output_path: Path):
        total_findings = sum(r.total_findings for r in results)
        avg_diversity = sum(r.diversity_score for r in results) / len(results) if results else 0
        best_value = max((r.value for r in results), default=0)
        
        source_counts = {}
        for r in results:
            for source in r.config.sources:
                source_counts[source] = source_counts.get(source, 0) + 1
        
        chart_data = json.dumps([{
            'round': r.round_num,
            'findings': r.total_findings,
            'diversity': round(r.diversity_score, 2),
            'value': round(r.value, 2)
        } for r in results])
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AutoResearch v3.6 - {topic}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #38bdf8; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #1e293b; padding: 20px; border-radius: 12px; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #38bdf8; }}
        .chart-container {{ background: #1e293b; padding: 20px; border-radius: 12px; margin: 20px 0; }}
        .source-tag {{ display: inline-block; padding: 4px 12px; background: #334155; border-radius: 20px; margin: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AutoResearch v3.6</h1>
        <p>Topic: {topic} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div>Total Findings</div>
                <div class="stat-value">{total_findings}</div>
            </div>
            <div class="stat-card">
                <div>Avg Diversity</div>
                <div class="stat-value">{avg_diversity:.2f}</div>
            </div>
            <div class="stat-card">
                <div>Best Value</div>
                <div class="stat-value">{best_value:.1f}</div>
            </div>
            <div class="stat-card">
                <div>Rounds</div>
                <div class="stat-value">{len(results)}</div>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>Sources Used</h3>
            {''.join(f'<span class="source-tag">{s}: {c}</span>' for s, c in source_counts.items())}
        </div>
    </div>
    
    <script>
        const data = {chart_data};
        new Chart(document.getElementById('chart'), {{
            type: 'line',
            data: {{
                labels: data.map(d => 'R' + d.round),
                datasets: [{{
                    label: 'Findings',
                    data: data.map(d => d.findings),
                    borderColor: '#38bdf8',
                    tension: 0.4
                }}]
            }}
        }});
    </script>
</body>
</html>'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path

# ════════════════════════════════════════════════════════════════
# 控制台样式
# ════════════════════════════════════════════════════════════════
class Console:
    R, B, CYN, GRN, MAG, YEL = "\033[0m", "\033[1m", "\033[96m", "\033[92m", "\033[95m", "\033[93m"
    
    @staticmethod
    def banner(msg):
        print(f"\n{Console.CYN}{'='*70}{Console.R}\n{Console.B}{Console.CYN}  {msg}{Console.R}\n{Console.CYN}{'='*70}{Console.R}")
    @staticmethod
    def step(msg): print(f"{Console.MAG}  >> {msg}{Console.R}")
    @staticmethod
    def info(msg): print(f"{Console.CYN}  [*] {msg}{Console.R}")
    @staticmethod
    def ok(msg): print(f"{Console.GRN}  [OK] {msg}{Console.R}")
    @staticmethod
    def warn(msg): print(f"{Console.YEL}  [!] {msg}{Console.R}")

print("AutoResearch v3.6 Part 2 loaded")
