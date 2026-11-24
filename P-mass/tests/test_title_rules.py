import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from title_rules import MAX_TITLE, make_title  # noqa: E402

SAMPLE_23_NOV = (
    "พิธีมิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23/11/2026 : 6.30 น สัปดาห์ที่ 34 เทศกาลธรรมดา "
    "ระลึกถึงน.เคลเมนต์ที่1 พระสันตะปาปา และน.โคลัมบัน เจ้าอธิการ "
    "ออกอากาศเพื่อผู้เดินไปวัดไม่ได้ เพื่อการประกาศพระวรสารในโลกปัจจุบัน"
)


def test_sample_from_facebook():
    r = make_title(SAMPLE_23_NOV, datetime(2026, 11, 23, 6, 30))
    print(len(r.title), r.title)
    assert len(r.title) <= MAX_TITLE
    assert r.title.startswith("มิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23 พ.ย. 2026 : 6.30 น")
    assert "เคลเมนต์" in r.title and "โคลัมบัน" in r.title
    assert "ออกอากาศ" not in r.title
    assert r.warnings == []
    assert r.description.startswith("พิธีมิสซาวัด")


def test_matches_existing_youtube_style():
    post = ("พิธีมิสซาวัด น.อันนา ท่าจีน วันพฤหัสบดีที่ 1/1/2026 : 9.00 น "
            "สมโภชพระนางมารีย์ พระชนนีของพระเจ้า ออกอากาศเพื่อผู้เดินไปวัดไม่ได้")
    r = make_title(post, datetime(2026, 1, 1, 9, 0))
    assert r.title == ("มิสซาวัด น.อันนา ท่าจีน วันพฤหัสบดีที่ 1 ม.ค. 2026 : 9.00 น "
                       "สมโภชพระนางมารีย์ พระชนนีของพระเจ้า")


def test_wrong_date_is_flagged():
    r = make_title(SAMPLE_23_NOV, datetime(2026, 11, 24, 6, 30))
    assert any("ไม่ตรงกับวันที่ไลฟ์" in w for w in r.warnings)


def test_wrong_weekday_is_flagged():
    r = make_title(SAMPLE_23_NOV.replace("วันจันทร์", "วันอังคาร"), datetime(2026, 11, 23, 6, 30))
    assert any("ไม่ตรงกับวันที่" in w for w in r.warnings)


def test_no_date_falls_back_to_live_time():
    r = make_title("มิสซาเช้านี้ สมโภชพระคริสตเจ้ากษัตริย์", datetime(2026, 11, 22, 9, 0))
    assert r.title.startswith("มิสซาวัด น.อันนา ท่าจีน วันอาทิตย์ที่ 22 พ.ย. 2026 : 9.00 น")
    assert r.warnings


def test_very_long_feast_is_cut_but_keeps_header():
    post = ("พิธีมิสซาวัด น.อันนา ท่าจีน วันเสาร์ที่ 28/11/2026 : 17.00 น "
            + "ระลึกถึงนักบุญผู้มีชื่อยาวมาก " * 8)
    r = make_title(post, datetime(2026, 11, 28, 17, 0))
    assert len(r.title) <= MAX_TITLE
    assert "28 พ.ย. 2026" in r.title and "17.00 น" in r.title
