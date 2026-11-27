import json
import subprocess
from pathlib import Path

import pytest

from stylebrain import crosspost, publish
from stylebrain.cli import main
from stylebrain.content import Plan

DAY = "2026-11-30"


class FakeApps:
    """Stands in for Google, Meta and TikTok: records every call and answers like they do."""

    def __init__(self):
        self.calls = []
        self.ig_polls = 0
        self.fail = set()

    def __call__(self, method, url, *, headers=None, data=None, params=None, form=None, json_body=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "params": params, "form": form,
                           "json": json_body, "size": len(data) if data else 0})
        j = lambda d, code=200, h=None: (code, h or {}, json.dumps(d).encode())  # noqa: E731
        for name in self.fail:
            if name in url:
                return j({"error": {"message": f"{name} is down"}}, 500)
        if url == publish.GOOGLE_TOKEN:
            return j({"access_token": "g-access"})
        if url.startswith(publish.YT_UPLOAD) and method == "POST":
            return j({}, 200, {"location": "https://upload.example/yt-session"})
        if url == "https://upload.example/yt-session":
            return j({"id": "abc123"})
        if url.endswith("/media") and method == "POST":
            return j({"id": "container1"})
        if url.startswith(publish.RUPLOAD):
            return j({"success": True})
        if url.endswith("/container1"):
            self.ig_polls += 1
            return j({"status_code": "FINISHED" if self.ig_polls > 1 else "IN_PROGRESS"})
        if url.endswith("/media_publish"):
            return j({"id": "media9"})
        if url.endswith("/media9"):
            return j({"permalink": "https://www.instagram.com/reel/XYZ/"})
        if "creator_info" in url:
            return j({"data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]}})
        if url.endswith("/video/init/"):
            return j({"data": {"publish_id": "pub1", "upload_url": "https://upload.example/tt"}})
        if url == "https://upload.example/tt":
            return j({}, 201)
        if url.endswith("/status/fetch/"):
            return j({"data": {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [777]}})
        return j({"error": {"message": f"unexpected {method} {url}"}}, 404)

    def hits(self, part):
        return [c for c in self.calls if part in c["url"]]


@pytest.fixture
def apps(monkeypatch):
    fake = FakeApps()
    monkeypatch.setattr(publish, "http", fake)
    monkeypatch.setattr(publish, "sleep", lambda s: None)
    return fake


def _video(path, w=1080, h=1920):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:r=30:d=1",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def setup(tmp_path, hook="One bench cue that works", status="planned"):
    plan = Plan(tmp_path)
    vid = tmp_path / "cut.mp4"
    _video(vid)
    i = plan.add_idea("Bench tip", "strength", hook=hook, draft=str(vid), status="edited")
    p = plan.schedule(i["id"], DAY, cta="save", status=status)
    crosspost.make(plan, p["id"], base=tmp_path)
    for name, acct in {"youtube": {"client_id": "c", "client_secret": "s", "refresh_token": "r"},
                       "instagram": {"ig_user_id": "17", "access_token": "page-token", "username": "me"},
                       "tiktok": {"client_key": "k", "client_secret": "s", "refresh_token": "r",
                                  "access_token": "t-access", "expires": 9e12}}.items():
        publish.save_account(name, acct, tmp_path)
    plan.save()
    return plan, p["id"]


def test_one_press_posts_to_all_three_and_records_links(tmp_path, apps):
    plan, pid = setup(tmp_path)
    r = publish.publish(plan, pid, base=tmp_path, log=lambda *a: None)
    assert set(r["results"]) == {"instagram", "tiktok", "youtube-shorts"}
    urls = plan.post(pid)["urls"]
    assert urls["youtube-shorts"] == "https://youtube.com/shorts/abc123"
    assert urls["instagram"] == "https://www.instagram.com/reel/XYZ/"
    assert urls["tiktok"] == "https://www.tiktok.com/video/777"
    assert plan.post(pid)["status"] == "posted"
    # what was sent: the prepared words, public on YouTube, Reels with the caption, private TikTok until audited
    yt = apps.hits("uploadType")[0] if apps.hits("uploadType") else apps.hits(publish.YT_UPLOAD)[0]
    assert yt["json"]["status"]["privacyStatus"] == "public" and yt["json"]["snippet"]["title"] == "Bench tip"
    ig = apps.hits("/17/media")[0]["form"]
    assert ig["media_type"] == "REELS" and ig["caption"].startswith("One bench cue")
    assert apps.hits(publish.RUPLOAD)[0]["size"] > 0
    tt = apps.hits("/video/init/")[0]["json"]
    assert tt["post_info"]["privacy_level"] == "SELF_ONLY" and tt["source_info"]["source"] == "FILE_UPLOAD"
    assert r["results"]["tiktok"]["privacy"] == "self_only"
    # pressing again posts nothing twice
    n = len(apps.calls)
    again = publish.publish(plan, pid, base=tmp_path, log=lambda *a: None)
    assert len(apps.calls) == n and all("skipped" in x for x in again["results"].values())
    assert json.loads(Path(plan.post(pid)["crosspost"], "publish-log.json").read_text())[-1]["post"] == pid


def test_audited_tiktok_posts_public(tmp_path, apps):
    plan, pid = setup(tmp_path)
    acct = publish.load_account("tiktok", tmp_path)
    publish.save_account("tiktok", {**acct, "audited": True}, tmp_path)
    publish.publish(plan, pid, only=["tiktok"], base=tmp_path, log=lambda *a: None)
    assert apps.hits("/video/init/")[0]["json"]["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"


def test_problems_block_only_that_platform_and_edits_count(tmp_path, apps):
    plan, pid = setup(tmp_path, hook="I hit [weight] today")
    folder = Path(plan.post(pid)["crosspost"])
    # he fixes the Instagram caption by hand; the others keep the placeholder
    ig = folder / "instagram.txt"
    ig.write_text(ig.read_text().replace("[weight]", "250 kg"))
    r = publish.publish(plan, pid, base=tmp_path, log=lambda *a: None)
    assert r["results"]["instagram"]["url"]
    assert "[weight]" in r["results"]["tiktok"]["error"] and "[weight]" in r["results"]["youtube-shorts"]["error"]
    assert "250 kg" in apps.hits("/17/media")[0]["form"]["caption"]
    assert not apps.hits("/video/init/") and not apps.hits(publish.YT_UPLOAD)


def test_one_app_down_does_not_stop_the_others(tmp_path, apps):
    plan, pid = setup(tmp_path)
    apps.fail.add("tiktokapis")
    r = publish.publish(plan, pid, base=tmp_path, log=lambda *a: None)
    assert "down" in r["results"]["tiktok"]["error"]
    assert set(plan.post(pid)["urls"]) == {"instagram", "youtube-shorts"}


def test_guards(tmp_path, apps):
    plan, pid = setup(tmp_path, status="proposed")
    with pytest.raises(publish.PublishError, match="approve it"):
        publish.publish(plan, pid, base=tmp_path)
    plan.set_post(pid, status="planned")
    (publish.accounts_dir(tmp_path) / "instagram.json").unlink()
    r = publish.publish(plan, pid, only=["instagram"], base=tmp_path, log=lambda *a: None)
    assert "connect instagram" in r["results"]["instagram"]["error"]
    dry = publish.publish(plan, pid, dry_run=True, base=tmp_path, log=lambda *a: None)
    assert dry["dry_run"] and not apps.calls


def test_read_paste_round_trip(tmp_path):
    v = crosspost.Version("youtube", "YouTube", {"title": "T", "description": "line one\n\nline two", "tags": ["a", "b c"]},
                          [], "none", "x.mp4", problems=["p"], notes=["n"])
    f = tmp_path / "youtube.txt"
    f.write_text(v.paste())
    got = publish.read_paste(f)
    assert got == {"video": "x.mp4", "title": "T", "description": "line one\n\nline two", "tags": ["a", "b c"]}


def test_due_post_and_cli(tmp_path, apps, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    plan, pid = setup(tmp_path)
    assert publish.due_post(plan, DAY) == pid
    with pytest.raises(publish.PublishError, match="no approved reel"):
        publish.due_post(plan, "2026-12-25")
    main(["publish", DAY])
    out = capsys.readouterr().out
    assert "posted to 3" in out and "make it public in the app" in out
    main(["publish-shortcut", str(tmp_path / "desk")])
    bat = (tmp_path / "desk" / "Post today's reel.cmd").read_text()
    assert "stylebrain publish today" in bat
