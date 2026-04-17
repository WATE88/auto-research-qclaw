"""
AutoResearch WebLearner — 网络学习收集模块
==========================================
定期从互联网搜索最新的贝叶斯优化/超参数优化领域知识，
提炼成结构化「外部知识」注入 InsightEngine，辅助进化迭代。

工作流：
  1. [定时触发]  每 WEB_LEARN_INTERVAL 代（默认15代）触发一次网络学习
  2. [搜索采集]  向多个知识源发起搜索/抓取（arXiv摘要、论文博客、文档）
  3. [知识提炼]  从采集结果中提取超参数建议、策略洞见、边界收紧建议
  4. [注入应用]  将外部知识合并到 InsightEngine 的知识库，影响下一轮迭代

知识来源（按可靠性排序）：
  - arXiv 最新论文（贝叶斯优化领域）
  - GPyOpt / BoTorch / Optuna 文档中的推荐配置
  - Machine Learning Mastery 等博客摘要
  - Google Scholar 搜索结果摘要（fallback）

依赖：仅使用 Python 标准库 + urllib（无需第三方HTTP库）

作者: AutoResearch WorkBuddy集成（2026-03-25）
"""

import json
import math
import re
import sqlite3
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = DB_PATH_DEFAULT = Path(__file__).parent
DB_PATH = BASE_DIR / "evolution_monitor.db"

# ── 知识源配置 ──────────────────────────────────────────────────────────────

# arXiv API：搜索贝叶斯优化最新论文（返回 Atom XML）
ARXIV_QUERY = (
    "http://export.arxiv.org/api/query?"
    "search_query=ti:bayesian+optimization+hyperparameter"
    "&sortBy=submittedDate&sortOrder=descending&max_results=5"
)

# Optuna 文档：推荐的采样器配置（GitHub raw）
OPTUNA_SAMPLER_DOC = (
    "https://raw.githubusercontent.com/optuna/optuna/master/README.md"
)

# BoTorch GitHub README（包含推荐参数范围）
BOTORCH_README = (
    "https://raw.githubusercontent.com/pytorch/botorch/main/README.md"
)

# Scikit-Optimize 文档片段
SKOPT_DOC = (
    "https://raw.githubusercontent.com/scikit-optimize/scikit-optimize/master/README.rst"
)

# fallback：DuckDuckGo lite 搜索（HTML）
DDG_SEARCH = (
    "https://lite.duckduckgo.com/lite/?q="
    "{query}&kl=wt-wt"
)

# 请求超时（秒）
HTTP_TIMEOUT = 12

# ── 数据库：web_knowledge 表 ──────────────────────────────────────────────────

def _ensure_web_knowledge_table():
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute("""
            CREATE TABLE IF NOT EXISTS web_knowledge (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT,       -- 来源标识
                title       TEXT,       -- 标题/摘要
                raw_snippet TEXT,       -- 原始文本片段
                extracted   TEXT,       -- JSON: 提炼出的超参数建议
                generation  INTEGER,    -- 采集时的进化代数
                timestamp   TEXT,
                applied     INTEGER DEFAULT 0  -- 是否已应用到进化
            )
        """)
        # 补丁：兼容旧表缺少 applied 列的情况
        cols = [r[1] for r in con.execute("PRAGMA table_info(web_knowledge)").fetchall()]
        if "applied" not in cols:
            con.execute("ALTER TABLE web_knowledge ADD COLUMN applied INTEGER DEFAULT 0")
        con.commit()
        con.close()
    except Exception:
        pass


