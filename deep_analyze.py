#!/usr/bin/env python3
"""
AutoResearch 深度分析器
对已有 findings 数据做深度研究分析
"""
import json, os
from pathlib import Path
from collections import Counter, defaultdict

os.environ["PYTHONIOENCODING"] = "utf-8"
FINDINGS_DIR = Path(__file__).parent / "findings"
REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

def load_topic_findings(topic_keyword: str) -> list:
    """加载某主题的所有发现"""
    all_findings = []
    for f in sorted(FINDINGS_DIR.glob("*.json")):
        if topic_keyword.lower().replace(" ", "_") in f.name.lower():
            data = json.load(open(f, encoding="utf-8"))
            all_findings.extend(data.get("findings", []))
    return all_findings

def deep_analyze(topic: str, findings: list) -> dict:
    """深度分析"""
    if not findings:
        return {}

    # 1. 按 star 排序
    github_items = [f for f in findings if f.get("source") == "github"]
    github_items.sort(key=lambda x: x.get("stars", 0), reverse=True)

    # 2. 技术分类
    categories = defaultdict(list)
    for item in github_items:
        desc = (item.get("description") or "").lower()
        title = item.get("title", "").lower()
        text = desc + " " + title

        if any(k in text for k in ["int4", "int8", "4-bit", "8-bit", "gguf", "gptq", "bnb", "bitsandbytes"]):
            categories["量化工具"].append(item)
        elif any(k in text for k in ["pruning", "sparsity", "sparse"]):
            categories["剪枝"].append(item)
        elif any(k in text for k in ["distill", "knowledge"]):
            categories["蒸馏"].append(item)
        elif any(k in text for k in ["inference", "serving", "deploy", "runtime"]):
            categories["推理部署"].append(item)
        elif any(k in text for k in ["benchmark", "evaluation", "test"]):
            categories["评测基准"].append(item)
        else:
            categories["其他"].append(item)

    # 3. 机构分析
    orgs = Counter()
    for item in github_items:
        org = item.get("title", "").split("/")[0]
        orgs[org] += 1

    # 4. star 分布
    stars_list = [item.get("stars", 0) for item in github_items]
    total_stars = sum(stars_list)
    avg_stars = total_stars // len(stars_list) if stars_list else 0

    return {
        "topic": topic,
        "total": len(findings),
        "github_count": len(github_items),
        "top5": github_items[:5],
        "categories": {k: len(v) for k, v in categories.items()},
        "top_categories": sorted(categories.items(), key=lambda x: len(x[1]), reverse=True),
        "top_orgs": orgs.most_common(5),
        "star_stats": {
            "total": total_stars,
            "avg": avg_stars,
            "max": max(stars_list) if stars_list else 0,
            "min": min(stars_list) if stars_list else 0,
        }
    }

def print_report(analysis: dict):
    """打印深度报告"""
    topic = analysis["topic"]
    print(f"\n{'='*60}")
    print(f"  深度研究报告: {topic}")
    print(f"{'='*60}")

    print(f"\n总发现: {analysis['total']} 个项目")
    print(f"Star 统计: 最高={analysis['star_stats']['max']:,} | 平均={analysis['star_stats']['avg']:,}")

    print(f"\n--- Top 5 项目 ---")
    for i, item in enumerate(analysis["top5"], 1):
        stars = item.get("stars", 0)
        title = item.get("title", "")
        desc = (item.get("description") or "")[:60]
        print(f"  {i}. {title} ({stars:,} stars)")
        print(f"     {desc}")

    print(f"\n--- 技术分类 ---")
    for cat, items in analysis["top_categories"]:
        bar = "█" * len(items)
        print(f"  {cat:<10} {bar} ({len(items)})")

    print(f"\n--- 主要机构 ---")
    for org, count in analysis["top_orgs"]:
        print(f"  {org}: {count} 个项目")

def save_markdown(analysis: dict) -> Path:
    """保存 Markdown 报告"""
    topic = analysis["topic"]
    lines = [
        f"# 深度研究报告: {topic}",
        f"",
        f"## 概览",
        f"- **总项目数**: {analysis['total']}",
        f"- **最高 Stars**: {analysis['star_stats']['max']:,}",
        f"- **平均 Stars**: {analysis['star_stats']['avg']:,}",
        f"",
        f"## Top 5 项目",
        f"",
    ]

    for i, item in enumerate(analysis["top5"], 1):
        stars = item.get("stars", 0)
        title = item.get("title", "")
        url = item.get("url", "")
        desc = item.get("description") or ""
        lines.append(f"### {i}. [{title}]({url}) ⭐{stars:,}")
        lines.append(f"{desc}")
        lines.append("")

    lines += [
        f"## 技术分类",
        f"",
    ]
    for cat, items in analysis["top_categories"]:
        lines.append(f"- **{cat}**: {len(items)} 个项目")
        for item in items[:3]:
            lines.append(f"  - {item.get('title','')} ({item.get('stars',0):,}⭐)")

    lines += [
        f"",
        f"## 主要机构",
        f"",
    ]
    for org, count in analysis["top_orgs"]:
        lines.append(f"- **{org}**: {count} 个项目")

    report = "\n".join(lines)
    fname = REPORTS_DIR / f"deep_{topic.replace(' ', '_')}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(report)
    return fname

if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "model quantization"

    print(f"Loading findings for: {topic}")
    findings = load_topic_findings(topic)

    if not findings:
        print(f"No findings found for '{topic}'")
        print("Available topics:")
        for f in sorted(FINDINGS_DIR.glob("*.json")):
            print(f"  - {f.stem}")
    else:
        analysis = deep_analyze(topic, findings)
        print_report(analysis)
        saved = save_markdown(analysis)
        print(f"\n[OK] Markdown report: {saved.name}")
