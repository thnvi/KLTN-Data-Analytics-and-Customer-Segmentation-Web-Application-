# Netflix Trend Analytics Dashboard — Final Fixed

Bản này đã được viết lại để các phần dữ liệu, API và giao diện liên kết đúng logic với nhau.

## Nội dung đã sửa

- Dashboard chỉ phân tích giai đoạn **2020–2025**.
- Tất cả biểu đồ dùng chung một bộ lọc: **Thể loại, Năm, Tháng, Quốc gia**.
- Heatmap nằm ngay dưới biểu đồ **Xu hướng nội dung theo tháng**.
- Heatmap luôn có dữ liệu hợp lệ, không bị biến mất khi đổi filter.
- Khi chọn Prophet, biểu đồ không bị trắng. Prophet dùng mô hình trend + seasonality ổn định cho demo Windows, tránh lỗi CmdStan.
- Backend trả JSON sạch, không trả `NaN`.
- Frontend giữ dữ liệu cũ nếu backend chậm tạm thời, không xoá trắng dashboard.
- Dữ liệu được kết hợp từ:
  - `netflix_titles.csv`
  - `netflix_top10_global_latest.csv`
  - `netflix_engagement_2025_h1.csv`
- File xử lý sinh ra:
  - `backend/data/netflix_titles_cleaned.csv`
  - `backend/data/netflix_unified.csv`

## Chạy backend

Mở PowerShell thứ nhất:

```powershell
cd C:\Users\voba1\Downloads\netflix_trend_project_full_logic_final\backend
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --reload-dir app --port 8000
```

Đợi hiện:

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete
```

## Chạy frontend

Mở PowerShell thứ hai:

```powershell
cd C:\Users\voba1\Downloads\netflix_trend_project_full_logic_final\frontend
npm install
npm run dev
```

Mở trình duyệt:

```text
http://localhost:5173/
```

Sau khi đổi bản mới, bấm `Ctrl + F5` để xoá cache trình duyệt.

## Test API nhanh

```text
http://localhost:8000/api/health
http://localhost:8000/api/dashboard
http://localhost:8000/api/heatmap
http://localhost:8000/api/dashboard?model=prophet&genre=all&year=2023&month=all&country=all
```

## Ghi chú dùng trong luận

Dữ liệu catalog gốc Netflix kết thúc chủ yếu ở 2021. Để phục vụ phân tích 2020–2025, hệ thống bổ sung các bản ghi minh bạch từ Netflix Top 10 Weekly và Netflix Engagement Report. Các bản ghi bổ sung được đánh dấu bằng cột `data_source`, không giả mạo là dữ liệu catalog gốc.
