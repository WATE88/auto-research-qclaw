#!/usr/bin/env python3
"""
AutoResearch 实用工具箱 v1.0
基于质量优先研究成果的实用应用
"""
import os, sys, json, re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("C:/Users/Admin/.qclaw/workspace/autoresearch")
REPORTS_DIR = WORKSPACE / "reports"
FINDINGS_DIR = WORKSPACE / "findings"

class ResearchKnowledgeBase:
    """研究知识库 - 基于 AutoResearch 成果"""
    
    def __init__(self):
        self.topics = {}
        self.load_all()
    
    def load_all(self):
        """加载所有研究成果"""
        for f in FINDINGS_DIR.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    topic = data.get("topic", f.stem)
                    self.topics[topic.lower()] = data
            except:
                pass
        print(f"[KB] 已加载 {len(self.topics)} 个研究主题")
    
    def search(self, keyword: str, top_n: int = 5):
        """搜索相关主题"""
        keyword = keyword.lower()
        matches = []
        
        for topic, data in self.topics.items():
            score = 0
            # 主题匹配
            if keyword in topic:
                score += 10
            
            # 项目匹配
            for finding in data.get("findings", [])[:10]:
                text = (finding.get("title", "") + " " + 
                       finding.get("description", "")).lower()
                if keyword in text:
                    score += 1
            
            if score > 0:
                matches.append((topic, score, data))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_n]
    
    def recommend_tools(self, use_case: str, top_n: int = 5):
        """根据使用场景推荐工具"""
        use_case = use_case.lower()
        
        # 场景映射
        scenarios = {
            "coding": ["AI coding assistant", "LLM agent tool use"],
            "research": ["AI research automation", "knowledge base RAG"],
            "deployment": ["open source LLM deployment", "AI workflow orchestration"],
            "evaluation": ["AI evaluation platform", "LLM reasoning benchmark"],
            "agent": ["AI agent memory system", "multi-agent collaboration"],
            "prompt": ["LLM prompt engineering framework"]
        }
        
        matched_topics = []
        for key, topics in scenarios.items():
            if key in use_case or use_case in key:
                matched_topics.extend(topics)
        
        if not matched_topics:
            # 模糊搜索
            return self.search(use_case, top_n)
        
        # 收集工具
        tools = []
        for topic in matched_topics:
            data = self.topics.get(topic.lower())
            if data:
                for f in data.get("findings", [])[:5]:
                    tools.append({
                        "name": f.get("title", ""),
                        "url": f.get("url", ""),
                        "stars": f.get("stars", 0),
                        "desc": f.get("description", "")[:100],
                        "topic": topic
                    })
        
        # 按 stars 排序
        tools.sort(key=lambda x: x["stars"], reverse=True)
        return tools[:top_n]
    
    def get_trending(self, top_n: int = 10):
        """获取热门主题"""
        trending = []
        for topic, data in self.topics.items():
            quality = data.get("quality", {})
            trending.append({
                "topic": topic,
                "score": quality.get("score", 0),
                "grade": quality.get("grade", "F"),
                "count": quality.get("total", 0)
            })
        
        trending.sort(key=lambda x: x["score"], reverse=True)
        return trending[:top_n]

class ProjectGenerator:
    """项目生成器 - 基于研究趋势"""
    
    def __init__(self, kb: ResearchKnowledgeBase):
        self.kb = kb
    
    def generate_idea(self, domain: str = None):
        """生成项目创意"""
        if domain:
            topics = self.kb.search(domain, 3)
        else:
            topics = [(t, 0, d) for t, d in list(self.kb.topics.items())[:3]]
        
        ideas = []
        for topic, score, data in topics:
            findings = data.get("findings", [])
            if len(findings) >= 2:
                # 组合两个热门项目
                f1, f2 = findings[0], findings[1]
                idea = {
                    "name": f"{f1['title'].split('/')[-1]}-for-{f2['title'].split('/')[-1]}",
                    "concept": f"将 {f1['title']} 的技术应用于 {f2['title']} 的场景",
                    "inspiration": [f1['title'], f2['title']],
                    "domain": topic
                }
                ideas.append(idea)
        
        return ideas
    
    def tech_stack(self, project_type: str):
        """推荐技术栈"""
        stacks = {
            "AI agent": {
                "framework": ["AutoGPT", "LangChain", "CrewAI"],
                "memory": ["MemGPT", "AutoGen"],
                "tools": ["OpenAI Function Calling", "LangChain Tools"]
            },
            "LLM app": {
                "model": ["Llama 3", "Qwen", "Mistral"],
                "deployment": ["Ollama", "vLLM", "TGI"],
                "RAG": ["LangChain", "LlamaIndex", "ChromaDB"]
            },
            "evaluation": {
                "benchmark": ["HELM", "OpenCompass", "EleutherAI LM Eval"],
                "metrics": ["ROUGE", "BERTScore", "GPT-4 Judge"]
            }
        }
        
        # 搜索相关主题补充
        related = self.kb.search(project_type, 2)
        for topic, _, data in related:
            findings = data.get("findings", [])[:3]
            for f in findings:
                name = f['title'].split('/')[-1]
                if name not in stacks.get(project_type, {}).get("framework", []):
                    stacks.setdefault(project_type, {}).setdefault("framework", []).append(name)
        
        return stacks.get(project_type, {})

def main():
    print("=" * 60)
    print("AutoResearch 实用工具箱 v1.0")
    print("=" * 60)
    
    kb = ResearchKnowledgeBase()
    generator = ProjectGenerator(kb)
    
    while True:
        print("\n[菜单]")
        print("1. 搜索研究主题")
        print("2. 推荐工具")
        print("3. 热门趋势")
        print("4. 生成项目创意")
        print("5. 技术栈推荐")
        print("0. 退出")
        
        choice = input("\n选择: ").strip()
        
        if choice == "1":
            keyword = input("搜索关键词: ").strip()
            results = kb.search(keyword, 5)
            print(f"\n找到 {len(results)} 个相关主题:")
            for topic, score, data in results:
                quality = data.get("quality", {})
                print(f"  • {topic} (评分: {quality.get('score', 0)}, {quality.get('grade', 'F')}级)")
        
        elif choice == "2":
            use_case = input("使用场景 (coding/research/deployment/evaluation/agent/prompt): ").strip()
            tools = kb.recommend_tools(use_case, 5)
            print(f"\n推荐工具 ({use_case}):")
            for i, t in enumerate(tools, 1):
                print(f"{i}. {t['name']} ({t['stars']}⭐)")
                print(f"   {t['desc']}...")
        
        elif choice == "3":
            trending = kb.get_trending(10)
            print("\n热门主题 Top 10:")
            for i, t in enumerate(trending, 1):
                print(f"{i}. {t['topic']} - {t['score']} ({t['grade']}级, {t['count']}项目)")
        
        elif choice == "4":
            domain = input("领域 (可选): ").strip() or None
            ideas = generator.generate_idea(domain)
            print("\n项目创意:")
            for idea in ideas:
                print(f"\n  💡 {idea['name']}")
                print(f"     概念: {idea['concept']}")
                print(f"     灵感来源: {', '.join(idea['inspiration'])}")
        
        elif choice == "5":
            project_type = input("项目类型 (AI agent/LLM app/evaluation): ").strip()
            stack = generator.tech_stack(project_type)
            print(f"\n{project_type} 技术栈推荐:")
            for category, items in stack.items():
                print(f"  [{category}] {', '.join(items[:5])}")
        
        elif choice == "0":
            print("再见!")
            break

if __name__ == "__main__":
    main()
