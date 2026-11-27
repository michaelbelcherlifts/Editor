// Hook research in the Claude desktop browser pane on youtube.com (signed out is fine; no API key, no cost).
// 1. On any youtube.com page: paste this file, then `await HR.search('powerlifting', HR.SHORTS)`.
//    Filters: HR.SHORTS (by relevance), HR.LONG_BY_VIEWS, HR.LONG_THIS_YEAR (most viewed this year).
// 2. On a /watch page: `HR.queue(['id1','id2'])`, poll `HR.results.length`, read `HR.results`.
//    Opening lines come from the player's own caption request (the transcript API refuses signed-out calls).
// The pane throttles timers when hidden, so sleeps run on a MessageChannel loop.
window.HR = window.HR || {};
(() => {
const walk = (o, key, out = []) => { if (!o || typeof o !== 'object') return out;
  if (Array.isArray(o)) { o.forEach(x => walk(x, key, out)); return out; }
  for (const k in o) { if (k === key) out.push(o[k]); else walk(o[k], key, out); } return out; };
const num = s => { const m = String(s || '').replace(/,/g, '').match(/([\d.]+)\s*([KMB])?/); return m ? parseFloat(m[1]) * ({K: 1e3, M: 1e6, B: 1e9}[m[2]] || 1) : 0; };
const ch = new MessageChannel(), q = [];
ch.port1.onmessage = () => { const now = performance.now(); for (let i = q.length - 1; i >= 0; i--) if (q[i].at <= now) { q[i].r(); q.splice(i, 1); } if (q.length) ch.port2.postMessage(0); };
const sleep = ms => new Promise(r => { q.push({at: performance.now() + ms, r}); ch.port2.postMessage(0); });
HR.SHORTS = 'EgIQCQ=='; HR.LONG_BY_VIEWS = 'CAMSAhAB'; HR.LONG_THIS_YEAR = 'CAMSBAgFEAE=';
HR.search = async (query, params) => {
  const body = {context: ytcfg.get('INNERTUBE_CONTEXT'), query}; if (params) body.params = params;
  const r = await fetch('/youtubei/v1/search?prettyPrint=false', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body)}).then(r => r.json());
  const out = [];
  for (const v of walk(r, 'videoRenderer')) out.push({id: v.videoId, title: (v.title?.runs || []).map(x => x.text).join(''), views: num(v.viewCountText?.simpleText), channel: v.ownerText?.runs?.[0]?.text, age: v.publishedTimeText?.simpleText, short: 0});
  for (const v of walk(r, 'shortsLockupViewModel')) out.push({id: v.onTap?.innertubeCommand?.reelWatchEndpoint?.videoId, title: v.overlayMetadata?.primaryText?.content, views: num(v.overlayMetadata?.secondaryText?.content), short: 1});
  return out.filter(x => x.id).sort((a, b) => b.views - a.views);
};
if (!HR.hooked) { HR.hooked = 1; HR.tt = [];
  const of = window.fetch; window.fetch = async function (...a) { const r = await of.apply(this, a);
    try { const u = (a[0] && a[0].url) || String(a[0]); if (u.includes('timedtext')) r.clone().text().then(t => HR.tt.push({u, t})); } catch (e) {} return r; };
  const oo = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function (m, u) {
    if (String(u).includes('timedtext')) this.addEventListener('load', () => HR.tt.push({u: String(u), t: this.responseText})); return oo.apply(this, arguments); }; }
const lines = json => { let j; try { j = JSON.parse(json); } catch (e) { return []; }
  return (j.events || []).filter(e => e.segs).map(e => ({s: (e.tStartMs || 0) / 1000, t: e.segs.map(s => s.utf8 || '').join('').replace(/\n/g, ' ').trim()})).filter(x => x.t); };
HR.one = async (id, seconds = 8) => {
  const p = document.getElementById('movie_player'); p.mute(); HR.tt = HR.tt.filter(x => !x.u.includes('v=' + id)); p.loadVideoById(id);
  for (let i = 0; i < 40; i++) { await sleep(400); const v = p.querySelector('video');
    if (document.querySelector('.ad-showing')) { document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button-modern')?.click(); continue; }
    if (p.getVideoData().video_id === id && v && v.readyState >= 2) break; }
  const pr = p.getPlayerResponse(), vd = pr.videoDetails || {};
  const en = (pr.captions?.playerCaptionsTracklistRenderer?.captionTracks || []).find(t => /^en/.test(t.languageCode));
  let ls = [];
  if (en) { try { p.loadModule('captions'); p.setOption('captions', 'track', {languageCode: en.languageCode, kind: en.kind || ''}); } catch (e) {}
    p.playVideo(); for (let i = 0; i < 20; i++) { await sleep(400); const hit = HR.tt.find(x => x.u.includes('v=' + id) && x.t.length > 50); if (hit) { ls = lines(hit.t); break; } } }
  p.pauseVideo();
  return {id, title: vd.title, views: +vd.viewCount, channel: vd.author, seconds: +vd.lengthSeconds,
          opening: ls.filter(x => x.s <= seconds).map(x => x.t).join(' ').slice(0, 260), captions: !!en};
};
HR.queue = async ids => { HR.results = HR.results || []; HR.running = 1;
  for (const id of ids) { try { HR.results.push(await HR.one(id)); } catch (e) { HR.results.push({id, error: String(e)}); } } HR.running = 0; };
})();
'HR ready'
