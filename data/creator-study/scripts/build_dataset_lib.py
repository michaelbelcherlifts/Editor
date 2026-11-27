import re
SUBS = {
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
def clean(recs):
    """Drop scans that an ad cut short (under 30 s scanned on a video longer than 30 s); keep the last good scan per id."""
    keep = {}
    for r in recs:
        A = r['A']
        if A.get('seconds', 0) > 30 and A.get('scanned_seconds', 99) < min(30, A['seconds'] * 0.5): continue
        keep[r['m']['id']] = r
    return list(keep.values())

V1_SEGMENT_KEYS = ('words_per_minute', 'words_per_minute_while_talking', 'hook_words', 'pauses_over_300ms', 'longest_pause')
def fix_speech(r):
    """Scans before speech_v 2 counted caption lines, not words. Rename those and recount words where the
    stored transcript is complete (under the 450-character cut)."""
    A = r['A']
    if A.get('speech_v') == 2 or 'words_per_minute' not in A:
        A.setdefault('speech_v', 2 if 'words_per_minute' not in A else A.get('speech_v'))
        return r
    A['caption_lines_per_minute'] = A.get('words_per_minute')
    for k in V1_SEGMENT_KEYS: A.pop(k, None)
    A['speech_v'] = 1
    tr = r.get('tr') or ''
    if tr and len(tr) < 440 and A.get('seconds', 0) <= 180:
        words = [w for w in re.sub(r'\[[^\]]*\]|>>', ' ', tr).split() if w]
        if A.get('seconds'): A['words_per_minute'] = round(len(words) / A['seconds'] * 60)
    return r
_clean0 = clean
def clean(recs):
    return [fix_speech(r) for r in _clean0(recs)]
