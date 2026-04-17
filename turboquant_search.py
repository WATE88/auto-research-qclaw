#!/usr/bin/env python3
"""搜索 TurboQuant 官方信息并提炼洞察"""
import os, sys, json, urllib.request, urllib.parse, re, hashlib
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

def prosearch(q, n=10):
    url = f"https://prosearch.tianji.com/search?q={urllib.parse.quote(q)}&limit={n}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"ProSearch 错误: {e}")
        return {}

def extract_insights(results):
    """从搜索结果提炼 TurboQuant 技术洞察"""
    insights = {
        "core_tech": [],
        "performance": [],
        "applications": [],
    }
    
    for item in results:
        title = item.get("title", "").lower()
        summary = item.get("summary", item.get("snippet", "")).lower()
        text = title + " " + summary
        
        # 核心技术点
        if any(kw in text for kw in ["3-bit", "three bit", "quantization", "vector"]):
            insights["core_tech"].append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": summary[:200],
            })
        
        # 性能指标
        if any(kw in text for kw in ["zero loss", "lossless", "accuracy", "throughput", "speedup"]):
            insights["performance"].append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": summary[:200],
            })
        
        # 应用场景
        if any(kw in text for kw in ["inference", "llm", "transformer", "gpu", "memory"]):
            insights["applications"].append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": summary[:200],
            })
    
    return insights

def main():
    print("=" * 60)
    print("  TurboQuant 技术洞察提炼")
    print("=" * 60)
    
    # 多维度搜索
    queries = [
        "TurboQuant Google Research KV cache quantization",
        "TurboQuant 3-bit zero loss LLM inference",
        "TurboQuant vector quantization compression algorithm",
    ]
    
    all_results = []
    for q in queries:
        print(f"\n搜索: {q}")
        data = prosearch(q)
        results = data.get("results", data.get("data", []))
        all_results.extend(results)
        print(f"  找到 {len(results)} 条结果")
    
    # 去重
    seen = set()
    unique = []
    for r in all_results:
        h = hashlib.md5(r.get("url", "").encode()).hexdigest()[:8]
        if h not in seen:
            seen.add(h)
            unique.append(r)
    
    print(f"\n去重后: {len(unique)} 条唯一结果")
    
    # 提炼洞察
    insights = extract_insights(unique)
    
    # 生成报告
    report = f"""# TurboQuant 技术洞察报告

**搜索时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
**来源**: ProSearch ({len(unique)} 条结果)

## 核心技术

"""
    for i, item in enumerate(insights["core_tech"][:5], 1):
        report += f"{i}. [{item['title'][:60]}]({item['url']})\n   {item['snippet'][:100]}...\n\n"
    
    report += "\n## 性能指标\n\n"
    for i, item in enumerate(insights["performance"][:5], 1):
        report += f"{i}. [{item['title'][:60]}]({item['url']})\n   {item['snippet'][:100]}...\n\n"
    
    report += "\n## 应用场景\n\n"
    for i, item in enumerate(insights["applications"][:5], 1):
        report += f"{i}. [{item['title'][:60]}]({item['url']})\n   {item['snippet'][:100]}...\n\n"
    
    report += """
## 对 AutoResearch 的改进建议

1. **KV Cache 量化关键词**: 新增 'KV cache', 'key-value cache', 'cache compression' 到术语词典
2. **零精度损失信号**: 将 'zero loss', 'lossless', 'zero precision loss' 加入高质量信号词（权重 +2.0）
3. **比特宽度关键词**: 新增 '3-bit', '4-bit', '8-bit', 'quantization bits' 到术语词典
4. **推理优化聚类**: 对 inference/throughput/memory 相关论文做聚类，保留最优方法

## 训练到 AutoResearch 的代码改进

```python
# 在 TECH_TERMS 中新增：
("KV缓存", "KV cache"),
("缓存压缩", "cache compression"),
("向量量化", "vector quantization"),
("零精度损失", "zero precision loss"),
("推理加速", "inference acceleration"),
("吞吐量", "throughput"),
("延迟", "latency"),

# 在 quality_signals 中新增：
"lossless": 2.0,
"zero precision": 2.5,
"throughput": 1.5,
"inference": 1.0,
```
"""
    
    # 保存报告
    out_file = "turboquant_tech_insights.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {out_file}")
    
    # 输出关键发现
    print("\n" + "=" * 60)
    print("  关键发现")
    print("=" * 60)
    print(f"核心技术: {len(insights['core_tech'])} 条")
    print(f"性能指标: {len(insights['performance'])} 条")
    print(f"应用场景: {len(insights['applications'])} 条")

if __name__ == "__main__":
    main()
