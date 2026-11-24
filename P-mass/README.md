# P mass

ลงคลิปมิสซาจาก Facebook ของคุณพ่อพงษ์เทพ ขึ้นช่อง YouTube ของคุณพ่ออัตโนมัติ
ทำงานบน GitHub Actions ทั้งหมด ไม่ต้องเปิดคอมพิวเตอร์และไม่มีค่าใช้จ่าย

## ทำงานอย่างไร

1. ตรวจหน้า Facebook ของคุณพ่อทุก 15 นาที **เฉพาะช่วงมิสซา** (เวลาประเทศไทย)
   - จ.–ส. 07:00–10:45 และ 17:30–21:45
   - อา. 09:30–12:45
2. เจอไลฟ์ใหม่ที่มีคำว่า "มิสซา" → ถ้ายังไลฟ์อยู่ รอรอบถัดไป → ถ้าจบแล้ว ดาวน์โหลด MP4
3. ตั้งชื่อคลิปตามรูปแบบเดิม (ไม่เกิน 100 ตัวอักษร) และใช้ข้อความ Facebook เต็มเป็นคำอธิบาย
   `มิสซาวัด น.อันนา ท่าจีน วันจันทร์ที่ 23 พ.ย. 2026 : 6.30 น ระลึกถึงน.เคลเมนต์ที่1 และน.โคลัมบัน`
4. อัปโหลดขึ้น YouTube (ไม่แจ้งเตือนผู้ติดตาม) แล้ว **ลบไฟล์วิดีโอทันที** วิดีโอไม่เคยถูกเก็บใน GitHub
   (เก็บแค่รายชื่อคลิปที่ทำแล้วใน `state/processed.json` ขนาดไม่กี่ KB)
5. ส่งอีเมลหาคุณคนเดียว พร้อมลิงก์ตรวจคลิป และคำเตือนถ้าวันที่ในโพสต์ดูผิด
   (เช่น คุณพ่อคัดลอกข้อความเก่ามาแล้วลืมแก้วันที่)

ครั้งแรกที่โปรแกรมเปิด Facebook ได้ มันจะ "จำ" คลิปเก่าทั้งหมดไว้ และจะไม่อัปโหลดคลิปเก่าซ้ำ

---

## ตั้งค่าครั้งเดียว (ประมาณ 30 นาที)

### ขั้น 1: Google Cloud (อนุญาตให้โปรแกรมอัปโหลดเข้าช่อง YouTube)

1. ไปที่ https://console.cloud.google.com → สร้างโปรเจกต์ใหม่ ชื่อ `P mass`
2. เมนู **APIs & Services → Library** → ค้นหา **YouTube Data API v3** → กด **Enable**
3. เมนู **Google Auth Platform** (หรือ OAuth consent screen)
   - **Branding:** ตั้งชื่อแอป `P mass` และใส่อีเมลของคุณ
   - **Audience:** เลือก **External** → กด **Publish app** ให้สถานะเป็น **In production**
     (สำคัญมาก: ถ้าค้างที่ Testing สิทธิ์จะหมดอายุทุก 7 วัน)
   - **Clients → Create client** → ประเภท **Web application**
     → Authorized redirect URIs ใส่ `https://developers.google.com/oauthplayground`
     → กด Create แล้วจด **Client ID** และ **Client secret**

### ขั้น 2: รับ Refresh token (เลือกช่องของคุณพ่อ)

1. เปิด https://developers.google.com/oauthplayground
2. กดรูปเฟือง ⚙️ มุมขวาบน → ติ๊ก **Use your own OAuth credentials** → วาง Client ID และ Client secret
3. ช่องด้านซ้าย "Input your own scopes" วางข้อความนี้ แล้วกด **Authorize APIs**
   ```
   https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly
   ```
4. ล็อกอิน → **เลือกช่อง YouTube ของคุณพ่อ** (ไม่ใช่ช่องของคุณเอง)
   - ถ้าไม่เห็นช่องคุณพ่อในรายการ แปลว่าต้องให้คุณพ่อล็อกอินทำขั้นนี้เองครั้งเดียว
5. ถ้าเจอข้อความ "Google hasn't verified this app" → กด **Advanced** → **Go to P mass** → **Allow**
6. กด **Exchange authorization code for tokens** → คัดลอก **Refresh token**

### ขั้น 3: รหัสผ่านแอปของ Gmail (สำหรับส่งอีเมลแจ้งเตือน)

1. บัญชี Gmail ต้องเปิด **การยืนยันแบบ 2 ขั้นตอน** ไว้ก่อน
2. ไปที่ https://myaccount.google.com/apppasswords → ตั้งชื่อ `P mass` → คัดลอกรหัส 16 ตัว

