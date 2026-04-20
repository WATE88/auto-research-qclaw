#!/usr/bin/env python3
"""
AutoResearch + Memory + MEMOS 集成模块
实现研究-记忆-笔记的完整工作流
"""
import os, sys, json, re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 路径配置
WORKSPACE = Path("C:/Users/Admin/.qclaw/workspace")
AUTORESEARCH_DIR = WORKSPACE / "autoresearch"
MEMORY_DIR = WORKSPACE / "memory"
FINDINGS_DIR = AUTORESEARCH_DIR / "findings"
REPORTS_DIR = AUTORESEARCH_DIR / "reports"

class ResearchMemoryBridge:
    """研究-记忆桥接器"""
    
    def __init__(self):
        self.findings_cache = {}
        self.load_findings()
    
    def load_findings(self):
        """加载所有研究发现"""
        for f in FINDINGS_DIR.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    topic = data.get("topic", f.stem)
                    self.findings_cache[topic.lower()] = data
            except:
                pass
        print(f"[Bridge] 已加载 {len(self.findings_cache)} 个研究发现")
    
    def research_to_memory(self, topic: str, importance: int = 4) -> str:
        """将研究成果转换为记忆条目"""
        data = self.findings_cache.get(topic.lower())
        if not data:
            return None
        
        quality = data.get("quality", {})
        findings = data.get("findings", [])[:5]  # 取前5个
        
        # 构建记忆内容
        content = f"研究主题: {topic}\n"
        content += f"质量评分: {quality.get('score', 0)} ({quality.get('grade', 'F')}级)\n\n"
        content += "核心发现:\n"
        
        for i, f in enumerate(findings, 1):
            content += f"{i}. {f.get('title', '')} ({f.get('stars', 0)} stars)\n"
            desc = f.get("description", "") or "No description"
            content += f"   {desc[:100]}...\n"
        
        # 生成标签
        tags = ["#研究", "#AI", f"#{quality.get('grade', 'F')}级"]
        
        # 分类
        category = "技术"
        if "benchmark" in topic.lower() or "evaluation" in topic.lower():
            category = "研究"
        elif "agent" in topic.lower():
            category = "项目"
        
        memory_entry = {
            "content": content,
            "tags": tags,
            "category": category,
            "importance": importance,
            "source": "autoresearch",
            "topic": topic,
            "score": quality.get("score", 0),
            "grade": quality.get("grade", "F"),
            "timestamp": datetime.now().isoformat()
        }
        
        return memory_entry
    
    def batch_convert(self, min_grade: str = "B") -> List[Dict]:
        """批量转换高质量研究到记忆"""
        grade_order = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
        min_level = grade_order.get(min_grade, 3)
        
        memories = []
        for topic, data in self.findings_cache.items():
            grade = data.get("quality", {}).get("grade", "F")
            if grade_order.get(grade, 0) >= min_level:
                memory = self.research_to_memory(topic, importance=4 if grade == "A" else 3)
                if memory:
                    memories.append(memory)
        
        return memories
    
    def save_to_memory_file(self, memories: List[Dict], filename: str = None):
        """保存记忆到记忆文件"""
        if not filename:
            filename = f"research_memories_{datetime.now().strftime('%Y%m%d')}.md"
        
        filepath = MEMORY_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 研究记忆汇总 - {datetime.now().strftime('%Y-%m-%d')}\n\n")
            f.write(f"> 自动生成自 AutoResearch，共 {len(memories)} 条高质量研究\n\n")
            
            for i, m in enumerate(memories, 1):
                f.write(f"## {i}. {m['topic']}\n\n")
                f.write(f"**标签**: {' '.join(m['tags'])}\n")
                f.write(f"**分类**: {m['category']} | **重要性**: {m['importance']}/5\n")
                f.write(f"**评分**: {m['score']} ({m['grade']}级)\n\n")
                f.write(f"```\n{m['content']}\n```\n\n")
                f.write("---\n\n")
        
        print(f"[Bridge] 已保存 {len(memories)} 条记忆到 {filepath}")
        return filepath
    
    def generate_daily_digest(self) -> str:
        """生成每日研究摘要"""
        today = datetime.now()
        
        # 获取今天的研究
        today_findings = []
        for topic, data in self.findings_cache.items():
            ts = data.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                    if dt.date() == today.date():
                        today_findings.append(data)
                except:
                    pass
        
        if not today_findings:
            return "今日暂无新研究"
        
        digest = f"# 研究日报 - {today.strftime('%Y-%m-%d')}\n\n"
        digest += f"今日完成 {len(today_findings)} 项研究\n\n"
        
        # 按评分排序
        today_findings.sort(key=lambda x: x.get("quality", {}).get("score", 0), reverse=True)
        
        for data in today_findings:
            topic = data.get("topic", "Unknown")
            quality = data.get("quality", {})
            digest += f"## {topic}\n"
            digest += f"- 评分: {quality.get('score', 0)} ({quality.get('grade', 'F')}级)\n"
            digest += f"- 项目数: {quality.get('total', 0)}\n\n"
        
        return digest
    
    def sync_to_memos_format(self, memories: List[Dict]) -> List[Dict]:
        """转换为 MEMOS 格式"""
        memos_notes = []
        for m in memories:
            note = {
                "content": f"{m['content']}\n\n{' '.join(m['tags'])}",
                "visibility": "PRIVATE",
                "resourceIdList": [],
                "relationList": []
            }
            memos_notes.append(note)
        return memos_notes


