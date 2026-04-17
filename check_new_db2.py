import sqlite3
import json

conn = sqlite3.connect('evolution_monitor.db')

# 表结构
print('=== generations 表结构 ===')
for col in conn.execute('PRAGMA table_info(generations)').fetchall():
    print(f'  {col[1]} {col[2]}')

print('\n=== candidates 表结构 ===')
for col in conn.execute('PRAGMA table_info(candidates)').fetchall():
    print(f'  {col[1]} {col[2]}')

# 最新数据
print('\n=== 最新5代数据 ===')
cols = [c[1] for c in conn.execute('PRAGMA table_info(generations)').fetchall()]
col_idx = {c:i for i,c in enumerate(cols)}
sql = f'SELECT * FROM generations ORDER BY generation DESC LIMIT 5'
rows = conn.execute(sql).fetchall()
for r in rows:
    gen = r[col_idx['generation']]
    best = r[col_idx['best_score']]
    print(f'Gen{gen}: best={best:.4f}')

# 总代数
total_gen = conn.execute('SELECT COUNT(*) FROM generations').fetchone()[0]
print(f'\n总代数: {total_gen}')

# 最优配置
if 'config' in col_idx:
    sql = 'SELECT * FROM generations ORDER BY best_score DESC LIMIT 1'
    best = conn.execute(sql).fetchone()
    if best:
        gen = best[col_idx['generation']]
        score = best[col_idx['best_score']]
        cfg_raw = best[col_idx['config']] if 'config' in col_idx else '{}'
        cfg = json.loads(cfg_raw) if cfg_raw else {}
        print(f'\n最优: Gen{gen} score={score:.4f}')
        for k,v in cfg.items(): print(f'  {k}: {v}')

conn.close()
