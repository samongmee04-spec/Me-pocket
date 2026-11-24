"""P mass: copy Father Pongthep's finished Facebook live Masses to his YouTube channel.

Runs on GitHub Actions. Each run:
  1. Looks at the Facebook profile for live videos it has not handled yet.
  2. Skips any that are still live (tries again next run).
  3. Downloads the finished video to a temporary folder (never into the repository).
  4. Writes the YouTube title/description from the Facebook caption (title_rules.py).
  5. Uploads to YouTube, deletes the local file, and emails the result.

Settings come from environment variables (GitHub Secrets) - see README.md.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import smtplib
import ssl
import sys
import tempfile
import time
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http.cookiejar import MozillaCookieJar
from pathlib import Path

from title_rules import make_title

THAI_TZ = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state" / "processed.json"

FB_PROFILE = os.environ.get("FB_PROFILE", "https://www.facebook.com/pongthep.pramualpromp.7").rstrip("/")
YT_PRIVACY = os.environ.get("YT_PRIVACY", "private")  # private | unlisted | public
MAX_AGE_DAYS = 2        # never upload Facebook videos older than this automatically
MAX_ATTEMPTS = 4        # give up on one video after this many failed runs
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def log(*a):
    print(datetime.now(THAI_TZ).strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------- state

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text("utf-8"))
    return {"initialized": False, "videos": {}, "last_alert_day": ""}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


# ----------------------------------------------------------------------------- email

def send_email(subject: str, body: str) -> None:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("NOTIFY_TO") or sender
    if not (sender and password):
        log("EMAIL (not configured):", subject, "\n", body)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"P mass <{sender}>"
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password.replace(" ", ""))
        s.send_message(msg)
    log("Email sent:", subject)


def run_link() -> str:
    server, repo, run_id = (os.environ.get(k) for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run_id}" if run_id else "(local run)"


# ----------------------------------------------------------------------------- Facebook

def cookie_file() -> str | None:
    """FB_COOKIES secret (Netscape cookies.txt text) -> temp file path, if provided."""
    data = os.environ.get("FB_COOKIES", "").strip()
    if not data:
        return None
    path = Path(tempfile.gettempdir()) / "fb_cookies.txt"
    if not data.startswith("# "):
        data = "# Netscape HTTP Cookie File\n" + data
    path.write_text(data + "\n", "utf-8")
    return str(path)


def fetch(url: str, cookies: str | None) -> str:
    handlers = []
    if cookies:
        jar = MozillaCookieJar(cookies)
        jar.load(ignore_discard=True, ignore_expires=True)
        handlers.append(urllib.request.HTTPCookieProcessor(jar))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "th-TH,th;q=0.9,en;q=0.8"})
    with opener.open(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


ID_PATTERNS = [
    re.compile(r"/videos/(?:[\w.\-]+/)?(\d{9,20})"),
    re.compile(r"/watch/?\?v=(\d{9,20})"),
    re.compile(r'"video_id"\s*:\s*"(\d{9,20})"'),
    re.compile(r'"videoId"\s*:\s*"(\d{9,20})"'),
    re.compile(r"/reel/(\d{9,20})"),
]


def discover_video_ids(cookies: str | None) -> list[str]:
    ids: list[str] = []
    pages = [f"{FB_PROFILE}/videos", f"{FB_PROFILE}/live_videos", FB_PROFILE,
             FB_PROFILE.replace("www.facebook.com", "m.facebook.com")]
    for page in pages:
        try:
            text = html.unescape(fetch(page, cookies)).replace("\\/", "/")
        except Exception as e:  # noqa: BLE001
            log("Could not open", page, "-", e)
            continue
        found = [m for p in ID_PATTERNS for m in p.findall(text)]
        log(f"{page}: {len(set(found))} video ids")
        for vid in found:
            if vid not in ids:
                ids.append(vid)
    return ids


def video_url(vid_or_url: str) -> str:
    return vid_or_url if vid_or_url.startswith("http") else f"https://www.facebook.com/watch/?v={vid_or_url}"


def ydl_opts(cookies: str | None, **extra) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "http_headers": {"User-Agent": UA},
            "retries": 10, "fragment_retries": 10, "socket_timeout": 60}
    if cookies:
        opts["cookiefile"] = cookies
    opts.update(extra)
    return opts


def get_info(url: str, cookies: str | None) -> dict:
    import yt_dlp
    with yt_dlp.YoutubeDL(ydl_opts(cookies)) as ydl:
        return ydl.extract_info(url, download=False)


def download(url: str, cookies: str | None, folder: Path) -> Path:
    import yt_dlp
    opts = ydl_opts(
        cookies,
        format="bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        merge_output_format="mp4",
        outtmpl=str(folder / "%(id)s.%(ext)s"),
        concurrent_fragment_downloads=4,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = sorted(folder.glob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
    if not files:
        raise RuntimeError("Download finished but no .mp4 file was produced")
    return files[0]


# ----------------------------------------------------------------------------- YouTube

def youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_info(yt) -> tuple[str, str, list[str]]:
    """(channel title, channel id, titles of the latest uploads)."""
    ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=25).execute().get("items", [])
    return ch["snippet"]["title"], ch["id"], [i["snippet"]["title"] for i in items]


def upload(yt, path: Path, title: str, description: str, recorded: datetime | None) -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {"title": title, "description": description[:5000], "categoryId": "29",
                    "defaultLanguage": "th", "defaultAudioLanguage": "th"},
        "status": {"privacyStatus": YT_PRIVACY, "selfDeclaredMadeForKids": False},
    }
    if recorded:
        body["recordingDetails"] = {"recordingDate": recorded.astimezone(timezone.utc).isoformat()}
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=64 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part=",".join(body), body=body, media_body=media, notifySubscribers=False)
    response, errors = None, 0
    while response is None:
        try:
            status, response = req.next_chunk()
            if status:
                log(f"Upload {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and errors < 8:
                errors += 1
                time.sleep(2 ** errors)
                continue
            raise
    return response["id"]


# ----------------------------------------------------------------------------- main flow

def live_start(info: dict) -> datetime | None:
    ts = info.get("release_timestamp") or info.get("timestamp")
    return datetime.fromtimestamp(ts, THAI_TZ) if ts else None


def process(vid: str, url: str, state: dict, cookies: str | None, manual: bool, dry_run: bool) -> None:
    rec = state["videos"].setdefault(vid, {"status": "new", "attempts": 0})
    if rec.get("status") == "done" and not dry_run:
        log("Already uploaded:", rec.get("youtube_id"))
        return
    info = get_info(url, cookies)
    vid = str(info.get("id") or vid)
    caption = (info.get("description") or info.get("title") or "").strip()
    started = live_start(info)
    live_status = info.get("live_status")
    log(f"Video {vid}: live_status={live_status} started={started} duration={info.get('duration')}")

    if live_status in ("is_live", "is_upcoming", "post_live"):
        log("Still live / replay not ready yet - will try again next run")
        rec["status"] = "waiting"
        return
    if not manual:
        if "มิสซา" not in caption:
            log("Not a Mass video - skipped")
            rec["status"] = "skipped_not_mass"
            return
        if started and datetime.now(THAI_TZ) - started > timedelta(days=MAX_AGE_DAYS):
            log("Older than", MAX_AGE_DAYS, "days - skipped")
            rec["status"] = "skipped_old"
            return

    t = make_title(caption, started)
    warn_text = "\n".join(f"⚠️ {w}" for w in t.warnings)
    log("Title:", t.title, f"({len(t.title)} chars)")

    if dry_run:
        send_email(
            f"[P mass] ทดสอบ (ยังไม่อัปโหลด): {t.title}",
            f"ทดสอบดึงข้อมูลจาก Facebook สำเร็จ ✅\n\nชื่อคลิปที่จะใช้ ({len(t.title)} ตัวอักษร):\n{t.title}\n\n"
            f"{warn_text}\n\nคำอธิบาย:\n{t.description}\n\nFacebook: {url}\nความยาว: "
            f"{round((info.get('duration') or 0) / 60)} นาที\n",
        )
        return

    yt = youtube()
    channel, channel_id, recent_titles = channel_info(yt)
    if t.title in recent_titles:
        log("Same title already on YouTube - skipped (probably uploaded by hand)")
        rec.update(status="skipped_duplicate", title=t.title)
        return

    work = Path(tempfile.mkdtemp(prefix="pmass-"))  # outside the repository
    try:
        file = download(url, cookies, work)
        size_mb = file.stat().st_size // (1024 * 1024)
        log(f"Downloaded {file.name} ({size_mb} MB)")
        yt_id = upload(yt, file, t.title, t.description, started)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # video deleted right after upload
        log("Temporary video files deleted")

    rec.update(status="done", youtube_id=yt_id, title=t.title,
               uploaded_at=datetime.now(THAI_TZ).isoformat(timespec="minutes"))
    send_email(
        f"[P mass] โพสต์แล้ว: {t.title}",
        f"อัปโหลดมิสซาขึ้นช่อง \"{channel}\" เรียบร้อย ✅ ({YT_PRIVACY})\n\n"
        f"ตรวจ/แก้ไข/เปลี่ยนเป็นสาธารณะ: https://studio.youtube.com/video/{yt_id}/edit\n"
        f"ดูคลิป: https://youtu.be/{yt_id}\n\n"
        f"ชื่อคลิป ({len(t.title)} ตัวอักษร):\n{t.title}\n\n{warn_text}\n\n"
        f"ต้นฉบับ Facebook: {url}\n",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="process this one Facebook video link now (manual mode)")
    ap.add_argument("--dry-run", action="store_true", help="read Facebook + make title, no upload")
    args = ap.parse_args()

    state = load_state()
    cookies = cookie_file()
    today = datetime.now(THAI_TZ).strftime("%Y-%m-%d")

    if args.url:
        url = args.url.strip()
        m = re.search(r"(\d{9,20})", url)
        targets = [(m.group(1) if m else url, url, True)]
    else:
        ids = discover_video_ids(cookies)
        if not ids:
            log("Facebook returned no videos (blocked or login required)")
            if state.get("last_alert_day") != today:
                state["last_alert_day"] = today
                send_email("[P mass] ⚠️ เปิดหน้า Facebook ของคุณพ่อไม่ได้",
                           "วันนี้โปรแกรมหาวิดีโอในหน้า Facebook ไม่เจอ อาจโดน Facebook บล็อกหรือบังคับล็อกอิน\n"
                           "ถ้ามีไลฟ์มิสซา กรุณาลงเองครั้งนี้ หรือกด Run workflow พร้อมใส่ลิงก์ไลฟ์ (ดู README)\n"
                           "ถ้าเกิดซ้ำหลายวัน ให้เพิ่ม FB_COOKIES (ดู README)\n\n"
                           f"รายละเอียด: {run_link()}\n(จะแจ้งเตือนเรื่องนี้ไม่เกินวันละครั้ง)")
            save_state(state)
            return 0
        if not state.get("initialized"):
            # First successful run: remember existing videos so old Masses are not re-uploaded.
            for vid in ids:
                state["videos"].setdefault(vid, {"status": "existing_at_setup", "attempts": 0})
            state["initialized"] = True
            save_state(state)
            log(f"First run: remembered {len(ids)} existing videos; new lives will be uploaded from now on")
            return 0
        targets = [(v, video_url(v), False) for v in ids
                   if state["videos"].get(v, {}).get("status", "new") in ("new", "waiting", "error")]
        log(f"{len(targets)} video(s) to check")

    for vid, url, manual in targets:
        rec = state["videos"].setdefault(vid, {"status": "new", "attempts": 0})
        try:
            process(vid, url, state, cookies, manual, args.dry_run)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            rec["attempts"] = rec.get("attempts", 0) + 1
            rec["status"] = "error" if rec["attempts"] < MAX_ATTEMPTS else "failed"
            rec["last_error"] = str(e)[:300]
            if manual or rec["attempts"] == 1 or rec["status"] == "failed":
                final = rec["status"] == "failed" or manual
                send_email(
                    f"[P mass] ❌ {'ลงคลิปไม่สำเร็จ' if final else 'มีปัญหา กำลังลองใหม่'}",
                    f"วิดีโอ: {url}\nปัญหา: {e}\n\n"
                    + ("หยุดลองแล้ว กรุณาลงคลิปนี้เองครั้งนี้\n" if final else
                       f"จะลองใหม่อัตโนมัติ (สูงสุด {MAX_ATTEMPTS} ครั้ง)\n")
                    + f"รายละเอียด: {run_link()}",
                )
        save_state(state)  # save after every video so progress is never lost
    return 0


if __name__ == "__main__":
    sys.exit(main())
