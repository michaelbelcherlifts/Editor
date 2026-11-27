"""The one-button poster: a prepared reel goes to Instagram, TikTok and YouTube Shorts.

Posting happens only when Michael asks for it: he runs `stylebrain publish`
(or double-clicks the shortcut `publish-shortcut` makes). Nothing here runs on a
schedule or posts by itself.

It posts what the cross-poster prepared (`library/crosspost/POST-title/`), using
each app's official API from his own computer:

- YouTube Shorts: the YouTube Data API's resumable upload. Free; public at once.
- Instagram Reels: the Instagram Graph API (Facebook Login for Business), with
  the video sent straight from the computer by resumable upload. Needs a
  professional (creator or business) account linked to a Facebook Page.
- TikTok: the Content Posting API (Direct Post, file upload). Until TikTok
  audits the app, every post is private ("only me"): he makes it public in the
  app. Set `"audited": true` in `library/accounts/tiktok.json` once it passes.

Before anything is sent, each platform's text is read back from its `.txt` file
(so his edits there count) and checked again: unfilled `[placeholders]`, the
no-worlds rule, caption and title limits, and the video's shape and length. A
platform with a problem is not posted; the others still go. A platform already
posted for that calendar post is skipped, so pressing twice does not post twice.

Sign-ins live in `library/accounts/` (not committed). Only standard-library HTTP
is used, so there is nothing extra to install.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import http.server
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from .edl import EditError

SHORT_FORM = ["instagram", "tiktok", "youtube-shorts"]
GRAPH = "https://graph.facebook.com/v23.0"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v23.0"
TIKTOK = "https://open.tiktokapis.com/v2"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TIKTOK_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
CHUNK = 10 * 1024 * 1024      # TikTok chunk size (5 to 64 MB; the last may be larger)
WAIT = 3.0                    # seconds between status checks
WAIT_LIMIT = 600              # give up on processing after this many seconds


class PublishError(EditError):
    pass


# ---------------------------------------------------------------- HTTP (swapped out in tests)

def http(method: str, url: str, *, headers: dict | None = None, data: bytes | None = None,
         params: dict | None = None, form: dict | None = None, json_body: dict | None = None) -> tuple[int, dict, bytes]:
    """One HTTP request. Returns (status, response headers, body). Never raises on an HTTP error status."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers.setdefault("Content-Type", "application/json; charset=UTF-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read()


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def _json(status: int, body: bytes, what: str) -> dict:
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {"raw": body[:300].decode(errors="replace")}
    if status >= 400:
        err = data.get("error", data)
        if isinstance(err, dict):
            err = err.get("message") or err.get("error_user_msg") or err.get("code") or err
        raise PublishError(f"{what} failed ({status}): {err}")
    return data


# ---------------------------------------------------------------- accounts

def accounts_dir(base: str | Path = ".") -> Path:
    return Path(base) / "library" / "accounts"


def load_account(platform: str, base: str | Path = ".") -> dict:
    name = "youtube" if platform.startswith("youtube") else platform
    path = accounts_dir(base) / f"{name}.json"
    if not path.exists():
        raise PublishError(f"{platform} is not connected: run `stylebrain connect {name}` first")
    return json.loads(path.read_text())


def save_account(platform: str, data: dict, base: str | Path = ".") -> Path:
    d = accounts_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{platform}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def _loopback_code(auth_url: str, params: dict, port: int) -> str:
    """Open the sign-in page in his browser and catch the code on http://localhost:PORT/."""
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if "code" in q or "error" in q:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<p>Signed in. You can close this tab and go back to Claude.</p>")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = auth_url + "?" + urllib.parse.urlencode({**params, "state": state})
    print(f"opening the sign-in page; if it does not open, go to:\n{url}")
    webbrowser.open(url)
    deadline = time.time() + 300
    while not got and time.time() < deadline:
        server.timeout = 5
        server.handle_request()
    server.server_close()
    if not got:
        raise PublishError("no sign-in came back within 5 minutes")
    if got.get("error") or got.get("state") != state:
        raise PublishError(f"sign-in refused: {got.get('error_description') or got.get('error') or 'state did not match'}")
    return got["code"]


