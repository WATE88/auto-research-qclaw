#!/usr/bin/env python3
"""
AutoResearch 实用工具箱 CLI v1.0
基于质量优先研究成果的实用应用
"""
import os, sys, json
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"

WORKSPACE = Path("C:/Users/Admin/.qclaw/workspace/autoresearch")
FINDINGS_DIR = WORKSPACE / "findings"

def load_topics():
    """加载所有研究主题"""
    topics = {}
    for f in FINDINGS_DIR.glob("*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                topic = data.get("topic", f.stem)
                topics[topic.lower()] = data
        except:
            pass
    return topics

def show_trending(topics, n=10):
    """显示热门主题"""
    trending = []
    for topic, data in topics.items():
        quality = data.get("quality", {})
        trending.append({
            "topic": topic,
            "score": quality.get("score", 0),
            "grade": quality.get("grade", "F"),
            "count": quality.get("total", 0)
        })
    
    trending.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"\n{'='*60}")
    print("热门主题 Top {}".format(n))
    print("="*60)
    for i, t in enumerate(trending[:n], 1):
        print(f"{i:2}. {t['topic'][:40]:<40} {t['score']:.3f} ({t['grade']}级)")
    print("="*60)

def show_stats(topics):
    """显示统计信息"""
    grades = {}
    total_score = 0
    
    for data in topics.values():
        grade = data.get("quality", {}).get("grade", "F")
        grades[grade] = grades.get(grade, 0) + 1
        total_score += data.get("quality", {}).get("score", 0)
    
    avg_score = total_score / len(topics) if topics else 0
    
    print(f"\n{'='*60}")
    print("研究统计")
    print("="*60)
    print(f"总主题数: {len(topics)}")
    print(f"平均评分: {avg_score:.3f}")
    print(f"等级分布: {grades}")
    print("="*60)

def recommend_for_use_case(topics, use_case):
    """根据使用场景推荐工具"""
    use_case = use_case.lower()
    
    # 场景映射
    scenarios = {
        "coding": ["AI coding assistant", "LLM agent tool use"],
        "research": ["AI research automation", "knowledge base RAG"],
        "deployment": ["open source LLM deployment", "AI workflow orchestration"],
        "evaluation": ["AI evaluation platform", "LLM reasoning benchmark"],
        "agent": ["AI agent memory system", "multi-agent collaboration"],
        "prompt": ["LLM prompt engineering framework"],
        "rag": ["knowledge base RAG", "RAG retrieval evaluation"],
        "benchmark": ["AI evaluation platform", "LLM reasoning benchmark"]
    }
    
    matched_topics = []
    for key, ts in scenarios.items():
        if key in use_case:
            matched_topics.extend(ts)
    
    if not matched_topics:
        print(f"未找到 '{use_case}' 的推荐场景")
        return
    
    print(f"\n{'='*60}")
    print(f"'{use_case}' 场景推荐工具")
    print("="*60)
    
    tools = []
    for topic in matched_topics:
        data = topics.get(topic.lower())
        if data:
            for f in data.get("findings", [])[:3]:
                tools.append({
                    "name": f.get("title", ""),
                    "stars": f.get("stars", 0),
                    "desc": f.get("description", "")[:80],
                    "topic": topic
                })
    
    tools.sort(key=lambda x: x["stars"], reverse=True)
    
    for i, t in enumerate(tools[:8], 1):
        print(f"{i}. {t['name']}")
        print(f"   {t['stars']} | {t['desc']}...")
    print("="*60)

def main():
    print("=" * 60)
    print("AutoResearch Toolkit v1.0")
    print("=" * 60)
    
    topics = load_topics()
    print(f"[INFO] Loaded {len(topics)} research topics")
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python research_toolkit_cli.py trending    # 热门主题")
        print("  python research_toolkit_cli.py stats       # 统计信息")
        print("  python research_toolkit_cli.py recommend <use_case>  # 推荐工具")
        print("\nUse cases: coding, research, deployment, evaluation, agent, rag, benchmark")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "trending":
        show_trending(topics)
    elif cmd == "stats":
        show_stats(topics)
    elif cmd == "recommend" and len(sys.argv) >= 3:
        recommend_for_use_case(topics, sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
