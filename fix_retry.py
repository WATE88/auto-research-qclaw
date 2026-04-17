"""修复 autorun_evolve.py 的数据源重试机制"""
import re

path = r'C:\Users\Admin\.qclaw\workspace\autoresearch\autorun_evolve.py'
with open(path, encoding='utf-8') as f:
    content = f.read()

changes = 0

# ── 1. fetch_prosearch: 加重试 ────────────────────────────────
old_ps = (
    'def fetch_prosearch(keyword: str, count=10, days=30) -> list[dict]:\n'
    '    import urllib.request\n'
    '    ck = _mkcache("prosearch", kw=keyword, c=count, d=days)\n'
    '    cached = _cache_get(ck, ttl=900)\n'
    '    if cached is not None: return cached\n'
    '    url = f"http://localhost:{PORT}/proxy/prosearch/search"\n'
    '    body = json.dumps({"keyword": keyword, "from_time": int(time.time()) - days*86400, "cnt": count}).encode()\n'
    '    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})\n'
    '    results = []\n'
    '    try:\n'
    '        with urllib.request.urlopen(req, timeout=25) as r:\n'
    '            res = json.loads(r.read().decode("utf-8", errors="replace"))\n'
    '            if res.get("success") and res.get("data", {}).get("docs"):\n'
    '                results = res["data"]["docs"]\n'
    '    except Exception as e:\n'
    '        C.warn(f"ProSearch 失败: {e}")\n'
    '    _cache_set(ck, results)\n'
    '    return results'
)
new_ps = (
    'def fetch_prosearch(keyword: str, count=10, days=30) -> list[dict]:\n'
    '    import urllib.request, time as _time\n'
    '    ck = _mkcache("prosearch", kw=keyword, c=count, d=days)\n'
    '    cached = _cache_get(ck, ttl=900)\n'
    '    if cached is not None: return cached\n'
    '    url = f"http://localhost:{PORT}/proxy/prosearch/search"\n'
    '    results = []\n'
    '    last_err = ""\n'
    '    for attempt in range(4):\n'
    '        body = json.dumps({"keyword": keyword, "from_time": int(time.time()) - days*86400, "cnt": count}).encode()\n'
    '        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})\n'
    '        try:\n'
    '            with urllib.request.urlopen(req, timeout=30) as r:\n'
    '                res = json.loads(r.read().decode("utf-8", errors="replace"))\n'
    '                if res.get("success") and res.get("data", {}).get("docs"):\n'
    '                    results = res["data"]["docs"]\n'
    '            break\n'
    '        except Exception as e:\n'
    '            last_err = str(e)\n'
    '            if attempt < 3:\n'
    '                wait = (2 ** attempt) + 1\n'
    '                C.step(f"ProSearch 重试 {attempt+2}/4 ({last_err[:50]})...")\n'
    '                _time.sleep(wait)\n'
    '    if not results:\n'
    '        C.warn(f"ProSearch 失败（已重试4次）: {last_err[:80]}")\n'
    '    _cache_set(ck, results)\n'
    '    return results'
)
if old_ps in content:
    content = content.replace(old_ps, new_ps)
    print("1. fetch_prosearch: 重试机制已添加")
    changes += 1
else:
    print("1. fetch_prosearch: 模式未找到（可能已修改过）")

# ── 2. fetch_github: 修复语法错误 + 加重试 ────────────────────
old_gh = (
    "    req = urllib.request.Request(url, headers={\"User-Agent\": \"Mozilla/5.0\"})\n"
    "            with urllib.request.urlopen(req, timeout=20) as r:\n"
    "                html = r.read().decode(\"utf-8\", errors=\"replace\")\n"
    "            for a in re.findall(r\"<article class=\\\"Box-row\\\">(.*?)</article>\", html, re.DOTALL)[:15]:\n"
    "                t = re.search(r'href=\"(/[^\\\"/]+/[^\\\"/]+)\\\"[^>]*>\\s*([^<]{3,200})', a)\n"
    "                d = re.search(r\"<p[^>]*>([^<\\n]{10,300})\", a)\n"
    "                s = re.search(r\"(\\d[\\d,]*)\\s+stars today\", a)\n"
    "                if t:\n"
    "                    items.append({\"title\": f\"github: {t.group(2).strip()}\",\n"
    "                                   \"url\": \"https://github.com\" + t.group(1),\n"
    "                                   \"type\": \"project\",\n"
    "                                   \"stars_today\": (s.group(1).replace(\",\",\"\") if s else \"0\"),\n"
    "                                   \"description\": (d.group(1).strip() if d else \"\"), \"source\": \"GitHub\"})\n"
    "            break  # 成功则退出重试循环\n"
    "        except Exception as e:\n"
    "            last_err = str(e)\n"
    "            if attempt < 2:\n"
    "                _time.sleep(2 ** attempt)  # 指数退避: 2s, 4s\n"
    "                C.step(f\"GitHub 重试 {attempt+2}/3 ({last_err[:40]})...\")\n"
    "    if not items:\n"
    "        C.warn(f\"GitHub 失败（已重试3次）: {last_err[:60]}\")\n"
    "    _cache_set(ck, items); return items[:limit]"
)