def connect_youtube(client_file: str | Path, base: str | Path = ".", port: int = 8765) -> dict:
    """Sign in to YouTube once with a Google Cloud 'Desktop app' OAuth client (client_secret JSON)."""
    raw = json.loads(Path(client_file).read_text())
    c = raw.get("installed") or raw.get("web") or raw
    redirect = f"http://127.0.0.1:{port}/"
    code = _loopback_code(GOOGLE_AUTH, {"client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
                                        "scope": YT_SCOPE, "access_type": "offline", "prompt": "consent"}, port)
    tok = _json(*http("POST", GOOGLE_TOKEN, form={"code": code, "client_id": c["client_id"],
                                                  "client_secret": c["client_secret"], "redirect_uri": redirect,
                                                  "grant_type": "authorization_code"})[::2], "YouTube sign-in")
    if not tok.get("refresh_token"):
        raise PublishError("Google gave no refresh token; remove the app's access in your Google account and try again")
    acct = {"client_id": c["client_id"], "client_secret": c["client_secret"], "refresh_token": tok["refresh_token"]}
    save_account("youtube", acct, base)
    return acct


def connect_tiktok(client_key: str, client_secret: str, base: str | Path = ".", port: int = 8766,
                   audited: bool = False) -> dict:
    """Sign in to TikTok once with a TikTok for Developers app (Login Kit + Content Posting API)."""
    redirect = f"http://localhost:{port}/callback/"
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()  # TikTok's desktop PKCE uses hex, not base64
    code = _loopback_code(TIKTOK_AUTH, {"client_key": client_key, "redirect_uri": redirect, "response_type": "code",
                                        "scope": "user.info.basic,video.publish", "code_challenge": challenge,
                                        "code_challenge_method": "S256"}, port)
    tok = _json(*http("POST", f"{TIKTOK}/oauth/token/", form={
        "client_key": client_key, "client_secret": client_secret, "code": code, "grant_type": "authorization_code",
        "redirect_uri": redirect, "code_verifier": verifier})[::2], "TikTok sign-in")
    acct = {"client_key": client_key, "client_secret": client_secret, "refresh_token": tok["refresh_token"],
            "access_token": tok["access_token"], "expires": time.time() + float(tok.get("expires_in", 0)) - 60,
            "audited": audited}
    save_account("tiktok", acct, base)
    return acct


def connect_instagram(token: str, app_id: str | None = None, app_secret: str | None = None,
                      base: str | Path = ".") -> dict:
    """Connect Instagram from a user token (Graph API Explorer, Facebook Login for Business).

    With the app id and secret the token is swapped for a 60-day one, and the Page
    token found from it does not expire. Finds the Instagram account linked to his Page."""
    if app_id and app_secret:
        token = _json(*http("GET", f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
            "fb_exchange_token": token})[::2], "Instagram token swap")["access_token"]
    pages = _json(*http("GET", f"{GRAPH}/me/accounts", params={
        "fields": "name,access_token,instagram_business_account{id,username}", "access_token": token})[::2],
        "finding the Facebook Page").get("data", [])
    linked = [p for p in pages if p.get("instagram_business_account")]
    if not linked:
        raise PublishError("no Facebook Page with a linked Instagram professional account was found for this sign-in")
    page = linked[0]
    ig = page["instagram_business_account"]
    acct = {"ig_user_id": ig["id"], "username": ig.get("username"), "page": page.get("name"),
            "access_token": page["access_token"]}
    save_account("instagram", acct, base)
    return acct


# ---------------------------------------------------------------- reading what to post

HEADERS = ("TITLE", "DESCRIPTION", "TAGS", "CAPTION")


def read_paste(path: str | Path) -> dict:
    """Read a PLATFORM.txt back, including any edits he made there."""
    lines = Path(path).read_text().splitlines()
    out: dict[str, list[str]] = {}
    cur = None
    for ln in lines[2:]:
        if ln.startswith("Video: ") and cur is None:
            out["video"] = [ln[7:].strip()]
            continue
        if ln.strip() in HEADERS:
            cur = ln.strip().lower()
            out[cur] = []
            continue
        if ln.startswith(("FIX BEFORE POSTING:", "note:")):
            cur = None
            continue
        if cur:
            out[cur].append(ln)
    text = {k: "\n".join(v).strip() for k, v in out.items()}
    if "tags" in text:
        text["tags"] = [t.strip() for t in text["tags"].split(",") if t.strip()]
    return text


