# Bmanga Pro Full

Bản full-featured manga reader/admin chạy Flask.

## Người đọc
- Manga / Manhwa / Manhua
- Trang chủ: nổi bật, mới cập nhật, xem nhiều
- Tìm kiếm nâng cao: từ khóa, thể loại, loại truyện, trạng thái, sắp xếp
- Theo dõi truyện
- Lịch sử đọc + lưu tiến độ trang
- Thông báo chương mới cho người theo dõi
- Đánh giá 1–5 sao
- Bình luận + thích bình luận
- Báo lỗi truyện/chương
- Hồ sơ người dùng, điểm danh vọng, VIP flag
- Reader dọc + chế độ 1 trang + fullscreen + phím điều hướng
- Responsive mobile/desktop

## Admin / Editor
- Dashboard thống kê
- CRUD truyện
- CRUD chương
- Upload cover
- Upload nhiều ảnh chương hoặc dùng URL ảnh
- Draft / publish chapter
- Quản lý người dùng, role user/editor/admin, khóa/mở, VIP, điểm
- Kiểm duyệt bình luận
- Quản lý báo lỗi
- Banner
- Cài đặt website + bật/tắt đăng ký
- CSRF protection, password hashing, secure cookie production
- PostgreSQL/SQLite
- Cloudinary tùy chọn cho ảnh production

## Chạy local
```bash
pip install -r requirements.txt
python app.py
```
Mở http://127.0.0.1:5000

## Admin
Đặt biến môi trường trước khi chạy production:
ADMIN_USERNAME
ADMIN_PASSWORD
SECRET_KEY

## Render
Build:
`pip install -r requirements.txt`

Start:
`gunicorn app:app --workers 2 --threads 4 --timeout 120`

Nên dùng PostgreSQL ngoài (Supabase/Neon/Render Postgres) và Cloudinary/R2 cho ảnh. SQLite + filesystem chỉ phù hợp test.

## Lưu ý
Đây là một codebase độc lập lấy cảm hứng từ nhóm tính năng phổ biến của website đọc truyện; không sao chép thương hiệu/giao diện độc quyền của website khác. Chỉ đăng nội dung bạn có quyền phân phối.
