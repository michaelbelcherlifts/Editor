// Style Brain in-browser clip analyzer. Runs on youtube.com watch pages; loads each video in the same player.
window.SB = window.SB || {};
(() => {
const sleep = ms => new Promise(r => setTimeout(r, ms));
const W = 72;
function hook(){
  if (window.__sbHook) return; window.__sbHook = 1; window.__tt = [];
  const of = window.fetch;
  window.fetch = async function (...a) { const r = await of.apply(this, a);
    try { const u = (a[0] && a[0].url) || String(a[0]); if (u.includes('timedtext')) r.clone().text().then(t => window.__tt.push({u, t})); } catch (e) {}
    return r; };
  const oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) { if (String(u).includes('timedtext')) this.addEventListener('load', () => window.__tt.push({u: String(u), t: this.responseText})); return oo.apply(this, arguments); };
}
function words(json){
  let j; try { j = JSON.parse(json); } catch (e) { return []; }
  const out = [];
  for (const ev of (j.events || [])) { if (!ev.segs) continue; const t0 = ev.tStartMs || 0, end = (t0 + (ev.dDurationMs || 0)) / 1000;
    for (const s of ev.segs) { if (!s.utf8 || !s.utf8.trim()) continue; out.push({w: s.utf8.trim(), s: (t0 + (s.tOffsetMs || 0)) / 1000, e: end}); } }
  out.sort((a, b) => a.s - b.s);
  for (let i = 0; i + 1 < out.length; i++) out[i].e = Math.max(out[i].s, Math.min(out[i].e, out[i + 1].s));
  return out;
}
async function seek(v, t){ return new Promise(r => { let done = 0; const f = () => { if (done) return; done = 1; v.removeEventListener('seeked', f); setTimeout(r, 25); }; v.addEventListener('seeked', f); v.currentTime = t; setTimeout(f, 2500); }); }
function frameStats(d, w, h, prevL){
  const n = w * h, L = new Float32Array(n); let R = 0, G = 0, B = 0, S = 0; const ls = new Array(n);
  let sh = [0,0,0,0], hi = [0,0,0,0];
  for (let i = 0, j = 0; i < d.length; i += 4, j++) { const r = d[i], g = d[i+1], b = d[i+2]; const l = .2126*r + .7152*g + .0722*b; L[j] = l; ls[j] = l; R += r; G += g; B += b;
    const mx = Math.max(r,g,b), mn = Math.min(r,g,b); S += mx > 5 ? (mx - mn) / mx : 0;
    if (l < 64) { sh[0]+=r; sh[1]+=g; sh[2]+=b; sh[3]++; } if (l > 179) { hi[0]+=r; hi[1]+=g; hi[2]+=b; hi[3]++; } }
  ls.sort((a, b) => a - b); const pc = p => ls[Math.min(n - 1, Math.floor(n * p))];
  // text signature: bright low-sat pixel with a dark pixel within 2 px horizontally, per 6 horizontal bands
  const bands = [0,0,0,0,0,0], bandMask = new Uint8Array(n);
  for (let y = 0; y < h; y++) for (let x = 2; x < w - 2; x++) { const j = y * w + x, i = j * 4; const r = d[i], g = d[i+1], b = d[i+2];
    if (L[j] > 200 && Math.max(r,g,b) - Math.min(r,g,b) < 45) { if (L[j-2] < 70 || L[j+2] < 70 || L[j-1] < 70 || L[j+1] < 70) { bandMask[j] = 1; bands[Math.min(5, Math.floor(y / h * 6))]++; } } }
  // letterbox: fraction of rows that are near-black
  let blackRows = 0; for (let y = 0; y < h; y++) { let s = 0; for (let x = 0; x < w; x++) s += L[y*w + x]; if (s / w < 12) blackRows++; }
  let diff = null, zoom = 0;
  if (prevL) { let df = 0; for (let j = 0; j < n; j++) df += Math.abs(L[j] - prevL[j]); diff = df / n;
    // zoom: compare prev scaled up 5% about centre with current
    const sc = 1.05; let dz = 0, cnt = 0; for (let y = 4; y < h - 4; y += 2) for (let x = 4; x < w - 4; x += 2) { const sx = Math.round((x - w/2) / sc + w/2), sy = Math.round((y - h/2) / sc + h/2);
      dz += Math.abs(L[y*w + x] - prevL[sy*w + sx]); cnt++; } dz /= cnt;
    let d0 = 0, c0 = 0; for (let y = 4; y < h - 4; y += 2) for (let x = 4; x < w - 4; x += 2) { d0 += Math.abs(L[y*w+x] - prevL[y*w+x]); c0++; } d0 /= c0;
    zoom = d0 > 3 && dz < d0 * 0.8 ? 1 : 0; }
  const m = (R + G + B) / 3 / n;
  return {L, bandMask, luma: ls.reduce((a, b) => a + b, 0) / n, p5: pc(.05), p95: pc(.95), p1: pc(.01), p99: pc(.99), sat: S / n, rb: (R - B) / n, gm: (G - (R + B) / 2) / n,
    sh, hi, bands: bands.map(c => c / (n / 6)), letter: blackRows / h, diff, zoom};
}
SB.frameStats = frameStats;
SB.TEXT_T = 0.02;
SB.textStats = function (v, tc, tx){
const w = tc.width, h = tc.height; tx.drawImage(v, 0, 0, w, h); const d = tx.getImageData(0, 0, w, h).data; const n = w * h; const L = new Float32Array(n), ok = new Uint8Array(n);
for (let i = 0, j = 0; j < n; i += 4, j++) { const r = d[i], g = d[i+1], b = d[i+2]; L[j] = .2126*r + .7152*g + .0722*b; ok[j] = (L[j] > 200 && Math.max(r,g,b) - Math.min(r,g,b) < 50) ? 1 : 0; }
const bands = [0,0,0,0,0,0], mask = new Uint8Array(n);
for (let y = 0; y < h; y++) { const bi = Math.min(5, Math.floor(y / h * 6)); for (let x = 3; x < w - 3; x++) { const j = y * w + x; if (!ok[j]) continue;
let left = 0, right = 0; for (let k = 1; k <= 3; k++) { if (L[j - k] < 80) left = 1; if (L[j + k] < 80) right = 1; }
if (left && right) { bands[bi]++; mask[j] = 1; } } }
const per = n / 6; return {bands: bands.map(c => c / per), mask};
};
SB.scan = async function (T1, STEP){
  const v = document.querySelector('#movie_player video') || document.querySelector('video'); v.pause(); v.muted = true;
  const vw = v.videoWidth, vh = v.videoHeight, H = Math.max(8, Math.round(W * vh / vw));
  const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d', {willReadFrequently: true});
const tc = document.createElement('canvas'); tc.width = 160; tc.height = Math.max(16, Math.round(160 * vh / vw)); const tx = tc.getContext('2d', {willReadFrequently: true});
  T1 = Math.min(T1, v.duration - 0.08); const fr = []; let prev = null, prevMask = null;
  for (let t = 0.04; t <= T1; t += STEP) { await seek(v, t); x.drawImage(v, 0, 0, W, H); const d = x.getImageData(0, 0, W, H).data;
    const f = SB.frameStats(d, W, H, prev ? prev : null); const ts = SB.textStats(v, tc, tx); f.bands = ts.bands; f.bandMask = ts.mask; let tcv = 0;
    if (prevMask) { let a = 0, u = 0; for (let j = 0; j < f.bandMask.length; j++) { if (f.bandMask[j] || prevMask[j]) { u++; if (f.bandMask[j] !== prevMask[j]) a++; } } tcv = u > 20 ? a / u : 0; }
    prev = f.L; prevMask = f.bandMask; delete f.L; delete f.bandMask; f.t = +t.toFixed(3); f.tc = tcv; fr.push(f); }
  return {fr, vw, vh, dur: v.duration};
};
function cutsFrom(fr){
  const cuts = [];
  for (let i = 1; i < fr.length; i++) { const lo = Math.max(1, i - 5), hiI = Math.min(fr.length - 1, i + 5); const loc = []; for (let k = lo; k <= hiI; k++) if (k !== i) loc.push(fr[k].diff); loc.sort((a, b) => a - b);
    const med = loc[Math.floor(loc.length / 2)] || 0; if (fr[i].diff > 20 && fr[i].diff > 2.5 * med + 4) { if (!cuts.length || fr[i].t - cuts[cuts.length - 1] > 0.2) cuts.push(fr[i].t); } }
  return cuts;
}
const r2 = x => Math.round(x * 100) / 100, r3 = x => Math.round(x * 1000) / 1000;
SB.summarise = function (meta, sc, ws){
  const fr = sc.fr, span = fr.length ? fr[fr.length - 1].t : 0, dur = meta.seconds;
  const cuts = cutsFrom(fr); const bounds = [0, ...cuts, span]; const shots = []; for (let i = 0; i < bounds.length - 1; i++) shots.push(bounds[i+1] - bounds[i]);
  const sorted = [...shots].sort((a, b) => a - b), med = sorted[Math.floor(sorted.length / 2)] || span;
  const mean = shots.reduce((a, b) => a + b, 0) / Math.max(1, shots.length); const sd = Math.sqrt(shots.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, shots.length));
  const avg = (k, f = fr) => f.reduce((a, z) => a + z[k], 0) / Math.max(1, f.length);
  const tint = k => { const s = [0,0,0,0]; fr.forEach(z => { for (let i = 0; i < 4; i++) s[i] += z[k][i]; }); return s[3] ? [s[0]/s[3], s[1]/s[3], s[2]/s[3]].map(v => Math.round(v)) : null; };
  const textAt = z => Math.max(...z.bands) > SB.TEXT_T; // any band with text-like pixels
  const capFr = fr.filter(textAt);
  const bandPos = capFr.length ? capFr.reduce((a, z) => { const b = z.bands; const tot = b.reduce((p, q) => p + q, 0); return a + b.reduce((p, q, i) => p + q * (i + .5) / 6, 0) / tot; }, 0) / capFr.length : null;
  const tChanges = fr.filter(z => z.tc > 0.5 && textAt(z)).length; const zoomFr = fr.filter(z => z.zoom).length;
  const first3 = fr.filter(z => z.t < 3), rest = fr.filter(z => z.t >= 3);
  const motion = fr.filter(z => z.diff !== null && !cuts.includes(z.t)); const motionMean = motion.length ? avg('diff', motion) : 0;
  // zoom events: runs of zoom frames
  let zoomEvents = 0; for (let i = 0; i < fr.length; i++) if (fr[i].zoom && !(i && fr[i-1].zoom)) zoomEvents++;
  const lastFirstDiff = (() => { if (fr.length < 4) return null; const a = fr[0], b = fr[fr.length - 1]; return Math.abs(a.luma - b.luma) + Math.abs(a.rb - b.rb); })();
  const A = {seconds: r2(dur), scanned_seconds: r2(span), vertical: sc.vh > sc.vw ? 1 : 0,
    cuts_per_minute: r2(cuts.length / Math.max(1, span) * 60), first_cut_at: cuts.length ? r2(cuts[0]) : r2(span), cuts_in_first_3s: cuts.filter(t => t < 3).length,
    cuts_3_10s: cuts.filter(t => t >= 3 && t < 10).length, median_shot: r2(med), mean_shot: r2(mean), shot_cv: r2(sd / Math.max(0.01, mean)), longest_shot: r2(Math.max(...shots, 0)),
    brightness: r3(avg('luma') / 255), contrast: r3((avg('p95') - avg('p5')) / 255), black_point: r3(avg('p1') / 255), white_point: r3(avg('p99') / 255), saturation: r3(avg('sat')),
    warmth: r3(avg('rb') / 255), green_magenta: r3(avg('gm') / 255),
    brightness_first_3s: first3.length ? r3(avg('luma', first3) / 255) : null, brightness_change_after_3s: first3.length && rest.length ? r3((avg('luma', rest) - avg('luma', first3)) / 255) : null,
    text_share: r3(capFr.length / Math.max(1, fr.length)), text_position: bandPos === null ? null : r3(bandPos), text_changes_per_10s: r2(tChanges / Math.max(1, span) * 10),
    text_top_share: r3(fr.filter(z => Math.max(z.bands[0], z.bands[1]) > SB.TEXT_T).length / Math.max(1, fr.length)), text_on_frame_1: fr.length && textAt(fr[0]) ? 1 : 0,
    zoom_events_per_minute: r2(zoomEvents / Math.max(1, span) * 60), zoom_share: r3(zoomFr / Math.max(1, fr.length)), letterbox_share: r3(avg('letter')), motion: r2(motionMean / 255 * 100),
    loop_gap: lastFirstDiff === null ? null : r2(lastFirstDiff)};
  const sh = tint('sh'), hi = tint('hi');
  if (sh) { A.shadow_r = sh[0]; A.shadow_g = sh[1]; A.shadow_b = sh[2]; } if (hi) { A.highlight_r = hi[0]; A.highlight_g = hi[1]; A.highlight_b = hi[2]; }
  // speech
  const sp = ws.filter(w => !/^\[.*\]$/.test(w.w));
  if (sp.length) { const gaps = []; for (let i = 1; i < sp.length; i++) gaps.push(sp[i].s - sp[i-1].e);
    const talk = sp[sp.length - 1].e - sp[0].s;
    A.first_word_at = r2(sp[0].s); A.words_per_minute = Math.round(sp.length / Math.max(1, dur) * 60); A.words_per_minute_while_talking = Math.round(sp.length / Math.max(1, talk) * 60);
    A.longest_pause = r2(Math.max(0, ...gaps)); A.pauses_over_300ms = gaps.filter(g => g > 0.3).length; A.hook_words = sp.filter(w => w.s < 3).length;
    A.speech_share = r3(Math.min(1, talk / Math.max(1, dur))); A.music_tags = ws.filter(w => /\[music\]/i.test(w.w)).length;
  } else { A.hook_words = 0; A.speech_share = 0; }
  const hookText = sp.filter(w => w.s < 3.5).map(w => w.w).join(' ');
  const hk = (s) => ({q: /\?|^(how|what|why|who|which|when|where|do|does|did|is|are|can|would|should|will)\b/i.test(s) ? 1 : 0, num: /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million)\b/i.test(s) ? 1 : 0,
    warn: /\b(stop|never|don'?t|avoid|mistake|wrong|worst|danger|warning|quit|ruin)/i.test(s) ? 1 : 0, you: /\b(you|your|you're|you'?ll)\b/i.test(s) ? 1 : 0, me: /\b(i|i'm|i've|my|me)\b/i.test(s) ? 1 : 0,
    sup: /\b(most|best|worst|biggest|heaviest|strongest|craziest|insane|impossible|ever|every|fastest|hardest|only|\w+est)\b/i.test(s) ? 1 : 0, money: /\$|\bdollars?\b|\bpay(ing)?\b/i.test(s) ? 1 : 0});
  const h1 = hk(hookText), h2 = hk(meta.title);
  A.hook_question = h1.q; A.hook_number = h1.num; A.hook_warning = h1.warn; A.hook_you = h1.you; A.hook_me = h1.me; A.hook_superlative = h1.sup; A.hook_money = h1.money;
  A.title_question = h2.q; A.title_number = h2.num; A.title_warning = h2.warn; A.title_you = h2.you; A.title_me = h2.me; A.title_superlative = h2.sup; A.title_money = h2.money;
  A.title_caps_share = r3((meta.title.match(/[A-Z]/g) || []).length / Math.max(1, (meta.title.match(/[A-Za-z]/g) || []).length)); A.title_words = meta.title.split(/\s+/).filter(Boolean).length;
  A.title_emoji = /\p{Extended_Pictographic}/u.test(meta.title) ? 1 : 0; A.has_transcript = sp.length ? 1 : 0;
  for (const k in A) if (A[k] === null || Number.isNaN(A[k])) delete A[k];
  // per-second timeline
  const secs = Math.ceil(span); const tl = [];
  for (let s = 0; s < secs; s++) { const fs = fr.filter(z => z.t >= s && z.t < s + 1); if (!fs.length) continue;
    tl.push({s, cuts: cuts.filter(t => t >= s && t < s + 1).length, luma: Math.round(avg('luma', fs)), text: +(fs.filter(textAt).length / fs.length).toFixed(2),
      textChange: fs.filter(z => z.tc > 0.5 && textAt(z)).length, zoom: fs.filter(z => z.zoom).length, motion: Math.round(avg('diff', fs.filter(z => z.diff !== null)) || 0),
      bands: [0,1,2,3,4,5].map(b => +(avg('_', fs.map(z => ({_: z.bands[b]}))).toFixed(3))), words: sp.filter(w => w.s >= s && w.s < s + 1).map(w => w.w).join(' ')}); }
  return {A, cuts: cuts.map(r2), shots: shots.map(r2), hookText, transcript: sp.map(w => w.w).join(' ').slice(0, 1500), timeline: tl};
};
SB.one = async function (id, opts = {}){
  hook(); const p = document.querySelector('#movie_player');
  if (p.getVideoData().video_id !== id) p.loadVideoById(id);
  for (let i = 0; i < 60; i++) { await sleep(500); const ad = document.querySelector('.ad-showing'); const v = p.querySelector('video');
    if (ad) { const sk = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button-modern, .ytp-ad-skip-button'); if (sk) sk.click(); continue; }
    if (p.getVideoData().video_id === id && v && v.readyState >= 2 && v.duration > 1) break; }
  const pr = p.getPlayerResponse(); const vd = pr.videoDetails || {}; const mf = (pr.microformat || {}).playerMicroformatRenderer || {};
  const meta = {id, title: vd.title || '', views: +vd.viewCount || null, seconds: +vd.lengthSeconds || p.querySelector('video').duration, channel: vd.author, channelId: vd.channelId, published: mf.publishDate || mf.uploadDate || null,
    isShortsLike: null};
  // transcript via the player's own caption request
  window.__tt = window.__tt.filter(x => !x.u.includes('v=' + id)); let ws = [];
  const tracks = ((pr.captions || {}).playerCaptionsTracklistRenderer || {}).captionTracks || [];
  const en = tracks.find(t => /^en/.test(t.languageCode));
  if (en) { try { p.loadModule('captions'); p.setOption('captions', 'track', {languageCode: en.languageCode, kind: en.kind || ''}); if (!(document.querySelector('.ytp-subtitles-button') || {}).getAttribute?.('aria-pressed') === 'true') {} try { p.toggleSubtitles(); } catch (e) {} await sleep(200); if (document.querySelector('.ytp-subtitles-button')?.getAttribute('aria-pressed') !== 'true') { try { p.toggleSubtitles(); } catch (e) {} } } catch (e) {}
    p.playVideo(); for (let i = 0; i < 16; i++) { await sleep(400); const hit = window.__tt.find(x => x.u.includes('v=' + id) && x.t.length > 50); if (hit) { ws = words(hit.t); break; } } }
  p.pauseVideo();
  const T1 = opts.max || 60, step = opts.step || 0.125;
  const sc = await SB.scan(T1, step);
  const out = SB.summarise(meta, sc, ws);
  return {SBREC: 1, meta: {...meta, w: sc.vw, h: sc.vh, captions_track: en ? (en.kind || 'manual') : null}, ...out};
};
SB.queue = async function (ids, opts){
  SB.results = SB.results || []; SB.errors = SB.errors || []; SB.running = 1;
  for (const id of ids) { if (SB.stop) break; SB.current = id; try { const r = await SB.one(id, opts); SB.results.push(r); } catch (e) { SB.errors.push({id, e: String(e)}); } }
  SB.running = 0; SB.current = null;
};
SB.take = function (){ const r = SB.results || []; SB.results = []; return r; };
})();
'SB ready'