# Simpler approach: just rewrite the function entirely
old_gh_fn = "def fetch_github_trending(lang=\"\", limit=8) -> list[dict]:"
new_gh_fn = (
    'def fetch_github_trending(lang="", limit=8) -> list[dict]:\n'
    '    import re, urllib.request, time as _time\n'
    '    ck = _mkcache("gh", l=lang)\n'
    '    cached = _cache_get(ck, ttl=900)\n'
    '    if cached is not None: return cached[:limit]\n'
    '    items = []\n'
    '    last_err = ""\n'
    '    for attempt in range(4):\n'
    '        try:\n'
    '            url = f"https://github.com/trending{\'/" + '" + lang + "if lang else \'" + '"}{...}"'
)

# Use sed-like approach via finding the function boundaries
# Find fetch_github_trending function
gh_start = content.find("def fetch_github_trending(")
gh_next = content.find("\ndef fetch_", gh_start + 1)
if gh_start != -1 and gh_next != -1:
    old_fn = content[gh_start:gh_next]
    new_fn = (
        'def fetch_github_trending(lang="", limit=8) -> list[dict]:\n'
        '    import re, urllib.request, time as _time\n'
        '    ck = _mkcache("gh", l=lang)\n'
        '    cached = _cache_get(ck, ttl=900)\n'
        '    if cached is not None: return cached[:limit]\n'
        '    items = []\n'
        '    last_err = ""\n'
        '    for attempt in range(4):\n'
        '        try:\n'
        '            url = f"https://github.com/trending{\'/" + '" + lang + " if lang else \'" + '"}"\n'
        '            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})\n'
        '            with urllib.request.urlopen(req, timeout=25) as r:\n'
        '                html = r.read().decode("utf-8", errors="replace")\n'
        '            for a in re.findall(r"<article class=\\"Box-row\\">(.*?)</article>", html, re.DOTALL)[:15]:\n'
        '                t = re.search(r\'href="(/[^"/]+/[^"/]+)"[^>]*>\s*([^<]{3,200})\', a)\n'
        '                d = re.search(r"<p[^>]*>([^<\n]{10,300})", a)\n'
        '                s = re.search(r"(\d[\d,]*)\s+stars today", a)\n'
        '                if t:\n'
        '                    items.append({"title": f"github: {t.group(2).strip()}",\n'
        '                                   "url": "https://github.com" + t.group(1),\n'
        '                                   "type": "project",\n'
        '                                   "stars_today": (s.group(1).replace(",","") if s else "0"),\n'
        '                                   "description": (d.group(1).strip() if d else ""),\n'
        '                                   "source": "GitHub"})\n'
        '            break\n'
        '        except Exception as e:\n'
        '            last_err = str(e)\n'
        '            if attempt < 3:\n'
        '                _time.sleep((2 ** attempt) + 1)\n'
        '                C.step(f"GitHub 重试 {attempt+2}/4 ({last_err[:40]})...")\n'
        '    if not items:\n'
        '        C.warn(f"GitHub 失败（已重试4次）: {last_err[:60]}")\n'
        '    _cache_set(ck, items)\n'
        '    return items[:limit]\n'
        '\n'
    )
    content = content[:gh_start] + new_fn + content[gh_next:]
    print("2. fetch_github_trending: 已重写（语法错误修复 + 重试4次）")
    changes += 1
else:
    print("2. fetch_github_trending: 未找到函数边界")