def recheck(platform: str, text: dict, video: str | None) -> list[str]:
    """The checks again, on the words as they will be sent."""
    from . import crosspost as cp

    spec = cp.PLATFORMS[platform]
    v = cp.Version(platform, spec["name"], {k: text[k] for k in ("caption", "title", "description") if k in text},
                   [], "", video)
    everything = "\n".join(str(x) for x in v.text.values())
    cp._check_words(v, everything)
    if not video or not Path(video).exists():
        v.problems.append(f"cannot find the video {video or '(none)'}")
    else:
        cp._check_video(v, spec, cp.video_facts(video))
    if "caption" in text:
        if not text["caption"]:
            v.problems.append("the caption is empty")
        elif len(text["caption"]) > spec["caption_max"]:
            v.problems.append(f"caption is {len(text['caption'])} characters; {spec['name']} allows {spec['caption_max']}")
        n = sum(1 for w in text["caption"].split() if w.startswith("#"))
        if n > spec["hashtags_max"]:
            v.problems.append(f"{n} hashtags; {spec['name']} allows {spec['hashtags_max']}")
    else:
        if not text.get("title"):
            v.problems.append("the title is empty")
        elif len(text["title"]) > spec["title_max"]:
            v.problems.append(f"title is {len(text['title'])} characters; YouTube allows {spec['title_max']}")
        if any(c in text.get("title", "") + text.get("description", "") for c in "<>"):
            v.problems.append("YouTube does not allow < or > in titles and descriptions")
    return v.problems


# ---------------------------------------------------------------- the three uploads