# ── HTTP 工具 ────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (AutoResearch-WebLearner/1.0; "
        "+https://github.com/autoresearch) Python-urllib"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch(url: str, timeout: int = HTTP_TIMEOUT) -> Optional[str]:
    """安全的 HTTP GET，返回 UTF-8 文本；超时/失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(1024 * 128)   # 最多读 128KB
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([^\s;]+)", ct)
            if m:
                charset = m.group(1).strip()
            try:
                return raw.decode(charset, errors="replace")
            except Exception:
                return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


# ── 知识提炼器 ───────────────────────────────────────────────────────────────

class KnowledgeExtractor:
    """
    从各类文本中提取对贝叶斯优化有价值的超参数建议。
    输出统一格式：
    {
        "acquisition": "EI" | "UCB" | "PI" | null,
        "normalize_y": true | false | null,
        "ucb_kappa_hint": float | null,          # 建议的 kappa 范围
        "n_candidates_hint": int | null,          # 建议的候选点数
        "key_insight": str,                       # 一句话洞见
        "confidence": float,                      # 0-1 置信度
        "source": str
    }
    """

    # 正则：从文本中捕获数值
    RE_KAPPA   = re.compile(r"kappa\s*[=:≈]\s*([\d.]+)", re.I)
    RE_N_CAND  = re.compile(r"n_candidates?\s*[=:]\s*(\d+)", re.I)
    RE_ACQ     = re.compile(r"\b(EI|UCB|PI|Expected Improvement|Upper Confidence Bound|Probability of Improvement)\b", re.I)
    RE_NORM    = re.compile(r"normalize_y\s*=\s*(True|False|1|0)", re.I)
    RE_PAPER_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
    RE_PAPER_SUMMARY = re.compile(r"<summary>(.*?)</summary>", re.S)

    ACQ_MAP = {
        "expected improvement": "EI", "ei": "EI",
        "upper confidence bound": "UCB", "ucb": "UCB",
        "probability of improvement": "PI", "pi": "PI",
    }

    def extract_arxiv(self, xml_text: str) -> list:
        """解析 arXiv Atom 返回的论文列表，提炼每篇摘要中的配置建议。"""
        results = []
        titles   = self.RE_PAPER_TITLE.findall(xml_text)
        summaries = self.RE_PAPER_SUMMARY.findall(xml_text)

        for title, summary in zip(titles, summaries):
            title   = re.sub(r"\s+", " ", title.strip())
            summary = re.sub(r"\s+", " ", summary.strip())
            rec = self._extract_from_text(summary, source=f"arXiv:{title[:60]}")
            if rec["confidence"] > 0.2:
                results.append(rec)

        return results

    def extract_readme(self, text: str, source_name: str) -> list:
        """从 README / 文档中提取配置建议段落。"""
        # 取每段文字
        paragraphs = re.split(r"\n{2,}", text)
        results = []
        keywords = ["kappa", "normalize", "acquisition", "n_candidates",
                    "hyperparameter", "bayesian", "EI", "UCB", "GP"]
        for para in paragraphs:
            if any(k.lower() in para.lower() for k in keywords):
                rec = self._extract_from_text(para, source=source_name)
                if rec["confidence"] > 0.15:
                    results.append(rec)
        return results[:3]   # 最多取3条

    def extract_ddg(self, html_text: str, query: str) -> list:
        """从 DuckDuckGo lite HTML 搜索结果中提取有意义的片段。"""
        # 去掉HTML标签
        clean = re.sub(r"<[^>]+>", " ", html_text)
        clean = re.sub(r"\s+", " ", clean)
        # 按句子切割，找包含关键词的句子
        sentences = re.split(r"[.!?。！？]\s", clean)
        results = []
        for sent in sentences[:80]:
            rec = self._extract_from_text(sent, source=f"Web搜索:{query[:30]}")
            if rec["confidence"] > 0.25:
                results.append(rec)
        return results[:5]

    def _extract_from_text(self, text: str, source: str) -> dict:
        """从任意文本片段提取配置关键词。"""
        confidence = 0.0
        rec = {
            "acquisition": None,
            "normalize_y": None,
            "ucb_kappa_hint": None,
            "n_candidates_hint": None,
            "key_insight": text[:120].strip(),
            "confidence": 0.0,
            "source": source,
        }

        # acquisition
        m = self.RE_ACQ.search(text)
        if m:
            raw = m.group(1).lower()
            rec["acquisition"] = self.ACQ_MAP.get(raw, raw.upper()[:3])
            confidence += 0.3

        # normalize_y
        m = self.RE_NORM.search(text)
        if m:
            val = m.group(1)
            rec["normalize_y"] = val.lower() in ("true", "1")
            confidence += 0.3

        # kappa
        m = self.RE_KAPPA.search(text)
        if m:
            try:
                rec["ucb_kappa_hint"] = float(m.group(1))
                confidence += 0.25
            except Exception:
                pass

        # n_candidates
        m = self.RE_N_CAND.search(text)
        if m:
            try:
                rec["n_candidates_hint"] = int(m.group(1))
                confidence += 0.2
            except Exception:
                pass

        # 基础相关性得分
        kws = ["bayesian", "gaussian", "acquisition", "optimize", "hyperparameter"]
        hits = sum(1 for k in kws if k in text.lower())
        confidence += hits * 0.05

        rec["confidence"] = round(min(confidence, 1.0), 3)
        return rec


# ── WebLearner 主类 ──────────────────────────────────────────────────────────

class WebLearner:
    """
    网络知识学习器。
    挂载到 InsightEngine 后，每 WEB_LEARN_INTERVAL 代触发一次网络学习。
    """

    WEB_LEARN_INTERVAL = 15   # 每N代触发一次网络学习
    MAX_STORED_ITEMS   = 50   # 数据库最多保留条目

    def __init__(self, insight_engine=None):
        self._insight = insight_engine
        self._extractor = KnowledgeExtractor()
        self._last_web_gen = -999
        self._web_knowledge_cache: list = []   # 最近提炼的知识
        self._lock = threading.Lock()
        self._bg_thread: Optional[threading.Thread] = None
        _ensure_web_knowledge_table()
        self._load_cached_knowledge()

    def _log(self, msg: str, level: str = "WEB"):
        try:
            self._insight._ctrl.log(f"[WebLearner] {msg}", level)
        except Exception:
            print(f"[WebLearner][{level}] {msg}")

    # ── 缓存恢复 ──────────────────────────────────────────────────────────────

    def _load_cached_knowledge(self):
        """从数据库恢复最近的知识缓存。"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute(
                "SELECT extracted FROM web_knowledge ORDER BY id DESC LIMIT 20"
            ).fetchall()
            con.close()
            items = []
            for r in rows:
                try:
                    items.append(json.loads(r[0]))
                except Exception:
                    pass
            with self._lock:
                self._web_knowledge_cache = items
            if items:
                self._log(f"历史网络知识已恢复，共 {len(items)} 条")
        except Exception:
            pass

    # ── 入口：由 InsightEngine.learn_and_apply 调用 ───────────────────────────

    def maybe_web_learn(self, current_gen: int):
        """
        检查是否需要触发网络学习；若需要则在后台线程中执行（不阻塞进化）。
        """
        if current_gen - self._last_web_gen < self.WEB_LEARN_INTERVAL:
            return
        if self._bg_thread and self._bg_thread.is_alive():
            self._log("上次网络学习尚未完成，本轮跳过")
            return

        self._last_web_gen = current_gen
        self._bg_thread = threading.Thread(
            target=self._do_web_learn,
            args=(current_gen,),
            daemon=True,
            name="WebLearner"
        )
        self._bg_thread.start()
        self._log(f"第 {current_gen} 代：后台启动网络知识采集...")

    def _do_web_learn(self, gen: int):
        """后台执行完整的网络学习流程。"""
        all_records = []

        # ── 1. arXiv 最新论文 ────────────────────────────────────────────────
        self._log("搜索 arXiv 最新论文...")
        xml = _fetch(ARXIV_QUERY, timeout=15)
        if xml:
            recs = self._extractor.extract_arxiv(xml)
            self._log(f"  arXiv: 提炼到 {len(recs)} 条知识")
            for r in recs:
                r["_data_source"] = "arxiv"
            all_records.extend(recs)
        else:
            self._log("  arXiv 抓取超时或失败", "WARN")

        # ── 2. BoTorch/Optuna README ──────────────────────────────────────────
        for url, name in [
            (BOTORCH_README, "botorch"),
            (OPTUNA_SAMPLER_DOC, "optuna"),
            (SKOPT_DOC, "skopt"),
        ]:
            text = _fetch(url, timeout=10)
            if text:
                recs = self._extractor.extract_readme(text, source_name=name)
                self._log(f"  {name}: 提炼到 {len(recs)} 条知识")
                for r in recs:
                    r["_data_source"] = name
                all_records.extend(recs)
            else:
                self._log(f"  {name} 文档抓取失败（跳过）", "DEBUG")

        # ── 3. DuckDuckGo 补充搜索（仅在前面知识不足时使用）──────────────────
        if len(all_records) < 3:
            for query in [
                "bayesian optimization best kappa EI UCB hyperparameter",
                "gaussian process normalize_y true false recommendation",
            ]:
                encoded = urllib.parse.quote(query)
                url = DDG_SEARCH.format(query=encoded)
                html = _fetch(url, timeout=12)
                if html:
                    recs = self._extractor.extract_ddg(html, query)
                    self._log(f"  DDG搜索[{query[:30]}]: {len(recs)} 条")
                    for r in recs:
                        r["_data_source"] = "duckduckgo"
                    all_records.extend(recs)

        if not all_records:
            self._log("本轮未采集到任何有效知识", "WARN")
            return

        # ── 4. 过滤 + 去重 + 存库 ────────────────────────────────────────────
        # 按置信度过滤
        valid = [r for r in all_records if r.get("confidence", 0) >= 0.2]
        # 按置信度排序
        valid.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        valid = valid[:15]   # 每次最多保留15条高质量知识

        self._log(f"采集完成：{len(all_records)} 原始 → {len(valid)} 有效条目")

        # 写入数据库
        try:
            con = sqlite3.connect(str(DB_PATH))
            for r in valid:
                con.execute(
                    """INSERT INTO web_knowledge
                       (source, title, raw_snippet, extracted, generation, timestamp, applied)
                       VALUES (?,?,?,?,?,?,0)""",
                    (
                        r.get("_data_source", "unknown"),
                        r.get("key_insight", "")[:200],
                        r.get("key_insight", ""),
                        json.dumps(r, ensure_ascii=False),
                        gen,
                        datetime.now().isoformat(),
                    )
                )
            # 保持数据库整洁：超出限制的旧记录删除
            con.execute(f"""
                DELETE FROM web_knowledge WHERE id NOT IN (
                    SELECT id FROM web_knowledge ORDER BY id DESC LIMIT {self.MAX_STORED_ITEMS}
                )
            """)
            con.commit()
            con.close()
        except Exception as e:
            self._log(f"写入 web_knowledge 失败: {e}", "WARN")

        # 更新内存缓存
        with self._lock:
            self._web_knowledge_cache = valid

        # ── 5. 立即应用到 InsightEngine ───────────────────────────────────────
        self._apply_to_insight(valid, gen)

    # ── 应用外部知识到进化引擎 ─────────────────────────────────────────────────

    def _apply_to_insight(self, records: list, gen: int):
        """
        将网络知识聚合后注入 InsightEngine 的知识库，
        并直接调整控制器的当前基因组（温和调整，不覆盖内部学习的成果）。
        """
        if not self._insight:
            return

        ctrl = self._insight._ctrl
        genome = ctrl.current_genome
        applied_items = []

        # ── A. 聚合 acquisition 建议（投票）──────────────────────────────────
        acq_votes: dict = {}
        for r in records:
            a = r.get("acquisition")
            if a and a in ("EI", "UCB", "PI"):
                acq_votes[a] = acq_votes.get(a, 0) + r.get("confidence", 0.5)
        if acq_votes:
            best_acq = max(acq_votes, key=acq_votes.get)
            # 仅当网络共识明确时才覆盖（票差要足够大）
            total_vote = sum(acq_votes.values())
            top_ratio  = acq_votes[best_acq] / total_vote
            if top_ratio >= 0.5:
                genome["acquisition"] = best_acq
                applied_items.append(f"acquisition→{best_acq}(网络共识{top_ratio:.0%})")

        # ── B. kappa 建议（加权平均）────────────────────────────────────────
        kappa_hints = [
            (r["ucb_kappa_hint"], r.get("confidence", 0.3))
            for r in records if r.get("ucb_kappa_hint") is not None
        ]
        if kappa_hints:
            w_sum = sum(w for _, w in kappa_hints)
            kappa_mean = sum(v * w for v, w in kappa_hints) / w_sum
            kappa_mean = max(0.3, min(12.0, kappa_mean))
            # 温和调整：只偏移20%（以避免过度干扰内部学习）
            old_kappa = genome.get("ucb_kappa", 2.576)
            new_kappa = round(old_kappa * 0.8 + kappa_mean * 0.2, 4)
            genome["ucb_kappa"] = new_kappa
            applied_items.append(f"ucb_kappa {old_kappa:.3f}→{new_kappa:.3f}(外部建议)")

        # ── C. normalize_y 建议（多数票）─────────────────────────────────────
        norm_votes = [r.get("normalize_y") for r in records if r.get("normalize_y") is not None]
        if len(norm_votes) >= 2:
            prefer_true = sum(1 for v in norm_votes if v)
            if prefer_true >= len(norm_votes) * 0.6:
                genome["normalize_y"] = True
                applied_items.append("normalize_y→True(网络多数建议)")
            elif prefer_true <= len(norm_votes) * 0.4:
                genome["normalize_y"] = False
                applied_items.append("normalize_y→False(网络多数建议)")

        # ── D. n_candidates 建议（加权均值）─────────────────────────────────
        nc_hints = [
            (r["n_candidates_hint"], r.get("confidence", 0.3))
            for r in records if r.get("n_candidates_hint") is not None
        ]
        if nc_hints:
            w_sum = sum(w for _, w in nc_hints)
            nc_mean = int(sum(v * w for v, w in nc_hints) / w_sum)
            nc_mean = max(100, min(2000, nc_mean))
            old_nc = genome.get("n_candidates", 512)
            # 温和调整
            new_nc = int(old_nc * 0.8 + nc_mean * 0.2)
            genome["n_candidates"] = new_nc
            applied_items.append(f"n_candidates {old_nc}→{new_nc}(外部建议)")

        # ── E. 注入知识种子（如有高质量外部建议）──────────────────────────────
        import copy
        top_recs = [r for r in records if r.get("confidence", 0) >= 0.55]
        if top_recs and hasattr(ctrl, "_elite_pool"):
            seed = copy.deepcopy(genome)
            best_acq_ext = acq_votes and max(acq_votes, key=acq_votes.get)
            if best_acq_ext:
                seed["acquisition"] = best_acq_ext
            if norm_votes:
                seed["normalize_y"] = sum(1 for v in norm_votes if v) > len(norm_votes) / 2
            seed_score = min(ctrl.best_score * 0.97, 0.90)
            ctrl._elite_pool.append((seed_score, seed))
            ctrl._elite_pool.sort(key=lambda x: x[0], reverse=True)
            ctrl._elite_pool = ctrl._elite_pool[:6]
            applied_items.append("注入外部知识种子→精英库")

        ctrl.current_genome = genome

        # 标记已应用
        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("UPDATE web_knowledge SET applied=1 WHERE generation=?", (gen,))
            con.commit()
            con.close()
        except Exception:
            pass

        if applied_items:
            self._log(f"✅ 外部知识已应用：{' | '.join(applied_items)}", "INFO")
            # ── 注册后验评估事件（5代后回来看是否有效）──────────────────────
            score_now = getattr(ctrl, "best_score", 0.0)
            sources_applied = list({r.get("_data_source", "unknown") for r in records})
            self.register_apply_event(gen, score_now, sources_applied)
        else:
            self._log("本轮外部知识未产生有效调整（置信度不足）", "DEBUG")

    # ── 查询接口：供 API 展示 ─────────────────────────────────────────────────

    def get_knowledge_summary(self) -> dict:
        """返回当前网络知识库摘要（供 API/Dashboard 展示）。"""
        with self._lock:
            cache = list(self._web_knowledge_cache)

        # 统计
        sources = {}
        acquisitions: dict = {}
        normalize_prefer: list = []
        for r in cache:
            src = r.get("_data_source", r.get("source", "unknown"))
            sources[src] = sources.get(src, 0) + 1
            a = r.get("acquisition")
            if a:
                acquisitions[a] = acquisitions.get(a, 0) + 1
            n = r.get("normalize_y")
            if n is not None:
                normalize_prefer.append(n)

        top_insights = [
            r.get("key_insight", "")[:100]
            for r in sorted(cache, key=lambda x: x.get("confidence", 0), reverse=True)[:5]
        ]

        try:
            con = sqlite3.connect(str(DB_PATH))
            db_total = con.execute("SELECT COUNT(*) FROM web_knowledge").fetchone()[0]
            last_gen = con.execute(
                "SELECT MAX(generation) FROM web_knowledge"
            ).fetchone()[0]
            con.close()
        except Exception:
            db_total, last_gen = 0, None

        return {
            "status":              "active",
            "db_total":            db_total,
            "last_fetched_gen":    self._last_web_gen,
            "last_db_gen":         last_gen,
            "cache_count":         len(cache),
            "sources_breakdown":   sources,
            "acquisition_votes":   acquisitions,
            "normalize_prefer_true": sum(1 for v in normalize_prefer if v),
            "normalize_prefer_false": sum(1 for v in normalize_prefer if not v),
            "top_insights":        top_insights,
        }

    def force_learn_now(self, gen: int = 0) -> str:
        """强制立即触发一次网络学习（API调用触发）。"""
        if self._bg_thread and self._bg_thread.is_alive():
            return "already_running"
        self._last_web_gen = -999   # 重置，确保触发
        self.maybe_web_learn(gen)
        return "started"

    # ── 后验评分追踪（KnowledgeRater）────────────────────────────────────────

    def record_post_apply_score(self, gen: int, score: float):
        """
        在应用网络知识后的第N代，记录当前分数，用于评估知识有效性。
        由 InsightEngine.learn_and_apply 每代调用。
        """
        if not hasattr(self, "_pending_eval"):
            self._pending_eval = []   # list of {gen, source_gen, source, score_before}
        if not hasattr(self, "_source_ratings"):
            self._source_ratings = {}  # source → {wins, total, avg_improvement}

        # 检查是否有等待评估的应用记录
        with self._lock:
            cache = list(self._web_knowledge_cache)

        still_pending = []
        for entry in getattr(self, "_pending_eval", []):
            wait_gens = gen - entry["applied_gen"]
            if wait_gens >= 5:
                # 足够代数后，用分数差评估
                improvement = score - entry["score_before"]
                src = entry["source"]
                if src not in self._source_ratings:
                    self._source_ratings[src] = {"wins": 0, "total": 0, "total_improvement": 0.0}
                r = self._source_ratings[src]
                r["total"] += 1
                r["total_improvement"] += improvement
                if improvement > 0:
                    r["wins"] += 1
                # 持久化到数据库
                self._save_source_rating(src, improvement)
            else:
                still_pending.append(entry)
        self._pending_eval = still_pending

    def register_apply_event(self, gen: int, score_before: float, sources: list):
        """知识应用时注册评估事件，等5代后回来看效果。"""
        if not hasattr(self, "_pending_eval"):
            self._pending_eval = []
        for src in sources:
            self._pending_eval.append({
                "applied_gen": gen,
                "score_before": score_before,
                "source": src,
            })

    def _save_source_rating(self, source: str, improvement: float):
        """持久化来源评分到 SQLite。"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            con.execute("""
                CREATE TABLE IF NOT EXISTS web_source_ratings (
                    source TEXT PRIMARY KEY,
                    total_uses INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    total_improvement REAL DEFAULT 0.0,
                    last_updated TEXT
                )
            """)
            con.execute("""
                INSERT INTO web_source_ratings(source, total_uses, wins, total_improvement, last_updated)
                VALUES(?, 1, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    total_uses = total_uses + 1,
                    wins = wins + excluded.wins,
                    total_improvement = total_improvement + excluded.total_improvement,
                    last_updated = excluded.last_updated
            """, (source, 1 if improvement > 0 else 0, improvement,
                  datetime.now().isoformat()))
            con.commit()
            con.close()
        except Exception:
            pass

    def get_source_ratings(self) -> list:
        """返回来源评分排行。"""
        try:
            con = sqlite3.connect(str(DB_PATH))
            rows = con.execute("""
                SELECT source, total_uses, wins, total_improvement
                FROM web_source_ratings
                ORDER BY total_improvement DESC
            """).fetchall()
            con.close()
            result = []
            for row in rows:
                src, total, wins, imp = row
                win_rate = wins / total if total > 0 else 0.0
                avg_imp  = imp / total if total > 0 else 0.0
                result.append({
                    "source": src,
                    "total_uses": total,
                    "win_rate":   round(win_rate, 3),
                    "avg_improvement": round(avg_imp, 5),
                    "score": round(win_rate * 0.6 + min(max(avg_imp, -1), 1) * 0.4, 3),
                })
            return result
        except Exception:
            return []

    def get_knowledge_summary_v2(self) -> dict:
        """增强版知识摘要，含来源评分。"""
        base = self.get_knowledge_summary()
        base["source_ratings"] = self.get_source_ratings()
        base["pending_eval_count"] = len(getattr(self, "_pending_eval", []))
        return base


# ── InsightEngine 扩展：注入 WebLearner ──────────────────────────────────────

def attach_web_learner(insight_engine) -> Optional[WebLearner]:
    """
    将 WebLearner 挂载到已有的 InsightEngine 实例上。
    在 InsightEngine.__init__ 结束时调用，或在 SelfEvolveController 初始化时调用。
    """
    try:
        learner = WebLearner(insight_engine=insight_engine)
        insight_engine._web_learner = learner
        return learner
    except Exception as e:
        print(f"[WebLearner] 挂载失败（不影响主流程）: {e}")
        if insight_engine:
            insight_engine._web_learner = None
        return None