class ResearchInsights:
    """研究洞察生成器"""
    
    def __init__(self, bridge: ResearchMemoryBridge):
        self.bridge = bridge
    
    def generate_tech_trends(self, top_n: int = 5) -> str:
        """生成技术趋势报告"""
        # 按评分排序
        sorted_topics = sorted(
            self.bridge.findings_cache.items(),
            key=lambda x: x[1].get("quality", {}).get("score", 0),
            reverse=True
        )
        
        report = "# AI/LLM 技术趋势报告\n\n"
        report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        report += "## 热门主题 Top {}\n\n".format(top_n)
        
        for i, (topic, data) in enumerate(sorted_topics[:top_n], 1):
            quality = data.get("quality", {})
            report += f"{i}. **{topic}**\n"
            report += f"   - 评分: {quality.get('score', 0)} ({quality.get('grade', 'F')}级)\n"
            report += f"   - 项目数: {quality.get('total', 0)}\n\n"
        
        # 分类统计
        categories = {}
        for topic, data in self.bridge.findings_cache.items():
            grade = data.get("quality", {}).get("grade", "F")
            categories[grade] = categories.get(grade, 0) + 1
        
        report += "## 质量分布\n\n"
        for grade in ["A", "B", "C", "D", "F"]:
            if grade in categories:
                report += f"- {grade}级: {categories[grade]} 个主题\n"
        
        return report
    
    def recommend_for_project(self, project_type: str) -> List[Dict]:
        """为项目推荐相关研究"""
        project_type = project_type.lower()
        
        # 关键词映射
        keywords = {
            "agent": ["agent", "autogpt", "langchain", "crewai"],
            "rag": ["rag", "retrieval", "knowledge", "vector"],
            "evaluation": ["benchmark", "evaluation", "metric"],
            "deployment": ["deployment", "inference", "optimization"],
            "coding": ["coding", "assistant", "copilot"]
        }
        
        matched_keywords = keywords.get(project_type, [project_type])
        
        recommendations = []
        for topic, data in self.bridge.findings_cache.items():
            score = 0
            topic_lower = topic.lower()
            
            for kw in matched_keywords:
                if kw in topic_lower:
                    score += 10
            
            # 检查项目描述
            for f in data.get("findings", [])[:3]:
                desc = f.get("description", "").lower()
                for kw in matched_keywords:
                    if kw in desc:
                        score += 1
            
            if score > 0:
                recommendations.append({
                    "topic": topic,
                    "score": score,
                    "quality": data.get("quality", {}).get("score", 0),
                    "data": data
                })
        
        recommendations.sort(key=lambda x: (x["score"], x["quality"]), reverse=True)
        return recommendations[:5]


def main():
    print("=" * 60)
    print("AutoResearch + Memory + MEMOS 集成工具")
    print("=" * 60)
    
    bridge = ResearchMemoryBridge()
    insights = ResearchInsights(bridge)
    
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python research_memory_bridge.py convert    # 转换高质量研究到记忆")
        print("  python research_memory_bridge.py digest     # 生成每日摘要")
        print("  python research_memory_bridge.py trends     # 生成技术趋势报告")
        print("  python research_memory_bridge.py recommend <项目类型>  # 项目推荐")
        print("\n项目类型: agent, rag, evaluation, deployment, coding")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "convert":
        print("\n[CONVERT] 转换高质量研究 (B+ 等级)...")
        memories = bridge.batch_convert(min_grade="B")
        if memories:
            filepath = bridge.save_to_memory_file(memories)
            print(f"✅ 已保存 {len(memories)} 条记忆")
            
            # 同时生成 MEMOS 格式
            memos_notes = bridge.sync_to_memos_format(memories)
            memos_file = MEMORY_DIR / f"memos_import_{datetime.now().strftime('%Y%m%d')}.json"
            with open(memos_file, 'w', encoding='utf-8') as f:
                json.dump(memos_notes, f, ensure_ascii=False, indent=2)
            print(f"✅ MEMOS 导入文件: {memos_file}")
        else:
            print("⚠️ 没有找到高质量研究")
    
    elif cmd == "digest":
        print("\n[DIGEST] 生成每日研究摘要...")
        digest = bridge.generate_daily_digest()
        print(digest)
        
        # 保存到今日记忆文件
        today_file = MEMORY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        with open(today_file, 'a', encoding='utf-8') as f:
            f.write("\n\n" + digest)
        print(f"✅ 已追加到 {today_file}")
    
    elif cmd == "trends":
        print("\n[TRENDS] 生成技术趋势报告...")
        report = insights.generate_tech_trends(top_n=10)
        print(report)
        
        # 保存报告
        report_file = AUTORESEARCH_DIR / "reports" / f"tech_trends_{datetime.now().strftime('%Y%m%d')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已保存: {report_file}")
    
    elif cmd == "recommend" and len(sys.argv) >= 3:
        project_type = sys.argv[2]
        print(f"\n[RECOMMEND] 为 '{project_type}' 项目推荐相关研究...")
        recommendations = insights.recommend_for_project(project_type)
        
        print(f"\n找到 {len(recommendations)} 个相关研究:\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['topic']}")
            print(f"   匹配度: {rec['score']} | 质量分: {rec['quality']:.3f}")
    
    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