def post_youtube(video: str, text: dict, acct: dict) -> dict:
    tok = _json(*http("POST", GOOGLE_TOKEN, form={"client_id": acct["client_id"], "client_secret": acct["client_secret"],
                                                  "refresh_token": acct["refresh_token"],
                                                  "grant_type": "refresh_token"})[::2], "YouTube sign-in refresh")
    auth = {"Authorization": f"Bearer {tok['access_token']}"}
    size = Path(video).stat().st_size
    meta = {"snippet": {"title": text["title"], "description": text.get("description", ""),
                        "tags": text.get("tags") or [], "categoryId": "17"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    status, headers, body = http("POST", YT_UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"},
                                 headers={**auth, "X-Upload-Content-Type": "video/mp4",
                                          "X-Upload-Content-Length": str(size)}, json_body=meta)
    _json(status, body, "starting the YouTube upload")
    where = headers.get("location")
    if not where:
        raise PublishError("YouTube did not give an upload address")
    data = _json(*http("PUT", where, headers={**auth, "Content-Type": "video/mp4"},
                       data=Path(video).read_bytes())[::2], "uploading to YouTube")
    vid = data["id"]
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "privacy": "public"}


def post_instagram(video: str, text: dict, acct: dict) -> dict:
    tok, ig = acct["access_token"], acct["ig_user_id"]
    made = _json(*http("POST", f"{GRAPH}/{ig}/media", form={
        "media_type": "REELS", "upload_type": "resumable", "caption": text["caption"], "share_to_feed": "true",
        "access_token": tok})[::2], "starting the Instagram upload")
    cid = made["id"]
    size = Path(video).stat().st_size
    _json(*http("POST", f"{RUPLOAD}/{cid}", headers={"Authorization": f"OAuth {tok}", "offset": "0",
                                                     "file_size": str(size)},
                data=Path(video).read_bytes())[::2], "uploading to Instagram")
    waited = 0.0
    while True:
        st = _json(*http("GET", f"{GRAPH}/{cid}", params={"fields": "status_code,status",
                                                           "access_token": tok})[::2], "Instagram processing")
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not process the video: {st.get('status') or code}")
        if waited > WAIT_LIMIT:
            raise PublishError("Instagram is still processing after 10 minutes; try again later")
        sleep(WAIT)
        waited += WAIT
    pub = _json(*http("POST", f"{GRAPH}/{ig}/media_publish", form={"creation_id": cid, "access_token": tok})[::2],
                "publishing on Instagram")
    mid = pub["id"]
    link = _json(*http("GET", f"{GRAPH}/{mid}", params={"fields": "permalink", "access_token": tok})[::2],
                 "reading the Instagram link")
    return {"id": mid, "url": link.get("permalink") or f"https://www.instagram.com/{acct.get('username') or ''}",
            "privacy": "public"}


def _tiktok_token(acct: dict, base: str | Path) -> str:
    if acct.get("access_token") and time.time() < float(acct.get("expires", 0)):
        return acct["access_token"]
    tok = _json(*http("POST", f"{TIKTOK}/oauth/token/", form={
        "client_key": acct["client_key"], "client_secret": acct["client_secret"], "grant_type": "refresh_token",
        "refresh_token": acct["refresh_token"]})[::2], "TikTok sign-in refresh")
    acct.update(access_token=tok["access_token"], refresh_token=tok.get("refresh_token", acct["refresh_token"]),
                expires=time.time() + float(tok.get("expires_in", 0)) - 60)
    save_account("tiktok", acct, base)
    return acct["access_token"]


def post_tiktok(video: str, text: dict, acct: dict, base: str | Path = ".") -> dict:
    auth = {"Authorization": f"Bearer {_tiktok_token(acct, base)}"}
    info = _json(*http("POST", f"{TIKTOK}/post/publish/creator_info/query/", headers=auth, json_body={})[::2],
                 "reading the TikTok account").get("data", {})
    options = info.get("privacy_level_options") or ["SELF_ONLY"]
    privacy = "PUBLIC_TO_EVERYONE" if acct.get("audited") and "PUBLIC_TO_EVERYONE" in options else "SELF_ONLY"
    size = Path(video).stat().st_size
    chunk = size if size <= 64 * 1024 * 1024 else CHUNK
    count = max(1, size // chunk)  # the last chunk takes the remainder
    init = _json(*http("POST", f"{TIKTOK}/post/publish/video/init/", headers=auth, json_body={
        "post_info": {"title": text["caption"][:2200], "privacy_level": privacy, "disable_duet": False,
                      "disable_comment": False, "disable_stitch": False},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
                        "total_chunk_count": count}})[::2], "starting the TikTok upload").get("data", {})
    pid, where = init["publish_id"], init["upload_url"]
    raw = Path(video).read_bytes()
    for i in range(count):
        a = i * chunk
        b = size if i == count - 1 else a + chunk
        status, _, body = http("PUT", where, headers={"Content-Type": "video/mp4",
                                                      "Content-Range": f"bytes {a}-{b - 1}/{size}"}, data=raw[a:b])
        if status >= 400:
            _json(status, body, "uploading to TikTok")
    waited = 0.0
    while True:
        st = _json(*http("POST", f"{TIKTOK}/post/publish/status/fetch/", headers=auth,
                         json_body={"publish_id": pid})[::2], "TikTok processing").get("data", {})
        s = st.get("status")
        if s == "PUBLISH_COMPLETE":
            break
        if s == "FAILED":
            raise PublishError(f"TikTok could not post it: {st.get('fail_reason') or 'unknown reason'}")
        if waited > WAIT_LIMIT:
            raise PublishError("TikTok is still processing after 10 minutes; check the app")
        sleep(WAIT)
        waited += WAIT
    ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
    url = f"https://www.tiktok.com/video/{ids[0]}" if ids else None
    return {"id": pid, "url": url, "privacy": privacy.lower()}


# ---------------------------------------------------------------- the button

def due_post(plan, day: str | dt.date = "today") -> str:
    """The reel to post for a day: approved, prepared, not yet posted everywhere."""
    from .content import parse_date

    day = parse_date(day).isoformat()
    for p in sorted(plan.posts, key=lambda p: p["id"]):
        if p["date"] != day or p["format"] != "reel" or p["status"] in ("proposed", "dropped"):
            continue
        left = [x for x in p["platforms"] if x in SHORT_FORM and x not in (p.get("urls") or {})]
        if left:
            return p["id"]
    raise PublishError(f"no approved reel left to post on {day}")


def publish(plan, post_id: str, *, only: list[str] | None = None, dry_run: bool = False,
            base: str | Path = ".", log=print) -> dict:
    """Post one calendar post's prepared versions to each short-form platform, when he asks."""
    post = plan.post(post_id)
    if post["status"] in ("proposed", "dropped"):
        raise PublishError(f"{post_id} is {post['status']}; approve it on the calendar first")
    folder = post.get("crosspost")
    if not folder or not Path(folder, "crosspost.json").exists():
        raise PublishError(f"{post_id} is not prepared yet: run `stylebrain crosspost {post_id}` first")
    targets = [p for p in post["platforms"] if p in SHORT_FORM and (not only or p in only)]
    if not targets:
        raise PublishError(f"{post_id} has no short-form platforms to post to (planned: {', '.join(post['platforms'])})")
    report: dict = {"post": post_id, "when": dt.datetime.now().isoformat(timespec="seconds"), "dry_run": dry_run,
                    "results": {}}
    for p in targets:
        if p in (post.get("urls") or {}):
            report["results"][p] = {"skipped": "already posted", "url": post["urls"][p]}
            log(f"  {p}: already posted ({post['urls'][p]})")
            continue
        paste = Path(folder, f"{p}.txt")
        if not paste.exists():
            report["results"][p] = {"error": f"missing {paste.name}"}
            log(f"  {p}: not prepared ({paste.name} is missing)")
            continue
        text = read_paste(paste)
        video = text.get("video")
        problems = recheck(p, text, video)
        if problems:
            report["results"][p] = {"error": "; ".join(problems)}
            log(f"  {p}: NOT posted: " + "; ".join(problems))
            continue
        if dry_run:
            report["results"][p] = {"would_post": video}
            log(f"  {p}: ready, would post {video}")
            continue
        try:
            acct = load_account(p, base)
            if p == "youtube-shorts":
                got = post_youtube(video, text, acct)
            elif p == "instagram":
                got = post_instagram(video, text, acct)
            else:
                got = post_tiktok(video, text, acct, base)
        except (PublishError, OSError) as e:
            report["results"][p] = {"error": str(e)}
            log(f"  {p}: NOT posted: {e}")
            continue
        report["results"][p] = got
        plan.record_result(post_id, url=got["url"] or None, platform=p)
        plan.save()  # save after each one, so a later failure never loses a posted link
        extra = "" if got["privacy"] == "public" else f" (posted as {got['privacy']}: make it public in the app)"
        log(f"  {p}: posted {got['url'] or '(link not given yet)'}{extra}")
    logf = Path(folder, "publish-log.json")
    history = json.loads(logf.read_text()) if logf.exists() else []
    logf.write_text(json.dumps(history + [report], indent=2) + "\n")
    return report


def shortcut(where: str | Path, project: str | Path) -> Path:
    """A double-click file that posts today's reel: the 'one button'."""
    where, project = Path(where), Path(project).resolve()
    where.mkdir(parents=True, exist_ok=True)
    bat = where / "Post today's reel.cmd"
    bat.write_text("@echo off\r\n"
                   f'cd /d "{project}"\r\n'
                   "uv run stylebrain publish today\r\n"
                   "echo.\r\npause\r\n")
    sh = where / "post-todays-reel.command"
    sh.write_text(f'#!/bin/sh\ncd "{project}"\nuv run stylebrain publish today\nread -p "Press Enter to close" _\n')
    sh.chmod(0o755)
    return bat


def format_report(r: dict) -> str:
    done = [p for p, x in r["results"].items() if x.get("url") and "skipped" not in x]
    failed = [p for p, x in r["results"].items() if x.get("error")]
    head = "checked (nothing sent)" if r["dry_run"] else f"posted to {len(done)}"
    return f"{r['post']}: {head}" + (f"; {len(failed)} not posted: {', '.join(failed)}" if failed else "")

