#!/usr/bin/env python3
"""
Token 优化研究 - 二百轮循环（支持断点续跑）
"""
import subprocess
import random
import time
import sys
import json
from pathlib import Path
from datetime import datetime

# 所有可用主题
ALL_TOPICS = [
    "AI agent framework", "LLM benchmark evaluation", "RAG evaluation",
    "model quantization", "speculative decoding", "KV cache optimization",
    "LLM inference optimization", "AI coding assistant", "multimodal LLM",
    "transformer architecture", "AI research tool", "knowledge graph RAG",
    "LLM training optimization", "AI agent memory system", "model compression",
    "prompt engineering", "LLM fine-tuning", "vector database",
    "AI safety alignment", "neural architecture search", "LLM reasoning",
    "chain of thought", "function calling", "tool use LLM",
    "embedding models", "text to speech", "speech to text",
    "computer vision", "diffusion models", "GAN applications"
]

STATE_FILE = Path("C:/Users/wate/.qclaw/workspace/autoresearch/run_200_state.json")
TOTAL_ROUNDS = 200

def load_state():
    """加载进度状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed": 0, "reports_generated": 0, "start_time": None}

def save_state(state):
    """保存进度状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def run_round(round_num, topics):
    """运行一轮研究"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] 第 {round_num} / {TOTAL_ROUNDS} 轮")
    print(f"  主题: {', '.join(topics[:3])}...")
    
    cmd = [sys.executable, "autorun_token_opt_v2.py"] + topics
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    # 统计生成的报告
    reports_this_round = result.stdout.count("[REPORT]")
    
    print(f"  完成 - 生成 {reports_this_round} 份报告")
    
    return reports_this_round

def main():
    print("="*60)
    print("  Token 优化研究 - 二百轮循环")
    print("="*60)
    print(f"  总计: {TOTAL_ROUNDS} 轮")
    print(f"  预计时间: 3-4 小时")
    print("="*60)
    
    # 加载状态
    state = load_state()
    if state["completed"] > 0:
        print(f"\n  检测到断点，从第 {state['completed'] + 1} 轮继续")
    else:
        state["start_time"] = datetime.now().isoformat()
    
    start_round = state["completed"] + 1
    
    # 切换到脚本目录
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)
    
    try:
        for i in range(start_round, TOTAL_ROUNDS + 1):
            # 随机选 5-10 个主题
            num_topics = random.randint(5, 10)
            topics = random.sample(ALL_TOPICS, min(num_topics, len(ALL_TOPICS)))
            
            # 运行研究
            reports = run_round(i, topics)
            state["completed"] = i
            state["reports_generated"] = state.get("reports_generated", 0) + reports
            
            # 每10轮保存一次状态
            if i % 10 == 0:
                save_state(state)
                elapsed = (datetime.now() - datetime.fromisoformat(state["start_time"])).total_seconds() / 60
                avg_time = elapsed / i
                remaining = avg_time * (TOTAL_ROUNDS - i)
                print(f"\n  [进度] {i}/{TOTAL_ROUNDS} | 已生成 {state['reports_generated']} 份报告 | 预计还需 {remaining:.0f} 分钟")
            
            # 短暂休息，避免请求过快
            if i < TOTAL_ROUNDS:
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\n\n  用户中断，进度已保存")
        save_state(state)
        return
    
    # 完成
    save_state(state)
    end_time = datetime.now()
    duration = (end_time - datetime.fromisoformat(state["start_time"])).total_seconds() / 3600
    
    print("\n" + "="*60)
    print("  二百轮研究全部完成！")
    print(f"  总报告数: {state['reports_generated']}")
    print(f"  总耗时: {duration:.1f} 小时")
    print("="*60)
    
    # 清理状态文件
    if STATE_FILE.exists():
        STATE_FILE.unlink()

if __name__ == "__main__":
    main()