### ขั้น 4: ใส่รหัสใน GitHub

ใน repo นี้ไปที่ **Settings → Secrets and variables → Actions → New repository secret**
แล้วเพิ่มทีละตัว (รหัสพวกนี้ถูกซ่อน ไม่มีใครเห็นแม้ repo จะเป็นสาธารณะ)

| ชื่อ | ค่า |
|---|---|
| `YT_CLIENT_ID` | Client ID จากขั้น 1 |
| `YT_CLIENT_SECRET` | Client secret จากขั้น 1 |
| `YT_REFRESH_TOKEN` | Refresh token จากขั้น 2 |
| `GMAIL_ADDRESS` | อีเมล Gmail ที่ใช้ส่งและรับแจ้งเตือน |
| `GMAIL_APP_PASSWORD` | รหัส 16 ตัวจากขั้น 3 |
| `NOTIFY_TO` | (ไม่บังคับ) อีเมลผู้รับ ถ้าไม่ใส่จะส่งเข้า `GMAIL_ADDRESS` |
| `FB_COOKIES` | (ไม่บังคับ) ใช้เมื่อ Facebook บล็อก ดูหัวข้อ "ถ้า Facebook บล็อก" |

### ขั้น 5: ทดสอบ

1. แท็บ **Actions** → **P mass** → **Run workflow**
2. ช่องลิงก์: วางลิงก์ไลฟ์ล่าสุดของคุณพ่อ และติ๊ก **ทดสอบเท่านั้น** → Run
3. ภายในไม่กี่นาทีจะได้อีเมล "ทดสอบ (ยังไม่อัปโหลด)" พร้อมชื่อคลิปที่จะใช้
4. ถ้าชื่อถูกต้อง ระบบพร้อมใช้งาน รอมิสซาครั้งถัดไปได้เลย

---

## ใช้งานประจำวัน

- **ไม่ต้องทำอะไร** รออีเมล "[P mass] โพสต์แล้ว"
- กดลิงก์ในอีเมล → ตรวจชื่อคลิป → เปลี่ยนเป็น **สาธารณะ (Public)**
  - ช่วงแรก YouTube บังคับให้คลิปจากโปรแกรมที่ยังไม่ผ่านการตรวจเป็น "ส่วนตัว" ก่อน
  - ถ้าวันหลังอยากให้เผยแพร่เลย: Settings → Secrets and variables → Actions → **Variables**
    → เพิ่ม `YT_PRIVACY` = `public` (หรือ `unlisted`)
- **อยากลงคลิปเฉพาะครั้ง** (เช่นมิสซาพิเศษนอกเวลา หรือ Facebook บล็อก):
  Actions → P mass → Run workflow → วางลิงก์ไลฟ์ → Run (ไม่ต้องติ๊กทดสอบ)

## ถ้า Facebook บล็อก

ถ้าได้อีเมล "เปิดหน้า Facebook ของคุณพ่อไม่ได้" ติดกันหลายวัน:

1. ใช้ **บัญชี Facebook สำรอง** (ไม่ควรใช้บัญชีหลัก) ที่ติดตามคุณพ่อ ล็อกอินใน Chrome
2. ติดตั้งส่วนขยาย **Get cookies.txt LOCALLY** → เปิด facebook.com → Export
3. คัดลอกข้อความทั้งหมดในไฟล์ไปใส่ secret ชื่อ `FB_COOKIES`

## ค่าใช้จ่าย

ฟรีทั้งหมด: GitHub Actions, yt-dlp, YouTube Data API และ Gmail
แนะนำให้ตั้ง repo เป็น **Public** เพราะ GitHub Actions ไม่จำกัดนาทีสำหรับ repo สาธารณะ
(รหัสใน Secrets ยังถูกซ่อนเหมือนเดิม) ถ้าเป็น Private จะมีโควตาฟรี 2,000 นาทีต่อเดือน ซึ่งพอใช้แต่เกือบเต็ม

## ไฟล์ในโปรเจกต์

| ไฟล์ | หน้าที่ |
|---|---|
| `pmass.py` | โปรแกรมหลัก: หาไลฟ์ ดาวน์โหลด อัปโหลด ส่งอีเมล |
| `title_rules.py` | กฎตั้งชื่อคลิปและย่อชื่อให้ไม่เกิน 100 ตัวอักษร |
| `.github/workflows/pmass.yml` | ตารางเวลาทำงาน |
| `state/processed.json` | รายชื่อคลิปที่ทำแล้ว (ไม่มีวิดีโอ) |
| `tests/` | ชุดทดสอบ (`python -m pytest tests`) |
