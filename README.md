# Bmanga — Production/Render

Bản triển khai công khai của website đọc manga.

## Có gì khác bản local
- Đổi thương hiệu KBB Manga -> Bmanga
- Gunicorn cho production
- PostgreSQL qua biến DATABASE_URL
- CSRF protection
- Secure cookie khi chạy production
- ProxyFix cho reverse proxy của Render
- Cloudinary tùy chọn để lưu ảnh bền vững
- Admin lấy từ biến môi trường, không hard-code mật khẩu
- `/health` cho health check
- `render.yaml` để deploy nhanh trên Render

## Chạy local
```bash
pip install -r requirements.txt
python app.py
```

## Deploy Render
1. Đưa toàn bộ project lên GitHub.
2. Trong Render chọn **New + > Blueprint**.
3. Chọn repository chứa project.
4. Render đọc `render.yaml` và tạo Web Service + PostgreSQL.
5. Trong Environment của Web Service đặt:
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
   - `CLOUDINARY_URL` nếu muốn admin upload ảnh trực tiếp.
6. Deploy.

## Cloudinary
Render web filesystem không nên được xem là kho ảnh lâu dài. Khi có `CLOUDINARY_URL`,
ảnh bìa và ảnh chương upload từ Admin sẽ được lưu trên Cloudinary.

Nếu không cấu hình Cloudinary, upload ảnh vẫn chạy khi test local, nhưng không phù hợp để giữ dữ liệu lâu dài trên hosting stateless.

## Admin
Không có mật khẩu admin mặc định trên production.
Tài khoản admin đầu tiên chỉ được tạo khi bạn đặt:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## Lưu ý
Chỉ đăng manga/truyện mà bạn sở hữu hoặc có quyền phân phối.
