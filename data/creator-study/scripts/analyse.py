"""Within-creator hits vs flops. Usage: analyse.py records.json out.md"""
import json, sys, math, statistics as st
from collections import defaultdict
from build_dataset_lib import creator, clean
recs = clean(json.load(open(sys.argv[1])))
from datetime import datetime, timezone
NOW = datetime(2026, 11, 27, tzinfo=timezone.utc)
for r in recs:
    p = r['m'].get('published')
    if p: r['A']['age_days'] = round((NOW - datetime.fromisoformat(p)).total_seconds() / 86400, 1)
by = defaultdict(list)
for r in recs:
    if r['A'].get('seconds', 0) > 180: continue
    slug, subs = creator(r['m'].get('channel'))
    if r['m'].get('views'): by[slug].append(r)
KEYS = ['age_days','seconds','cuts_per_minute','first_cut_at','cuts_in_first_3s','median_shot','text_share','text_changes_per_10s',
 'text_on_frame_1','zoom_events_per_minute','motion','brightness','contrast','saturation','warmth','first_word_at',
 'words_per_minute','longest_pause','hook_words','speech_share','hook_question','hook_number','hook_you','hook_me',
 'hook_money','title_question','title_number','title_words','loop_gap']
def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0]*len(xs); i = 0
    while i < len(o):
        j = i
        while j+1 < len(o) and xs[o[j+1]] == xs[o[i]]: j += 1
        for k in range(i, j+1): r[o[k]] = (i+j)/2
        i = j+1
    return r
def spearman(x, y):
    if len(x) < 6 or len(set(x)) < 2: return None
    rx, ry = rank(x), rank(y); mx, my = st.mean(rx), st.mean(ry)
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry)); den = math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))
    return num/den if den else None
out = ['# Hits vs flops, within each creator\n', 'Reach = log10(views / creator median). rho = Spearman rank correlation of the attribute with views inside one creator. n = clips with that attribute. |rho| under 0.3 is treated as nothing.\n']
pooled = defaultdict(lambda: [0, 0, 0])  # key -> [creators positive, negative, total]
for slug, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    if len(rs) < 8: continue
    views = [r['m']['views'] for r in rs]; med = st.median(views)
    rs.sort(key=lambda r: -r['m']['views'])
    out.append(f"\n## {slug} (n={len(rs)}, median views {med:,.0f}, range {min(views):,} to {max(views):,})\n")
    out.append('Top 3: ' + '; '.join(f"\"{r['m']['title'][:60]}\" {r['m']['views']:,}" for r in rs[:3]))
    out.append('\nBottom 3: ' + '; '.join(f"\"{r['m']['title'][:60]}\" {r['m']['views']:,}" for r in rs[-3:]) + '\n')
    hi = [r for r in rs if r['m']['views'] >= med]; lo = [r for r in rs if r['m']['views'] < med]
    lines = []
    for k in KEYS:
        pairs = [(r['A'][k], math.log10(r['m']['views'])) for r in rs if isinstance(r['A'].get(k), (int, float))]
        if not pairs: continue
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
        h = [r['A'][k] for r in hi if isinstance(r['A'].get(k), (int, float))]; l = [r['A'][k] for r in lo if isinstance(r['A'].get(k), (int, float))]
        if rho is None or not h or not l: continue
        if abs(rho) >= 0.3:
            pooled[k][0 if rho > 0 else 1] += 1
            lines.append((abs(rho), f"| {k} | {rho:+.2f} | {st.median(h):.3g} | {st.median(l):.3g} | {len(pairs)} |"))
        pooled[k][2] += 1
    out.append('| attribute | rho | median, top half | median, bottom half | n |\n|---|---|---|---|---|')
    out += [l for _, l in sorted(lines, reverse=True)] or ['| (nothing reached 0.3) | | | | |']
out.append('\n## Across creators\nHow many creators show the same direction (|rho| >= 0.3). An attribute that points the same way for several creators is steadier than one strong result.\n')
out.append('| attribute | creators: more = more views | creators: more = fewer views | creators tested |\n|---|---|---|---|')
for k, (p, n, t) in sorted(pooled.items(), key=lambda kv: -(max(kv[1][0], kv[1][1]) - min(kv[1][0], kv[1][1]))):
    out.append(f"| {k} | {p} | {n} | {t} |")
open(sys.argv[2], 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
