#!/usr/bin/env python3
"""
Token 优化研究 - 十轮循环
每轮随机选择主题，确保多样性
"""
import subprocess
import random
import time
import sys
from pathlib import Path

# 所有可用主题
ALL_TOPICS = [
    "AI agent framework",
    "LLM benchmark evaluation", 
    "RAG evaluation",
    "model quantization",
    "speculative decoding",
    "KV cache optimization",
    "LLM inference optimization",
    "AI coding assistant",
    "multimodal LLM",
    "transformer architecture",
    "AI research tool",
    "knowledge graph RAG",
    "LLM training optimization",
    "AI agent memory system",
    "model compression",
    "prompt engineering",
    "LLM fine-tuning",
    "vector database",
    "AI safety alignment",
    "neural architecture search"
]

def run_round(round_num, topics):
    """运行一轮研究"""
    print(f"\n{'='*60}")
    print(f"  第 {round_num} / 10 轮")
    print(f"  主题: {', '.join(topics[:3])}...")
    print(f"{'='*60}\n")
    
    # 构建命令
    cmd = [sys.executable, "autorun_token_opt_v2.py"] + topics
    
    # 执行
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    print(f"\n  第 {round_num} 轮完成")
    print(f"{'='*60}\n")
    
    return result.returncode == 0

def main():
    print("="*60)
    print("  Token 优化研究 - 十轮循环")
    print("="*60)
    
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    for i in range(1, 11):
        # 每轮随机选 5-8 个主题
        num_topics = random.randint(5, 8)
        topics = random.sample(ALL_TOPICS, num_topics)
        
        success = run_round(i, topics)
        
        if not success:
            print(f"⚠️ 第 {i} 轮出错，继续下一轮...")
        
        if i < 10:
            print("  等待 3 秒...")
            time.sleep(3)
    
    print("\n" + "="*60)
    print("  🎉 十轮研究全部完成！")
    print("="*60)

if __name__ == "__main__":
    import os
    main()
