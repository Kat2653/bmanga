# Bmanga Portal Full

Bản web truyện độc lập, có bố cục/nhóm chức năng tương đương các cổng đọc manga phổ biến nhưng dùng nhận diện Bmanga riêng. Không kèm nội dung truyện của website bên thứ ba.

## Có sẵn
- Trang chủ: truyện hot, mới cập nhật, xem nhiều, theo dõi nhiều, banner.
- Tìm kiếm/lọc: từ khóa, thể loại, loại Manga/Manhwa/Manhua, trạng thái, sắp xếp.
- Xếp hạng top theo view/theo dõi/cập nhật.
- Trang chi tiết: metadata, thể loại, mô tả, chương, view/follow/rating.
- Reader: đọc dọc, 1 trang, fullscreen, chương trước/sau, lưu tiến độ.
- Thành viên: đăng ký, đăng nhập, theo dõi, lịch sử, đổi mật khẩu, thông báo.
- Bình luận, trả lời, like, báo lỗi.
- Nhóm dịch.
- Admin: dashboard, CRUD truyện/chương, upload nhiều ảnh, import chương ZIP, import cả bộ ZIP, user/role/VIP/ban, bình luận, báo lỗi, banner, nhóm, cài đặt, backup JSON.
- PostgreSQL qua `DATABASE_URL`; Cloudinary qua `CLOUDINARY_URL`.
- Sitemap, robots, health check.

## Rất quan trọng trên Render
Render filesystem không nên dùng để giữ dữ liệu/ảnh lâu dài. Để tránh mất dữ liệu:
1. Tạo PostgreSQL và đặt `DATABASE_URL`.
2. Tạo Cloudinary và đặt `CLOUDINARY_URL` nếu bạn upload ảnh.
3. Đặt `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

Nếu chưa có Cloudinary, hệ thống vẫn lưu ảnh local để test nhưng ảnh có thể mất sau redeploy/restart trên host ephemeral.

## Biến môi trường
Xem `.env.example`.

## Chạy local
```bash
pip install -r requirements.txt
python app.py
```

## Import cả bộ bằng ZIP
Trong Admin -> Import cả bộ. ZIP khuyên dùng:
```text
metadata.json
cover.jpg
Chapter 1/001.jpg
Chapter 1/002.jpg
Chapter 2/001.jpg
```

`metadata.json` ví dụ:
```json
{
  "title": "Tên truyện",
  "author": "Tác giả",
  "artist": "Họa sĩ",
  "genres": ["Comedy", "Romance"],
  "type": "Manga",
  "status": "Đang tiến hành",
  "description": "Mô tả"
}
```

Chỉ upload nội dung bạn có quyền phân phối.
