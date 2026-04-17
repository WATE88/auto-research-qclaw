"""
autoresearch_version.py
═══════════════════════════════════════════════════════════════════
实验版本管理 & Replay
───────────────────────────────────────────────────────────────────
功能：
  1. ExperimentRecord  — 单次实验的完整快照（配置/分数/代码哈希/元数据）
  2. ExperimentStore   — 基于 JSON Lines 的持久化存储（无数据库依赖）
  3. VersionManager    — 版本标签/比较/最优检索
  4. ReplayEngine      — 从历史记录精确重放任意实验
  5. REST-ready helpers — 服务器端直接调用的 dict 接口

设计原则：
  - 零外部依赖（纯 stdlib）
  - 追加写入，永不覆盖，天然审计链
  - UUID 实验 ID + 用户自定义 tag
  - 支持按 tag / score / 时间范围 / config 字段过滤
"""

from __future__ import annotations
import hashlib
import json
import os
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("version")

# 默认存储路径（与项目在同一目录）
_DEFAULT_DB = Path(__file__).parent / "experiments.jsonl"


# ══════════════════════════════════════════════════════════════════
# 1. 数据结构
# ══════════════════════════════════════════════════════════════════

@dataclass
class ExperimentRecord:
    exp_id:     str            # UUID
    ts:         float          # Unix timestamp
    tag:        str            # 用户标签，如 "baseline" / "v1.2" / "prod"
    config:     Dict           # 超参数配置快照
    score:      float          # 最终得分（最大化）
    n_iter:     int            # 实际迭代次数
    duration_s: float          # 耗时（秒）
    code_hash:  str            # 当前 autoresearch_optimizer.py 的 MD5（可选）
    meta:       Dict = field(default_factory=dict)  # 自由扩展字段
    notes:      str = ""       # 人工备注

    @classmethod
    def create(
        cls,
        config: Dict,
        score: float,
        n_iter: int = 0,
        duration_s: float = 0.0,
        tag: str = "auto",
        meta: Optional[Dict] = None,
        notes: str = "",
        code_hash: str = "",
    ) -> "ExperimentRecord":
        return cls(
            exp_id=str(uuid.uuid4()),
            ts=time.time(),
            tag=tag,
            config=config,
            score=score,
            n_iter=n_iter,
            duration_s=duration_s,
            code_hash=code_hash,
            meta=meta or {},
            notes=notes,
        )

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ExperimentRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        import datetime
        dt = datetime.datetime.fromtimestamp(self.ts).strftime("%Y-%m-%d %H:%M:%S")
        return (f"[{self.exp_id[:8]}] {dt} tag={self.tag!r:12s} "
                f"score={self.score:+.4f} iter={self.n_iter} dur={self.duration_s:.1f}s")


# ══════════════════════════════════════════════════════════════════
# 2. 持久化存储（JSON Lines）
# ══════════════════════════════════════════════════════════════════

