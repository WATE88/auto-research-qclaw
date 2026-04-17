import sqlite3
import json

conn = sqlite3.connect('evolution_monitor.db')

# 查看表结构
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('=== 新数据库表 ===', [t[0] for t in tables])

# 最新数据
print('\n=== 最新5代数据 ===')
rows = conn.execute('SELECT generation, best_score, avg_score FROM generations ORDER BY generation DESC LIMIT 5').fetchall()
for r in rows: print(f'Gen{r[0]}: best={r[1]:.4f} avg={r[2]:.4f}')

# 总代数
total_gen = conn.execute('SELECT COUNT(*) FROM generations').fetchone()[0]
print(f'\n总代数: {total_gen}')

# 最优配置
best = conn.execute('SELECT generation, best_score, config FROM generations ORDER BY best_score DESC LIMIT 1').fetchone()
if best:
    print(f'\n最优: Gen{best[0]} score={best[1]:.4f}')
    cfg = json.loads(best[2]) if best[2] else {}
    for k,v in cfg.items(): print(f'  {k}: {v}')

conn.close()
