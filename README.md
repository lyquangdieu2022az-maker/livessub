# VietSub Live

Web app mobile-first de mo video trong trinh duyet iPhone va hien phu de tieng Viet ngay trong player.

## App lam duoc gi

- Chon video hoac audio tu may va phat ngay trong browser.
- Chay tot theo huong web app tren iPhone Safari va Chrome iOS.
- Tao subtitle tieng Viet dan theo tung doan khi job dang chay.
- Hien overlay subtitle truc tiep tren player thay vi cho tai file xong moi xem.
- Xuat `.srt`, `.vtt`, va `.json` sau khi hoan tat.
- Xoa video goc va audio tam tren server sau khi trich xuat xong.

## Kien truc

- `FastAPI`: API va giao dien web.
- `faster-whisper`: speech-to-text local theo stream segment.
- `imageio-ffmpeg`: tach audio ma khong can cai `ffmpeg` he thong.
- `Gemini API`: dich subtitle sang tieng Viet theo batch, giu dung segmentation.
- `HTML5 video + overlay subtitle`: hien phu de live trong player tren mobile browser.

## Chay local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Mo trinh duyet tai [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Deploy len Render

- Push repo nay len GitHub.
- Trong Render, chon `New +` -> `Blueprint`.
- Chon repo vua push. Render se doc file `render.yaml` o root cua repo.
- O buoc tao service dau tien, nhap `GEMINI_API_KEY` khi Render prompt secret co `sync: false`.
- Deploy xong, mo URL `.onrender.com` cua service.

Mac dinh trong `render.yaml`:

- service chay `Python native runtime`
- health check la `/api/health`
- `numInstances: 1` de khong vo job subtitle dang giu trong RAM
- `WHISPER_MODEL_SIZE=base` de giam ap luc RAM cho Render free plan
- thu muc upload/output dat o `/tmp/...` vi Render mac dinh dung filesystem ephemeral

## Bien moi truong

- `GEMINI_API_KEY`: can de dich subtitle sang tieng Viet.
- `SUBTITLE_TRANSLATION_MODEL`: mac dinh `gemini-2.5-flash`.
- `WHISPER_MODEL_SIZE`: mac dinh `small`.
- `UPLOAD_DIR`: thu muc upload tam.
- `OUTPUT_DIR`: thu muc chua file phu de da xuat.

## Luu y

- Lan dau transcribe, `faster-whisper` se tai model ve may nen doan mo dau co the cham hon.
- Day la web player rieng, khong phai extension chen vao moi website video tren iPhone.
- Video goc duoc tai len server de trich audio, nhung app se xoa ban goc va file audio tam sau khi xu ly.
- Neu chua co `GEMINI_API_KEY`, che do dich tieng Viet se khong chay duoc.
- Job hien tai duoc giu trong bo nho RAM; neu dua len production, nen them queue va storage/job state ben ngoai process.
- Tren Render free plan, service co the cham hoac ngu sau mot thoi gian khong dung. Neu ban muon on dinh hon, nen nang len plan tra phi.
