# Dữ liệu đã thêm vào project

Project hiện dùng 3 nguồn dữ liệu:

1. `netflix_titles.csv`
   - Dataset danh mục Netflix ban đầu của project.
   - Dùng cho EDA, forecast supply trend và metadata cho recommendation.
   - Dataset gốc chủ yếu có dữ liệu `date_added` đến 2021.

2. `netflix_top10_global_latest.csv`
   - Nguồn: Netflix Tudum Top 10 official all-weeks-global.
   - Dùng để bổ sung độ phổ biến theo tuần: weekly rank, weekly views, weekly hours viewed.
   - Trong dashboard/heatmap, code tạo các dòng bổ sung giai đoạn 2020-2024 từ nguồn này.

3. `netflix_engagement_2025_h1.csv`
   - Nguồn: Netflix Engagement Report.
   - Dùng để bổ sung demand/engagement: hours viewed, runtime, views, available globally.
   - Trong dashboard/heatmap, code tạo các dòng bổ sung giai đoạn 2020-2024 dựa trên `release_date`.

File sinh ra sau khi chạy backend:

- `netflix_titles_cleaned.csv`: dữ liệu danh mục đã làm sạch và đã bổ sung các dòng 2020-2024 từ 2 dataset mới.
- `netflix_unified.csv`: dữ liệu danh mục đã nối thêm popularity + engagement theo `title_key`.

Lưu ý khi viết luận:

- `netflix_titles.csv` là dữ liệu metadata danh mục, cập nhật đến khoảng 2021.
- `netflix_top10_global_latest.csv` và `netflix_engagement_2025_h1.csv` là dữ liệu popularity/engagement công khai từ Netflix, không phải log cá nhân từng người dùng.
- Vì không có lịch sử xem riêng tư của từng user, phần recommendation dùng content-based filtering kết hợp popularity/engagement score.
