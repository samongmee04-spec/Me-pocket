import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pmass  # noqa: E402

CAPTION = ("พิธีมิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23/11/2026 : 6.30 น สัปดาห์ที่ 34 เทศกาลธรรมดา "
           "ระลึกถึงน.เคลเมนต์ที่1 พระสันตะปาปา และน.โคลัมบัน เจ้าอธิการ ออกอากาศเพื่อผู้เดินไปวัดไม่ได้")


def setup(monkeypatch, tmp_path, ids, infos):
    monkeypatch.setattr(pmass, "STATE_FILE", tmp_path / "processed.json")
    monkeypatch.setattr(pmass, "discover_video_ids", lambda c: list(ids))
    monkeypatch.setattr(pmass, "get_info", lambda url, c: infos[url.split("v=")[-1]])
    now = datetime(2026, 11, 23, 8, 0, tzinfo=pmass.THAI_TZ)

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(pmass, "datetime", FakeDT)
    emails, uploads, files = [], [], []
    monkeypatch.setattr(pmass, "send_email", lambda s, b: emails.append((s, b)))
    monkeypatch.setattr(pmass, "youtube", lambda: object())
    monkeypatch.setattr(pmass, "channel_info", lambda yt: ("Pongthep", "UC1", []))

    def fake_download(url, c, folder):
        f = folder / "v.mp4"
        f.write_bytes(b"x" * 10)
        files.append(f)
        return f

    monkeypatch.setattr(pmass, "download", fake_download)
    monkeypatch.setattr(pmass, "upload", lambda yt, p, t, d, r: uploads.append(t) or "YT123")
    monkeypatch.setattr(sys, "argv", ["pmass.py"])
    return emails, uploads, files


def info(vid, status="was_live", caption=CAPTION, ts=datetime(2026, 11, 23, 6, 30, tzinfo=pmass.THAI_TZ)):
    return {"id": vid, "live_status": status, "description": caption, "timestamp": ts.timestamp(), "duration": 3600}


def test_full_flow(monkeypatch, tmp_path):
    ids = ["111111111"]
    infos = {"111111111": info("111111111"), "222222222": info("222222222", status="is_live"),
             "333333333": info("333333333")}
    emails, uploads, files = setup(monkeypatch, tmp_path, ids, infos)

    pmass.main()  # first run: only remembers existing videos
    assert uploads == [] and pmass.load_state()["initialized"]

    ids[:0] = ["222222222"]  # new live, still running
    pmass.main()
    assert uploads == [] and pmass.load_state()["videos"]["222222222"]["status"] == "waiting"

    infos["222222222"]["live_status"] = "was_live"  # live finished
    pmass.main()
    assert len(uploads) == 1 and uploads[0].startswith("มิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23 พ.ย. 2026")
    assert pmass.load_state()["videos"]["222222222"]["status"] == "done"
    assert not files[0].exists() and not files[0].parent.exists()  # video deleted
    assert "โพสต์แล้ว" in emails[-1][0] and "YT123" in emails[-1][1]

    pmass.main()  # nothing new -> no second upload
    assert len(uploads) == 1


def test_non_mass_video_is_ignored(monkeypatch, tmp_path):
    ids = ["111111111"]
    infos = {"111111111": info("111111111"), "444444444": info("444444444", caption="ทำบุญวันเกิด")}
    emails, uploads, _ = setup(monkeypatch, tmp_path, ids, infos)
    pmass.main()
    ids.insert(0, "444444444")
    pmass.main()
    assert uploads == [] and pmass.load_state()["videos"]["444444444"]["status"] == "skipped_not_mass"


def test_blocked_facebook_alerts_once_per_day(monkeypatch, tmp_path):
    emails, uploads, _ = setup(monkeypatch, tmp_path, [], {})
    pmass.main()
    pmass.main()
    assert len(emails) == 1 and "Facebook" in emails[0][0]
