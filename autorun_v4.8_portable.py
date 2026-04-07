#!/usr/bin/env python3
"""
AutoResearch v4.8 — 跨机器自动运行版本
新增功能:
  - 自动检测运行环境 (Windows/Linux/macOS)
  - 自动创建目录结构
  - 支持定时任务自动运行
  - 支持配置文件自定义主题
  - 错误恢复和重试机制
  - 跨平台路径处理
"""
import os, sys, json, time, asyncio, aiohttp, math, re, argparse, platform
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter
import logging

# ════════════════════════════════════════════════════════════════
# 环境配置
# ════════════════════════════════════════════════════════════════

os.environ["PYTHONIOENCODING"] = "utf-8"

# 自动检测脚本目录
SCRIPT_DIR = Path(__file__).parent.resolve()

# 创建目录结构
CACHE_DIR = SCRIPT_DIR / "_cache"
REPORTS_DIR = SCRIPT_DIR / "reports"
FINDINGS_DIR = SCRIPT_DIR / "findings"
TRENDS_DIR = SCRIPT_DIR / "trends"
CONFIG_DIR = SCRIPT_DIR / "config"

for d in [CACHE_DIR, REPORTS_DIR, FINDINGS_DIR, TRENDS_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 配置文件路径
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_TOPICS_FILE = CONFIG_DIR / "topics.txt"

# 日志配置
LOG_FILE = SCRIPT_DIR / "autoresearch.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AutoResearch")

# ════════════════════════════════════════════════════════════════
# 配置管理
# ════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "version": "4.8",
    "daily_topics": [
        "AI agent framework",
        "LLM evaluation benchmark",
        "RAG evaluation",
        "AI model benchmark",
        "NLP evaluation"
    ],
    "github_api": {
        "rate_limit_wait": 60,
        "max_retries": 3,
        "timeout": 15
    },
    "scoring": {
        "agent_weight": 0.20,
        "beir_weight": 0.25,
        "nlg_weight": 0.15,
        "base_weight": 0.40
    },
    "auto_run": {
        "enabled": True,
        "schedule": "09:00",
        "topics_per_run": 5
    }
}