# ── 3. fetch_hackernews: 加超时容错 ────────────────────────────
hn_start = content.find("def fetch_hackernews(")
hn_next = content.find("\ndef fetch_", hn_start + 1)
if hn_start != -1 and hn_next != -1:
    old_fn = content[hn_start:hn_next]
    new_fn = (
        'def fetch_hackernews(n=10) -> list[dict]:\n'
        '    import urllib.request, time as _time\n'
        '    ck = _mkcache("hn", n=n)\n'
        '    cached = _cache_get(ck, ttl=600)\n'
        '    if cached is not None: return cached\n'
        '    items = []\n'
        '    last_err = ""\n'
        '    for attempt in range(4):\n'
        '        try:\n'
        '            with urllib.request.urlopen(urllib.request.Request(\n'
        '                "https://hacker-news.firebaseio.com/v0/topstories.json",\n'
        '                headers={"User-Agent": "Mozilla/5.0"}\n'
        '            ), timeout=15) as r:\n'
        '                ids = json.loads(r.read().decode())\n'
        '            for iid in ids[:n*2]:\n'
        '                try:\n'
        '                    with urllib.request.urlopen(urllib.request.Request(\n'
        '                        f"https://hacker-news.firebaseio.com/v0/item/{iid}.json",\n'
        '                        headers={"User-Agent": "Mozilla/5.0"}\n'
        '                    ), timeout=15) as r2:\n'
        '                        item = json.loads(r2.read().decode())\n'
        '                    if item.get("title"):\n'
        '                        items.append({"title": f"hn: {item[\'title\']}",\n'
        '                                       "url": item.get("url") or f"https://news.ycombinator.com/item?id={iid}",\n'
        '                                       "type": "discussion", "score": item.get("score", 0),\n'
        '                                       "source": "HackerNews"})\n'
        '                    if len(items) >= n: break\n'
        '                except Exception:\n'
        '                    continue\n'
        '            break\n'
        '        except Exception as e:\n'
        '            last_err = str(e)\n'
        '            if attempt < 3:\n'
        '                _time.sleep((2 ** attempt) + 1)\n'
        '                C.step(f"HackerNews 重试 {attempt+2}/4 ({last_err[:40]})...")\n'
        '    if not items:\n'
        '        C.warn(f"HackerNews 失败（已重试4次）: {last_err[:60]}")\n'
        '    _cache_set(ck, items)\n'
        '    return items\n'
        '\n'
    )
    content = content[:hn_start] + new_fn + content[hn_next:]
    print("3. fetch_hackernews: 已重写（超时15s + 重试4次）")
    changes += 1
else:
    print("3. fetch_hackernews: 未找到")

# ── 4. fetch_arxiv: 加超时容错 ────────────────────────────────
arx_start = content.find("def fetch_arxiv(")
arx_next = content.find("\ndef fetch_", arx_start + 1)
if arx_start != -1 and arx_next != -1:
    old_fn = content[arx_start:arx_next]
    new_fn = (
        'def fetch_arxiv(topic: str, limit=5) -> list[dict]:\n'
        '    import re, urllib.request, urllib.parse, time as _time\n'
        '    ck = _mkcache("arxiv", t=topic, n=limit)\n'
        '    cached = _cache_get(ck, ttl=7200)\n'
        '    if cached is not None: return cached[:limit]\n'
        '    url = (f"http://export.arxiv.org/api/query"\n'
        '           f"?search_query=all:{urllib.parse.quote(topic)}"\n'
        '           f"&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending")\n'
        '    items = []\n'
        '    last_err = ""\n'
        '    for attempt in range(4):\n'
        '        try:\n'
        '            with urllib.request.urlopen(\n'
        '                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),\n'
        '                timeout=30\n'
        '            ) as r:\n'
        '                xml = r.read().decode("utf-8", errors="replace")\n'
        '            for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):\n'
        '                tm = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)\n'
        '                lm = re.search(r"<id>(.*?)</id>", entry)\n'
        '                sm = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)\n'
        '                if tm:\n'
        '                    items.append({"title": f"[论文] {tm.group(1).strip().replace(chr(10),\' \')}",\n'
        '                                   "url": (lm.group(1).strip() if lm else ""),\n'
        '                                   "type": "paper",\n'
        '                                   "abstract": ((sm.group(1).strip()[:200] if sm else "") + "..."),\n'
        '                                   "source": "ArXiv"})\n'
        '            break\n'
        '        except Exception as e:\n'
        '            last_err = str(e)\n'
        '            if attempt < 3:\n'
        '                _time.sleep((2 ** attempt) + 1)\n'
        '                C.step(f"ArXiv 重试 {attempt+2}/4 ({last_err[:40]})...")\n'
        '    if not items:\n'
        '        C.warn(f"ArXiv 失败（已重试4次）: {last_err[:60]}")\n'
        '    _cache_set(ck, items)\n'
        '    return items[:limit]\n'
        '\n'
    )
    content = content[:arx_start] + new_fn + content[arx_next:]
    print("4. fetch_arxiv: 已重写（超时30s + 重试4次）")
    changes += 1
else:
    print("4. fetch_arxiv: 未找到")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n完成！共修改 {changes} 个函数。验证语法...")
import subprocess
result = subprocess.run(['python', '-m', 'py_compile', path], capture_output=True, text=True)
if result.returncode == 0:
    print("语法验证通过 ✅")
else:
    print(f"语法错误: {result.stderr[:200]}")