class ExperimentStore:
    """
    线程安全的 JSONL 追加存储
    每行一条 ExperimentRecord，按 ts 递增排列
    """

    def __init__(self, path: Path = _DEFAULT_DB):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── 写 ────────────────────────────────────────────────────────

    def save(self, record: ExperimentRecord) -> str:
        """追加一条记录，返回 exp_id"""
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"[Store] saved {record.exp_id[:8]} tag={record.tag} score={record.score:.4f}")
        return record.exp_id

    def update_notes(self, exp_id: str, notes: str) -> bool:
        """更新一条记录的备注（重写整个文件，记录数少时可接受）"""
        records = self.load_all()
        found = False
        for r in records:
            if r.exp_id == exp_id:
                r.notes = notes
                found = True
                break
        if found:
            with self._lock:
                with self.path.open("w", encoding="utf-8") as f:
                    for r in records:
                        f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        return found

    # ── 读 ────────────────────────────────────────────────────────

    def load_all(self) -> List[ExperimentRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(ExperimentRecord.from_dict(json.loads(line)))
                except Exception as e:
                    logger.warning(f"[Store] 跳过损坏记录: {e}")
        return records

    def get_by_id(self, exp_id: str) -> Optional[ExperimentRecord]:
        for r in self.load_all():
            if r.exp_id == exp_id or r.exp_id.startswith(exp_id):
                return r
        return None

    def query(
        self,
        tag: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        ts_from: Optional[float] = None,
        ts_to:   Optional[float] = None,
        limit: int = 100,
        sort_by: str = "ts",      # ts / score
        ascending: bool = False,
    ) -> List[ExperimentRecord]:
        records = self.load_all()
        if tag:
            records = [r for r in records if r.tag == tag]
        if min_score is not None:
            records = [r for r in records if r.score >= min_score]
        if max_score is not None:
            records = [r for r in records if r.score <= max_score]
        if ts_from is not None:
            records = [r for r in records if r.ts >= ts_from]
        if ts_to is not None:
            records = [r for r in records if r.ts <= ts_to]
        key = (lambda r: r.ts) if sort_by == "ts" else (lambda r: r.score)
        records.sort(key=key, reverse=not ascending)
        return records[:limit]

    def best(self, tag: Optional[str] = None) -> Optional[ExperimentRecord]:
        records = self.query(tag=tag, sort_by="score", ascending=False)
        return records[0] if records else None

    def count(self) -> int:
        return len(self.load_all())


# ══════════════════════════════════════════════════════════════════
# 3. 版本管理器
# ══════════════════════════════════════════════════════════════════

class VersionManager:
    """版本标签管理、比较、导出"""

    def __init__(self, store: ExperimentStore):
        self.store = store

    def tag_best(self, tag_name: str = "best") -> Optional[str]:
        """给当前最优实验打标签（通过更新 meta）"""
        best = self.store.best()
        if not best:
            return None
        best.meta["version_tag"] = tag_name
        self.store.update_notes(best.exp_id, f"[AUTO-TAG] {tag_name}")
        return best.exp_id

    def compare(self, id1: str, id2: str) -> Optional[Dict]:
        """对比两个实验的配置差异和得分差异"""
        r1 = self.store.get_by_id(id1)
        r2 = self.store.get_by_id(id2)
        if not r1 or not r2:
            return None

        # 配置 diff
        all_keys = set(r1.config) | set(r2.config)
        diff = {}
        for k in all_keys:
            v1 = r1.config.get(k, "<missing>")
            v2 = r2.config.get(k, "<missing>")
            if v1 != v2:
                diff[k] = {"exp1": v1, "exp2": v2}

        return {
            "exp1": {"id": r1.exp_id, "tag": r1.tag, "score": r1.score},
            "exp2": {"id": r2.exp_id, "tag": r2.tag, "score": r2.score},
            "score_delta": r2.score - r1.score,
            "config_diff": diff,
            "n_changed_params": len(diff),
        }

    def leaderboard(self, top_n: int = 10) -> List[Dict]:
        """返回 Top-N 排行榜"""
        records = self.store.query(sort_by="score", ascending=False, limit=top_n)
        return [
            {
                "rank": i + 1,
                "exp_id": r.exp_id[:8],
                "tag": r.tag,
                "score": round(r.score, 4),
                "n_iter": r.n_iter,
                "duration_s": round(r.duration_s, 1),
                "ts": r.ts,
                "notes": r.notes,
            }
            for i, r in enumerate(records)
        ]

    def export_csv(self, path: str = "experiments.csv") -> str:
        """导出所有实验为 CSV"""
        import csv
        records = self.store.query(sort_by="ts", ascending=True, limit=100000)
        if not records:
            return ""
        cfg_keys = sorted({k for r in records for k in r.config})
        fields = ["exp_id", "ts", "tag", "score", "n_iter", "duration_s", "notes"] + cfg_keys
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in records:
                row = {
                    "exp_id": r.exp_id, "ts": r.ts, "tag": r.tag,
                    "score": r.score, "n_iter": r.n_iter,
                    "duration_s": r.duration_s, "notes": r.notes,
                }
                for k in cfg_keys:
                    row[k] = r.config.get(k, "")
                writer.writerow(row)
        return path


# ══════════════════════════════════════════════════════════════════
# 4. Replay 引擎
# ══════════════════════════════════════════════════════════════════

class ReplayEngine:
    """
    从历史记录精确重放任意实验
    evaluate_fn: 接受 config dict，返回 score float
    """

    def __init__(self, store: ExperimentStore, evaluate_fn: Callable[[Dict], float]):
        self.store = store
        self.evaluate_fn = evaluate_fn

    def replay(self, exp_id: str, tag_suffix: str = "replay") -> Optional[ExperimentRecord]:
        """
        用历史配置重跑一次实验，结果作为新记录保存
        """
        orig = self.store.get_by_id(exp_id)
        if not orig:
            logger.error(f"[Replay] 找不到实验 {exp_id}")
            return None
        logger.info(f"[Replay] 重放 {exp_id[:8]} config={orig.config}")
        t0 = time.time()
        try:
            score = self.evaluate_fn(orig.config)
        except Exception as e:
            logger.error(f"[Replay] 评估失败: {e}")
            return None
        dur = time.time() - t0
        new_rec = ExperimentRecord.create(
            config=orig.config,
            score=score,
            n_iter=orig.n_iter,
            duration_s=dur,
            tag=f"{orig.tag}_{tag_suffix}",
            meta={"replayed_from": orig.exp_id},
            notes=f"Replayed from {orig.exp_id[:8]}",
        )
        self.store.save(new_rec)
        delta = score - orig.score
        logger.info(f"[Replay] 完成 new={score:.4f} orig={orig.score:.4f} delta={delta:+.4f}")
        return new_rec

    def replay_best(self, tag: Optional[str] = None) -> Optional[ExperimentRecord]:
        best = self.store.best(tag=tag)
        if not best:
            return None
        return self.replay(best.exp_id)


# ══════════════════════════════════════════════════════════════════
# 5. 便捷函数（供服务器直接调用）
# ══════════════════════════════════════════════════════════════════

_default_store: Optional[ExperimentStore] = None
_default_vm:    Optional[VersionManager] = None


def get_store(path: Optional[str] = None) -> ExperimentStore:
    global _default_store
    if _default_store is None or path:
        _default_store = ExperimentStore(Path(path) if path else _DEFAULT_DB)
    return _default_store


def get_version_manager() -> VersionManager:
    global _default_vm
    if _default_vm is None:
        _default_vm = VersionManager(get_store())
    return _default_vm


def record_experiment(
    config: Dict,
    score: float,
    tag: str = "auto",
    n_iter: int = 0,
    duration_s: float = 0.0,
    notes: str = "",
) -> str:
    """一行代码记录一次实验，返回 exp_id"""
    rec = ExperimentRecord.create(
        config=config, score=score, tag=tag,
        n_iter=n_iter, duration_s=duration_s, notes=notes,
    )
    return get_store().save(rec)


def api_list(tag=None, limit=50, sort_by="score") -> Dict:
    records = get_store().query(tag=tag, sort_by=sort_by, ascending=False, limit=limit)
    return {
        "total": get_store().count(),
        "returned": len(records),
        "records": [
            {
                "exp_id": r.exp_id[:8],
                "full_id": r.exp_id,
                "ts": r.ts,
                "tag": r.tag,
                "score": round(r.score, 4),
                "n_iter": r.n_iter,
                "duration_s": round(r.duration_s, 1),
                "config": r.config,
                "notes": r.notes,
            }
            for r in records
        ],
    }


def api_leaderboard(top_n: int = 10) -> Dict:
    return {"leaderboard": get_version_manager().leaderboard(top_n=top_n)}


def api_compare(id1: str, id2: str) -> Dict:
    result = get_version_manager().compare(id1, id2)
    return result or {"error": "实验未找到"}


def api_get(exp_id: str) -> Dict:
    r = get_store().get_by_id(exp_id)
    if not r:
        return {"error": "not found"}
    return r.to_dict()


# ══════════════════════════════════════════════════════════════════
# 6. 快速演示
# ══════════════════════════════════════════════════════════════════

def demo():
    import random, tempfile
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = f.name

    store = ExperimentStore(Path(tmp))
    vm = VersionManager(store)

    # 模拟 20 次实验
    configs = [
        {"lr": round(10 ** random.uniform(-4, -1), 6),
         "batch": random.choice([16, 32, 64, 128]),
         "optimizer": random.choice(["adam", "sgd", "adamw"])}
        for _ in range(20)
    ]
    for i, cfg in enumerate(configs):
        score = -((cfg["lr"] - 0.001) ** 2) * 1000 + random.gauss(0.7, 0.1)
        rec = ExperimentRecord.create(
            config=cfg, score=score, tag=f"run_{i//5}",
            n_iter=100, duration_s=random.uniform(5, 30)
        )
        store.save(rec)

    print(f"总记录: {store.count()}")
    print("\n── 排行榜 Top5 ──")
    for row in vm.leaderboard(5):
        print(f"  #{row['rank']} [{row['exp_id']}] score={row['score']:+.4f} tag={row['tag']}")

    best = store.best()
    print(f"\n最优: {best.summary()}")

    # 对比前2名
    top2 = store.query(sort_by="score", ascending=False, limit=2)
    if len(top2) >= 2:
        cmp = vm.compare(top2[0].exp_id, top2[1].exp_id)
        print(f"\n对比Top1 vs Top2: delta={cmp['score_delta']:+.4f} 参数差异{cmp['n_changed_params']}项")

    os.unlink(tmp)
    print("\n✅ 版本管理演示通过")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