def load_config() -> dict:
    """加载配置文件，不存在则创建默认配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"Loaded config from {CONFIG_FILE}")
                return config
        except Exception as e:
            logger.warning(f"Config load failed: {e}, using defaults")
    
    # 创建默认配置
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    logger.info(f"Created default config at {CONFIG_FILE}")
    return DEFAULT_CONFIG.copy()

def load_topics() -> list:
    """加载主题列表"""
    topics = []
    
    # 从配置文件加载
    config = load_config()
    topics.extend(config.get("daily_topics", []))
    
    # 从 topics.txt 加载
    if DEFAULT_TOPICS_FILE.exists():
        with open(DEFAULT_TOPICS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    topics.append(line)
        logger.info(f"Loaded {len(topics)} topics from {DEFAULT_TOPICS_FILE}")
    
    return list(set(topics))  # 去重

# ════════════════════════════════════════════════════════════════
# NLG 评测 (保持 v4.7 功能)
# ════════════════════════════════════════════════════════════════

class NLGEvaluator:
    @staticmethod
    def _tokenize(text: str) -> list:
        return re.findall(r'\b\w+\b', text.lower())

    @staticmethod
    def rouge_1(reference: str, hypothesis: str) -> float:
        ref_tokens = set(NLGEvaluator._tokenize(reference))
        hyp_tokens = set(NLGEvaluator._tokenize(hypothesis))
        if not ref_tokens:
            return 0.0
        return len(ref_tokens & hyp_tokens) / len(ref_tokens)

    @staticmethod
    def rouge_2(reference: str, hypothesis: str) -> float:
        def get_bigrams(text):
            tokens = NLGEvaluator._tokenize(text)
            return set(zip(tokens[:-1], tokens[1:])) if len(tokens) > 1 else set()
        ref_bg = get_bigrams(reference)
        hyp_bg = get_bigrams(hypothesis)
        if not ref_bg:
            return 0.0
        return len(ref_bg & hyp_bg) / len(ref_bg)

    @staticmethod
    def semantic_similarity(text1: str, text2: str) -> float:
        tokens1 = NLGEvaluator._tokenize(text1)
        tokens2 = NLGEvaluator._tokenize(text2)
        if not tokens1 or not tokens2:
            return 0.0
        freq1 = Counter(tokens1)
        freq2 = Counter(tokens2)
        common = set(freq1.keys()) & set(freq2.keys())
        if not common:
            return 0.0
        dot = sum(freq1[k] * freq2[k] for k in common)
        norm1 = math.sqrt(sum(v**2 for v in freq1.values()))
        norm2 = math.sqrt(sum(v**2 for v in freq2.values()))
        return dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

    @staticmethod
    def coherence_score(text: str) -> float:
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if not sentences:
            return 0.0
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        return min(avg_len / 15, 1.0) * 0.5 + 0.5 * (len(set(' '.join(sentences).split())) / len(' '.join(sentences).split()) if sentences else 0)

    @staticmethod
    def evaluate_corpus(results: list, topic: str) -> dict:
        if not results:
            return {}
        scores = {"rouge_1": [], "semantic_sim": [], "coherence": []}
        for r in results:
            title = r.get("title", "")
            desc = r.get("description", "") or ""
            scores["rouge_1"].append(NLGEvaluator.rouge_1(topic, desc))
            scores["semantic_sim"].append(NLGEvaluator.semantic_similarity(desc, topic))
            scores["coherence"].append(NLGEvaluator.semantic_similarity(title, desc))
        return {
            "rouge_1_avg": sum(scores["rouge_1"]) / len(scores["rouge_1"]),
            "semantic_sim_avg": sum(scores["semantic_sim"]) / len(scores["semantic_sim"]),
            "coherence_avg": sum(scores["coherence"]) / len(scores["coherence"]),
        }

# ════════════════════════════════════════════════════════════════
# Agent 评测 (保持 v4.7 功能)
# ════════════════════════════════════════════════════════════════

class AgentEvaluator:
    TOOL_KW = ["tool", "api", "function", "plugin", "integration", "web", "search", "browser", "file", "database"]
    REASONING_KW = ["reason", "think", "plan", "chain", "step", "stage", "phase"]
    AUTONOMY_KW = ["autonomous", "auto", "self-supervised", "self-improve", "learn", "adapt"]

    @staticmethod
    def task_completion_score(results: list, topic: str) -> float:
        if not results:
            return 0.0
        scores = []
        topic_words = set(topic.lower().split())
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            relevance = len(topic_words & set(text.split())) / len(topic_words) if topic_words else 0
            actionable = any(kw in text for kw in ["tutorial", "guide", "example", "how to", "implement", "framework"])
            complete = any(kw in text for kw in ["complete", "full", "end-to-end", "pipeline", "workflow"])
            scores.append(relevance * 0.5 + (0.3 if actionable else 0.1) + (0.2 if complete else 0.1))
        return sum(scores) / len(scores)

    @staticmethod
    def tool_use_score(results: list) -> float:
        if not results:
            return 0.0
        scores = []
        for r in results:
            desc = (r.get("description") or "").lower()
            tool_count = sum(1 for kw in AgentEvaluator.TOOL_KW if kw in desc)
            scores.append(min(tool_count / 3, 1.0))
        return sum(scores) / len(scores)

    @staticmethod
    def reasoning_depth_score(results: list) -> float:
        if not results:
            return 0.0
        scores = []
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            reasoning_count = sum(1 for kw in AgentEvaluator.REASONING_KW if kw in text)
            scores.append(min(reasoning_count / 3, 1.0))
        return sum(scores) / len(scores)

    @staticmethod
    def autonomy_score(results: list) -> float:
        if not results:
            return 0.0
        scores = []
        for r in results:
            desc = (r.get("description") or "").lower()
            autonomy_count = sum(1 for kw in AgentEvaluator.AUTONOMY_KW if kw in desc)
            scores.append(min(autonomy_count / 2, 1.0))
        return sum(scores) / len(scores)

    @staticmethod
    def evaluate(results: list, topic: str) -> dict:
        return {
            "task_completion": round(AgentEvaluator.task_completion_score(results, topic), 4),
            "tool_use": round(AgentEvaluator.tool_use_score(results), 4),
            "reasoning_depth": round(AgentEvaluator.reasoning_depth_score(results), 4),
            "autonomy": round(AgentEvaluator.autonomy_score(results), 4),
        }

# ════════════════════════════════════════════════════════════════
# BEIR 检索指标
# ════════════════════════════════════════════════════════════════

class RetrievalMetrics:
    @staticmethod
    def relevance_scores(results: list, query: str) -> list:
        query_words = set(query.lower().split())
        expansions = {"llm": ["language model", "gpt"], "ai": ["artificial intelligence"], "benchmark": ["evaluation", "metric"]}
        expanded = query_words.copy()
        for word in list(query_words):
            expanded.update(expansions.get(word, []))
        scores = []
        for r in results:
            text = ((r.get("title") or "") + " " + (r.get("description") or "")).lower()
            text_words = set(text.split())
            exact = len(query_words & text_words)
            semantic = len(expanded & text_words) - exact
            title_match = any(qw in (r.get("title") or "").lower() for qw in query_words)
            scores.append(exact * 1.0 + semantic * 0.5 + (1.0 if title_match else 0.0))
        return scores

    @staticmethod
    def dcg(scores: list) -> float:
        return sum(s / math.log2(i + 2) for i, s in enumerate(scores[:10]))

    @staticmethod
    def ndcg(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0
        dcg = RetrievalMetrics.dcg(scores)
        idcg = RetrievalMetrics.dcg(sorted(scores, reverse=True))
        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def map_score(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        if not scores:
            return 0.0
        positions = [i+1 for i, s in enumerate(scores) if s >= 0.5]
        if not positions:
            return 0.0
        return sum((positions.index(p)+1)/p for p in positions) / len(positions)

    @staticmethod
    def mrr(results: list, query: str) -> float:
        scores = RetrievalMetrics.relevance_scores(results, query)
        for i, s in enumerate(scores):
            if s >= 0.5:
                return 1.0 / (i + 1)
        return 0.0

# ════════════════════════════════════════════════════════════════
# 综合评分
# ════════════════════════════════════════════════════════════════

class QualityScorer:
    @staticmethod
    def score(findings: list, topic: str = "") -> dict:
        if not findings:
            return {"total": 0, "quality_score": 0, "grade": "F", "dimensions": {}}
        
        n = len(findings)
        
        # 基础维度
        authority = sum(0.9 if f.get("source") == "github" else 0.5 for f in findings) / n
        stars = [f.get("stars", 0) for f in findings if f.get("stars", 0) > 0]
        star_score = sum(min(s / max(stars), 1.0) for s in stars) / len(stars) if stars else 0
        sources = Counter(f.get("source", "unknown") for f in findings)
        diversity = 1 - sum((c / n) ** 2 for c in sources.values())
        coverage = min(n / 20, 1.0)
        
        # BEIR
        ndcg = RetrievalMetrics.ndcg(findings, topic)
        map_s = RetrievalMetrics.map_score(findings, topic)
        mrr = RetrievalMetrics.mrr(findings, topic)
        
        # NLG
        nlg = NLGEvaluator.evaluate_corpus(findings, topic)
        rouge_1 = nlg.get("rouge_1_avg", 0)
        semantic_sim = nlg.get("semantic_sim_avg", 0)
        
        # Agent
        agent = AgentEvaluator.evaluate(findings, topic)
        task_completion = agent.get("task_completion", 0)
        tool_use = agent.get("tool_use", 0)
        reasoning = agent.get("reasoning_depth", 0)
        autonomy = agent.get("autonomy", 0)
        
        # 综合评分
        final_score = (
            authority * 0.10 + star_score * 0.05 + diversity * 0.05 + coverage * 0.05 +
            ndcg * 0.20 + map_s * 0.10 + mrr * 0.05 +
            rouge_1 * 0.10 + semantic_sim * 0.05 +
            task_completion * 0.15 + tool_use * 0.05 + reasoning * 0.03 + autonomy * 0.02
        )
        
        # 等级
        grade = "A" if final_score >= 0.70 else "B" if final_score >= 0.55 else "C" if final_score >= 0.40 else "D" if final_score >= 0.25 else "F"
        
        return {
            "total": n,
            "quality_score": round(final_score, 3),
            "grade": grade,
            "dimensions": {
                "authority": round(authority, 3), "star_power": round(star_score, 3),
                "diversity": round(diversity, 3), "coverage": round(coverage, 3),
                "ndcg": round(ndcg, 3), "map": round(map_s, 3), "mrr": round(mrr, 3),
                "rouge_1": round(rouge_1, 3), "semantic_sim": round(semantic_sim, 3),
                "task_completion": round(task_completion, 3), "tool_use": round(tool_use, 3),
                "reasoning_depth": round(reasoning, 3), "autonomy": round(autonomy, 3),
            }
        }

# ════════════════════════════════════════════════════════════════
# API 客户端 (带重试机制)
# ════════════════════════════════════════════════════════════════

class APIClient:
    def __init__(self, config: dict):
        self.session = None
        self.config = config
        self.cache_file = CACHE_DIR / "api_cache.json"
        self.cache = self._load_cache()
        self.rate_limited = False
        self.last_request_time = 0

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                data = json.load(open(self.cache_file))
                now = time.time()
                return {k: v for k, v in data.items() if now - v.get("_cached_at", 0) < 7 * 86400}
            except:
                return {}
        return {}

    def _save_cache(self):
        json.dump(self.cache, open(self.cache_file, 'w'), indent=2)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": f"AutoResearch/{self.config.get('version', '4.8')} (educational)"}
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def search_github(self, query: str, limit: int = 20) -> list:
        # 检查缓存
        key = f"github:{query}:{limit}"
        if key in self.cache:
            data = self.cache[key].get("data", [])
            logger.info(f"[CACHE] GitHub: {query} -> {len(data)} items")
            return data
        
        # 检查限流
        if self.rate_limited:
            wait_time = self.config.get("github_api", {}).get("rate_limit_wait", 60)
            elapsed = time.time() - self.last_request_time
            if elapsed < wait_time:
                logger.warning(f"[RATE_LIMIT] Waiting {wait_time - elapsed:.0f}s...")
                await asyncio.sleep(wait_time - elapsed)
            self.rate_limited = False
        
        # 请求间隔
        min_interval = 2.0
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        
        # 发送请求
        max_retries = self.config.get("github_api", {}).get("max_retries", 3)
        timeout = self.config.get("github_api", {}).get("timeout", 15)
        
        for attempt in range(max_retries):
            try:
                self.last_request_time = time.time()
                url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
                
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = [{
                            "title": item.get("full_name", ""),
                            "url": item.get("html_url", ""),
                            "description": item.get("description", ""),
                            "stars": item.get("stargazers_count", 0),
                            "source": "github"
                        } for item in data.get("items", [])[:limit]]
                        
                        self.cache[key] = {"data": results, "_cached_at": time.time()}
                        self._save_cache()
                        logger.info(f"[OK] GitHub: {query} -> {len(results)} items")
                        return results
                    
                    elif resp.status == 403:
                        logger.warning(f"[RATE_LIMIT] GitHub API rate limited")
                        self.rate_limited = True
                        await asyncio.sleep(self.config.get("github_api", {}).get("rate_limit_wait", 60))
                        continue
                    
                    else:
                        logger.error(f"[ERROR] GitHub HTTP {resp.status}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"[TIMEOUT] GitHub request (attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"[ERROR] GitHub: {e}")
                await asyncio.sleep(3)
        
        return []

# ════════════════════════════════════════════════════════════════
# 研究函数
# ════════════════════════════════════════════════════════════════

@dataclass
class ResearchResult:
    topic: str
    findings: list
    quality: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self) -> Path:
        # 安全的文件名
        safe_topic = re.sub(r'[\\/*?:"<>|]', '_', self.topic)
        fname = FINDINGS_DIR / f"{safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump({
                "topic": self.topic,
                "timestamp": self.timestamp,
                "findings": self.findings,
                "quality": self.quality
            }, f, indent=2, ensure_ascii=False)
        return fname

async def research_topic(topic: str, config: dict) -> ResearchResult:
    logger.info(f"\n{'='*60}")
    logger.info(f"Research: {topic}")
    logger.info(f"{'='*60}")
    
    async with APIClient(config) as client:
        findings = await client.search_github(topic, 20)
    
    quality = QualityScorer.score(findings, topic)
    result = ResearchResult(topic=topic, findings=findings, quality=quality)
    saved = result.save()
    
    dims = quality.get("dimensions", {})
    logger.info(f"Grade: {quality['grade']} | Score: {quality['quality_score']:.3f}")
    logger.info(f"[Agent] task={dims.get('task_completion',0):.3f} tool={dims.get('tool_use',0):.3f}")
    logger.info(f"[BEIR] NDCG={dims.get('ndcg',0):.3f} MAP={dims.get('map',0):.3f}")
    logger.info(f"Saved: {saved.name}")
    
    return result

# ════════════════════════════════════════════════════════════════
# 自动运行
# ════════════════════════════════════════════════════════════════

async def auto_run(config: dict):
    """自动运行研究任务"""
    auto_config = config.get("auto_run", {})
    if not auto_config.get("enabled", True):
        logger.info("Auto-run disabled")
        return
    
    topics = load_topics()
    topics_per_run = auto_config.get("topics_per_run", 5)
    
    logger.info(f"Auto-run starting with {min(len(topics), topics_per_run)} topics")
    
    for i, topic in enumerate(topics[:topics_per_run]):
        logger.info(f"\n[{i+1}/{min(len(topics), topics_per_run)}] Processing: {topic}")
        try:
            await research_topic(topic, config)
        except Exception as e:
            logger.error(f"Failed: {e}")
        await asyncio.sleep(3)  # 间隔
    
    logger.info("\n" + "="*60)
    logger.info("Auto-run completed")

# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AutoResearch v4.8 - Portable Cross-Platform")
    parser.add_argument("--topic", "-t", default="", help="Single topic to research")
    parser.add_argument("--auto", "-a", action="store_true", help="Auto-run with config topics")
    parser.add_argument("--daily", "-d", action="store_true", help="Run daily topics")
    parser.add_argument("--regrade", action="store_true", help="Re-score existing findings")
    parser.add_argument("--config", "-c", default="", help="Path to config file")
    parser.add_argument("--init", action="store_true", help="Initialize directories and config")
    args = parser.parse_args()
    
    # 初始化
    if args.init:
        logger.info("Initializing AutoResearch v4.8...")
        config = load_config()
        if not DEFAULT_TOPICS_FILE.exists():
            with open(DEFAULT_TOPICS_FILE, 'w', encoding='utf-8') as f:
                f.write("# AutoResearch Topics\n")
                f.write("# One topic per line, lines starting with # are ignored\n\n")
                f.write("\n".join(DEFAULT_CONFIG["daily_topics"]))
            logger.info(f"Created {DEFAULT_TOPICS_FILE}")
        logger.info("Initialization complete")
        return
    
    # 加载配置
    config = load_config()
    
    # 重评分
    if args.regrade:
        logger.info("Re-scoring with v4.8...")
        for f in sorted(FINDINGS_DIR.glob("*.json")):
            try:
                data = json.load(open(f, encoding="utf-8"))
                topic = data.get("topic", f.stem)
                findings = data.get("findings", [])
                if not findings:
                    continue
                quality = QualityScorer.score(findings, topic)
                logger.info(f"[{quality['grade']}] {topic[:35]:<35} {quality['quality_score']:.3f}")
            except Exception as e:
                logger.error(f"[ERROR] {f.name}: {e}")
        return
    
    # 单主题
    if args.topic:
        asyncio.run(research_topic(args.topic, config))
        return
    
    # 自动运行
    if args.auto or args.daily:
        asyncio.run(auto_run(config))
        return
    
    # 默认帮助
    print("AutoResearch v4.8 - Portable Cross-Platform")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Script Dir: {SCRIPT_DIR}")
    print(f"Findings: {len(list(FINDINGS_DIR.glob('*.json')))} files")
    print("\nUsage:")
    print("  python autorun_v4.8_portable.py --init              # Initialize")
    print("  python autorun_v4.8_portable.py --topic 'AI agents' # Single topic")
    print("  python autorun_v4.8_portable.py --auto             # Auto-run")
    print("  python autorun_v4.8_portable.py --daily            # Daily topics")
    print("  python autorun_v4.8_portable.py --regrade          # Re-score findings")

if __name__ == "__main__":
    main()