// Speech fix (speech_v 2, applied from 27 Nov 05:58 UTC). YouTube's caption events often hold a whole line
// per segment, so the counts above were caption lines, not words. This wrapper splits lines into words,
// keeps only words inside the scanned window, and recomputes the speech numbers.
if (!SB.summarise0) SB.summarise0 = SB.summarise;
SB.summarise = function (meta, sc, ws) {
  const out = SB.summarise0(meta, sc, ws);
  try {
    const A = out.A, fr = sc.fr, span = fr.length ? fr[fr.length - 1].t : 0;
    const W = [];
    for (const x of (ws || []).filter(w => !/^\[.*\]$/.test(w.w))) {
      const parts = x.w.split(/\s+/).filter(Boolean), e = Math.max(x.e, x.s + 0.01);
      parts.forEach((p, k) => W.push({w: p, s: x.s + (e - x.s) * k / parts.length, e: x.s + (e - x.s) * (k + 1) / parts.length}));
    }
    const win = Math.max(1, Math.min(span || meta.seconds, meta.seconds)), sp = W.filter(w => w.s < win);
    A.speech_v = 2; A.transcript_words_total = W.length;
    A.transcript_last_word_at = W.length ? Math.round(W[W.length - 1].s * 100) / 100 : null;
    if (sp.length) {
      const g = []; for (let i = 1; i < sp.length; i++) g.push(sp[i].s - sp[i - 1].e);
      const talk = sp[sp.length - 1].e - sp[0].s;
      A.first_word_at = Math.round(sp[0].s * 100) / 100; A.words_per_minute = Math.round(sp.length / win * 60);
      A.words_per_minute_while_talking = Math.round(sp.length / Math.max(1, talk) * 60);
      A.longest_pause = Math.round(Math.max(0, ...g) * 100) / 100; A.pauses_over_300ms = g.filter(x => x > 0.3).length;
      A.hook_words = sp.filter(w => w.s < 3).length; A.speech_share = Math.round(Math.min(1, talk / win) * 1000) / 1000;
    } else { A.hook_words = 0; A.speech_share = 0; }
  } catch (e) { out.patch_err = String(e); }
  return out;
};
