"""Turn Father Pongthep's Facebook live caption into a YouTube title.

Facebook caption example:
  พิธีมิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23/11/2026 : 6.30 น สัปดาห์ที่ 34 เทศกาลธรรมดา
  ระลึกถึงน.เคลเมนต์ที่1 พระสันตะปาปา และน.โคลัมบัน เจ้าอธิการ ออกอากาศเพื่อผู้เดินไปวัดไม่ได้ ...

YouTube title produced (house style, max 100 characters):
  มิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23 พ.ย. 2026 : 6.30 น สัปดาห์ที่ 34 ...

The chapel, date, time and Saint/feast name are never removed. When the title is too
long, less important words are dropped in a fixed order (see shorten()).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

MAX_TITLE = 100
CHAPEL = "มิสซาวัด น.อันนา ท่าจีน"

THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
THAI_WEEKDAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

# Text after these phrases is the standing "why we broadcast" sentence, not the feast.
BOILERPLATE_STARTS = ["ออกอากาศเพื่อ", "ถ่ายทอดสดเพื่อ", "เพื่อการประกาศพระวรสาร", "เพื่อผู้เดินไปวัดไม่ได้"]

# Descriptive titles of Saints that can be dropped to save space (the Saint's name stays).
SAINT_TITLES = [
    "นักปราชญ์แห่งพระศาสนจักร", "พระสันตะปาปา", "พระสังฆราช", "เจ้าอธิการ", "เจ้าอธิการิณี",
    "นักปราชญ์", "มรณสักขี", "พรหมจารี", "พระสงฆ์", "นักบวช", "ฤษี",
]

DATE_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})")
TIME_RE = re.compile(r":?\s*(\d{1,2})\s*[.:]\s*(\d{2})\s*น\.?")
WEEKDAY_RE = re.compile(r"วัน(" + "|".join(THAI_WEEKDAYS) + r")")
ORDINARY_WEEK_RE = re.compile(r"สัปดาห์ที่\s*\d+\s*(?:เทศกาล\S+)?")


@dataclass
class TitleResult:
    title: str
    description: str
    warnings: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = text.replace("<", "").replace(">", "")  # YouTube rejects these characters
    return re.sub(r"\s+", " ", text).strip()


def _cut_boilerplate(text: str) -> str:
    cut = len(text)
    for phrase in BOILERPLATE_STARTS:
        i = text.find(phrase)
        if i > 0:
            cut = min(cut, i)
    text = text[:cut]
    text = re.sub(r"https?://\S+|#\S+", "", text)
    return _clean(text)


def _format_date(m: re.Match) -> str:
    d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
    if not 1 <= mo <= 12:
        return m.group(0)
    return f"{d} {THAI_MONTHS[mo - 1]} {y}"


def _to_gregorian_year(y: int) -> int:
    return y - 543 if y > 2400 else y


def shorten(header: str, feast: str, limit: int = MAX_TITLE) -> str:
    def join(h, f):
        return _clean(f"{h} {f}")

    title = join(header, feast)
    if len(title) <= limit:
        return title

    # 1) Drop "สัปดาห์ที่ 34 เทศกาลธรรมดา" when there is another feast/Saint named.
    without_week = _clean(ORDINARY_WEEK_RE.sub("", feast))
    if without_week:
        feast = without_week
        title = join(header, feast)
        if len(title) <= limit:
            return title

    # 2) Drop Saints' descriptive titles, one at a time, from the end.
    for word in reversed(sorted(SAINT_TITLES, key=len)):
        pattern = re.compile(r"\s+" + re.escape(word) + r"(?=\s|$)")
        while pattern.search(feast) and len(join(header, feast)) > limit:
            matches = list(pattern.finditer(feast))
            last = matches[-1]
            feast = _clean(feast[:last.start()] + feast[last.end():])
    title = join(header, feast)
    if len(title) <= limit:
        return title

    # 3) Shorter header: "วันจันทร์ที่ 23" -> "จ. 23" is not house style, so instead
    #    drop "ที่" after the weekday.
    header = re.sub(r"(วัน\S+?)ที่ ", r"\1 ", header)
    title = join(header, feast)
    if len(title) <= limit:
        return title

    # 4) Last resort: cut the feast text at a space and add "…".
    room = limit - len(header) - 2
    cut = feast[:room]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return _clean(f"{header} {cut}…")


def make_title(caption: str, live_time: datetime | None = None) -> TitleResult:
    """live_time: when the live started, in Thailand time (used for checks and fallback)."""
    caption = caption or ""
    description = caption.strip().replace("<", "").replace(">", "")
    warnings: list[str] = []
    text = _cut_boilerplate(_clean(caption))

    # Remove "พิธี" in front of "มิสซา" to match the YouTube house style.
    text = re.sub(r"^พิธี\s*(?=มิสซา)", "", text)

    date_m = DATE_RE.search(text)
    time_m = TIME_RE.search(text, date_m.end() if date_m else 0)

    if not date_m:
        if live_time is None:
            warnings.append("ไม่พบวันที่ในโพสต์ ใช้ข้อความโพสต์เป็นชื่อคลิปแทน")
            return TitleResult(shorten("", text) or CHAPEL, description, warnings)
        wd = THAI_WEEKDAYS[live_time.weekday()]
        header = (f"{CHAPEL} วัน{wd}ที่ {live_time.day} {THAI_MONTHS[live_time.month - 1]} "
                  f"{live_time.year} : {live_time.hour}.{live_time.minute:02d} น")
        warnings.append("ไม่พบวันที่ในโพสต์ ใช้วันเวลาที่ไลฟ์แทน กรุณาตรวจชื่อคลิป")
        feast = ""
        if "มิสซา" not in text:
            feast = text
        return TitleResult(shorten(header, feast), description, warnings)

    # Sanity checks: the date written in the post vs. the real live date and weekday.
    d, mo, y = int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))
    try:
        posted = datetime(_to_gregorian_year(y), mo, d)
        wd_m = WEEKDAY_RE.search(text[:date_m.start()])
        if wd_m and THAI_WEEKDAYS[posted.weekday()] != wd_m.group(1):
            warnings.append(f"วันในโพสต์ (วัน{wd_m.group(1)}) ไม่ตรงกับวันที่ {d}/{mo}/{y} "
                            f"(ซึ่งเป็นวัน{THAI_WEEKDAYS[posted.weekday()]})")
        if live_time and posted.date() != live_time.date():
            warnings.append(f"วันที่ในโพสต์ ({d}/{mo}/{y}) ไม่ตรงกับวันที่ไลฟ์จริง "
                            f"({live_time.day}/{live_time.month}/{live_time.year}) "
                            "คุณพ่ออาจคัดลอกข้อความเก่ามา")
    except ValueError:
        warnings.append(f"วันที่ในโพสต์ไม่ถูกต้อง: {date_m.group(0)}")

    end = time_m.end() if time_m else date_m.end()
    header = text[:end]
    header = DATE_RE.sub(_format_date, header)
    header = re.sub(r"\s*:\s*", " : ", header)
    header = re.sub(r"\s*น\.?$", " น", header)
    if not header.startswith("มิสซา"):
        # Post did not start with the usual wording; keep its own beginning.
        warnings.append("ข้อความโพสต์ไม่ได้ขึ้นต้นแบบปกติ กรุณาตรวจชื่อคลิป")
    feast = text[end:]
    # Space between "ระลึกถึงน." -> keep as written by Father, only tidy spaces.
    return TitleResult(shorten(header, feast), description, warnings)
