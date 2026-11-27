"""Turn analyzer records (records.json) into clip files + repo dataset."""
import json, os, re, csv, math, statistics, sys
from build_dataset_lib import clean
recs = clean(json.load(open('records.json')))
SUBS = {  # channel name substring (lower) -> (slug, subscribers)
 'mekluvin': ('mekluvin', 345e3), 'chris bumstead': ('cbum', 4.9e6), 'vince wilkinson': ('vince', 106e3),
 'alex eubank': ('alex', 1.34e6), 'luka hocevar': ('luka', 618e3), 'tren twins': ('tren', 2.23e6),
 'sam sulek': ('sam', 4.58e6), 'togi': ('togi', 1.46e6), 'shane stoffer': ('togi', 1.46e6),
 'noah anderson': ('noah', 559e3), 'jun yuh': ('jun', 762e3), 'good good': ('goodgood', 2.18e6),
 'japes': ('japes', 19.5e3), 'solid': ('solidheaston', 96.1e3), 'dalton joyce': ('youngdalt', 4.97e3),
 'young dalt': ('youngdalt', 4.97e3),
}
def creator(ch):
    c = (ch or '').lower()
    for k, v in SUBS.items():
        if k in c: return v
    return (re.sub(r'[^a-z0-9]+', '', c) or 'unknown', None)
SCHEMA = ['seconds','first_word_at','words_per_minute','longest_pause','pauses_over_300ms','hook_words',
 'hook_question','hook_number','hook_warning','hook_you','hook_me','hook_superlative','cuts_per_minute',
 'first_cut_at','cuts_in_first_3s','vertical','brightness','contrast','saturation','warmth']
clips_dir = sys.argv[1]; repo_dir = sys.argv[2]
os.makedirs(clips_dir, exist_ok=True); os.makedirs(repo_dir + '/records', exist_ok=True)
rows = []; unknown = set()
by_creator = {}
for r in recs:
    m = r['m']; slug, subs = creator(m.get('channel'))
    if subs is None: unknown.add(m.get('channel'))
    by_creator.setdefault(slug, []).append(r)
medians = {s: statistics.median([x['m']['views'] for x in v if x['m'].get('views')]) for s, v in by_creator.items()}
for r in recs:
    m = r['m']; A = r['A']; slug, subs = creator(m.get('channel'))
    long_form = A.get('seconds', 0) > 180
    attrs = {k: v for k, v in A.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    # Text on the first frame is measured from pixels, so it maps to the schema flag.
    if 'text_on_frame_1' in attrs: attrs['judge_text_on_frame_1'] = attrs['text_on_frame_1']
    if A.get('text_changes_per_10s') is not None:
        attrs['judge_captions'] = 1 if A['text_changes_per_10s'] >= 8 and A.get('text_share', 0) >= 0.4 else 0
    if m.get('published'):
        from datetime import datetime, timezone
        pub = datetime.fromisoformat(m['published'])
        attrs['age_days'] = round((datetime(2026, 11, 27, tzinfo=timezone.utc) - pub).total_seconds() / 86400, 1)
    url = f"https://www.youtube.com/{'watch?v=' if long_form else 'shorts/'}{m['id']}"
    clip = {'id': m['id'], 'group': slug, 'about': f"{m.get('channel')}, {m.get('title')}, {url}", 'mine': False,
            'attributes': attrs, 'outcome': {k: v for k, v in {'views': m.get('views'), 'subscribers': subs}.items() if v}}
    # long-form openings are measured on the first 60 s only; keep them out of the shorts model set
    if not long_form:
        json.dump(clip, open(f"{clips_dir}/{m['id']}.json", 'w'), indent=1)
    full = {'creator': slug, 'format': 'long-form opening' if long_form else 'short', 'meta': m, 'attributes': A,
            'cuts': r.get('cuts'), 'hook': r.get('hook'), 'transcript_start': r.get('tr'),
            'timeline_fields': 's,cuts,text_share,text_changes,zoom_frames,motion,luma,text_band(0 top..5 bottom),text_density',
            'timeline': r.get('tl'), 'subscribers': subs,
            'reach_vs_creator_median': round(math.log10(max(m.get('views') or 1, 1) / medians[slug]), 3) if medians.get(slug) else None}
    json.dump(full, open(f"{repo_dir}/records/{slug}__{m['id']}.json", 'w'), indent=1)
    rows.append({'creator': slug, 'format': full['format'], 'id': m['id'], 'title': m.get('title'), 'views': m.get('views'),
                 'subscribers': subs, 'published': m.get('published'), 'reach_vs_creator_median': full['reach_vs_creator_median'],
                 'hook': (r.get('hook') or '')[:160], **{k: A.get(k) for k in sorted(A) if not isinstance(A.get(k), str)}})
keys = []
for row in rows:
    for k in row:
        if k not in keys: keys.append(k)
with open(f"{repo_dir}/clips.csv", 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
from collections import Counter
print(len(rows), Counter((x['creator'], x['format']) for x in rows), 'unknown:', unknown)
