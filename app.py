import os, json, uuid
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

try:
    import cloudinary
    import cloudinary.uploader
except Exception:
    cloudinary = None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'bmanga.db')}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    SQLALCHEMY_DATABASE_URI=DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

def now():
    return datetime.utcnow()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class Manga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    alt_title = db.Column(db.String(255), default="")
    author = db.Column(db.String(255), default="")
    artist = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    genres = db.Column(db.String(500), default="")
    status = db.Column(db.String(50), default="Đang tiến hành")
    cover = db.Column(db.Text, default="")
    featured = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True)
    number = db.Column(db.Float, nullable=False)
    title = db.Column(db.String(255), default="")
    pages_json = db.Column(db.Text, default="[]")
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    manga = db.relationship("Manga", backref=db.backref("chapters", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("manga_id", "number"),)

class Bookmark(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class History(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    read_at = db.Column(db.DateTime, nullable=False, default=now)

class Rating(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    score = db.Column(db.Integer, nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship("User")
    manga = db.relationship("Manga")

def seed():
    db.create_all()
    admin_user = os.environ.get("ADMIN_USERNAME")
    admin_pass = os.environ.get("ADMIN_PASSWORD")
    if admin_user and admin_pass and not User.query.filter_by(username=admin_user).first():
        db.session.add(User(username=admin_user, password_hash=generate_password_hash(admin_pass), role="admin"))
        db.session.commit()

    if Manga.query.count() == 0:
        samples = [
            Manga(title="Kiếm Sĩ Bóng Đêm", slug="kiem-si-bong-dem", author="Bmanga Studio",
                  artist="Bmanga Studio", description="Truyện mẫu để kiểm tra hệ thống.",
                  genres="Hành động,Phiêu lưu", status="Đang tiến hành", featured=True),
            Manga(title="Thám Tử Phòng 404", slug="tham-tu-phong-404", author="Bmanga Studio",
                  artist="Bmanga Studio", description="Truyện mẫu để kiểm tra hệ thống.",
                  genres="Bí ẩn,Hài", status="Đang tiến hành", featured=True),
        ]
        db.session.add_all(samples)
        db.session.commit()
        for m in samples:
            for n in range(1, 4):
                db.session.add(Chapter(
                    manga_id=m.id, number=float(n), title=f"Chương {n}",
                    pages_json=json.dumps([
                        f"/static/demo/page-{((n-1)%3)+1}.svg",
                        f"/static/demo/page-{((n)%3)+1}.svg",
                        f"/static/demo/page-{((n+1)%3)+1}.svg",
                    ])
                ))
        db.session.commit()

with app.app_context():
    seed()

def current_user():
    return db.session.get(User, session.get("uid")) if session.get("uid") else None

@app.context_processor
def inject_user():
    return {"me": current_user()}

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Bạn cần đăng nhập.", "warning")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u or u.role != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def latest_number(manga_id):
    c = Chapter.query.filter_by(manga_id=manga_id).order_by(Chapter.number.desc()).first()
    return c.number if c else None

@app.route("/")
def home():
    featured = Manga.query.filter_by(featured=True).order_by(Manga.updated_at.desc()).limit(8).all()
    latest = Manga.query.order_by(Manga.updated_at.desc()).limit(16).all()
    popular = Manga.query.order_by(Manga.views.desc()).limit(8).all()
    for group in (featured, latest, popular):
        for m in group:
            m.latest = latest_number(m.id)
    return render_template("home.html", featured=featured, latest=latest, popular=popular)

@app.route("/search")
def search():
    q = request.args.get("q","").strip()
    genre = request.args.get("genre","").strip()
    status = request.args.get("status","").strip()
    qry = Manga.query
    if q:
        like = f"%{q}%"
        qry = qry.filter(db.or_(Manga.title.ilike(like), Manga.alt_title.ilike(like), Manga.author.ilike(like)))
    if genre:
        qry = qry.filter(Manga.genres.ilike(f"%{genre}%"))
    if status:
        qry = qry.filter_by(status=status)
    rows = qry.order_by(Manga.updated_at.desc()).all()
    for m in rows:
        m.latest = latest_number(m.id)
    return render_template("search.html", rows=rows, q=q, genre=genre, status=status)

@app.route("/manga/<slug>")
def manga_detail(slug):
    m = Manga.query.filter_by(slug=slug).first_or_404()
    m.views += 1
    db.session.commit()
    chapters = Chapter.query.filter_by(manga_id=m.id).order_by(Chapter.number.desc()).all()
    scores = [r.score for r in Rating.query.filter_by(manga_id=m.id).all()]
    rating = type("R", (), {"avg": round(sum(scores)/len(scores),1) if scores else None, "c": len(scores)})()
    comments = Comment.query.filter_by(manga_id=m.id).order_by(Comment.id.desc()).limit(50).all()
    bookmarked = bool(current_user() and Bookmark.query.filter_by(user_id=current_user().id, manga_id=m.id).first())
    return render_template("manga.html", m=m, chapters=chapters, rating=rating, comments=comments, bookmarked=bookmarked)

@app.route("/read/<int:chapter_id>")
def read_chapter(chapter_id):
    c = db.session.get(Chapter, chapter_id)
    if not c: abort(404)
    c.views += 1
    prevc = Chapter.query.filter(Chapter.manga_id==c.manga_id, Chapter.number<c.number).order_by(Chapter.number.desc()).first()
    nextc = Chapter.query.filter(Chapter.manga_id==c.manga_id, Chapter.number>c.number).order_by(Chapter.number.asc()).first()
    u = current_user()
    if u:
        h = History.query.filter_by(user_id=u.id, manga_id=c.manga_id).first()
        if h:
            h.chapter_id, h.read_at = c.id, now()
        else:
            db.session.add(History(user_id=u.id, manga_id=c.manga_id, chapter_id=c.id))
    db.session.commit()
    c.manga_title = c.manga.title
    c.slug = c.manga.slug
    pages = json.loads(c.pages_json or "[]")
    return render_template("reader.html", c=c, pages=pages, prevc=prevc, nextc=nextc)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if len(username)<3 or len(password)<6:
            flash("Tên đăng nhập ≥3 ký tự, mật khẩu ≥6 ký tự.","danger")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Tên đăng nhập đã tồn tại.","danger")
            return redirect(url_for("register"))
        db.session.add(User(username=username, password_hash=generate_password_hash(password)))
        db.session.commit()
        flash("Tạo tài khoản thành công.","success")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username","").strip()).first()
        if u and check_password_hash(u.password_hash, request.form.get("password","")):
            session["uid"] = u.id
            return redirect(request.args.get("next") or url_for("home"))
        flash("Sai tài khoản hoặc mật khẩu.","danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.post("/bookmark/<int:manga_id>")
@login_required
def bookmark(manga_id):
    u = current_user()
    b = Bookmark.query.filter_by(user_id=u.id, manga_id=manga_id).first()
    if b:
        db.session.delete(b)
    else:
        db.session.add(Bookmark(user_id=u.id, manga_id=manga_id))
    db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.post("/rate/<int:manga_id>")
@login_required
def rate(manga_id):
    score = max(1,min(5,int(request.form.get("score",5))))
    u = current_user()
    r = Rating.query.filter_by(user_id=u.id, manga_id=manga_id).first()
    if r: r.score = score
    else: db.session.add(Rating(user_id=u.id, manga_id=manga_id, score=score))
    db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.post("/comment/<int:manga_id>")
@login_required
def comment(manga_id):
    body = request.form.get("body","").strip()
    if body:
        db.session.add(Comment(user_id=current_user().id, manga_id=manga_id, body=body[:1000]))
        db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.route("/me")
@login_required
def profile():
    u = current_user()
    bookmarks = [db.session.get(Manga, b.manga_id) for b in Bookmark.query.filter_by(user_id=u.id).order_by(Bookmark.created_at.desc()).all()]
    hist_rows = History.query.filter_by(user_id=u.id).order_by(History.read_at.desc()).all()
    history = []
    for h in hist_rows:
        m = db.session.get(Manga, h.manga_id)
        c = db.session.get(Chapter, h.chapter_id)
        history.append(type("H", (), {"read_at":h.read_at, "title":m.title, "slug":m.slug, "chapter_id":c.id, "number":c.number})())
    return render_template("profile.html", bookmarks=bookmarks, history=history)

def upload_image(file, folder):
    if not file or not file.filename:
        return ""
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in [".jpg",".jpeg",".png",".webp",".gif"]:
        return ""
    if cloudinary and os.environ.get("CLOUDINARY_URL"):
        result = cloudinary.uploader.upload(file, folder=f"bmanga/{folder}", resource_type="image")
        return result["secure_url"]
    # Local fallback for development only.
    target_dir = os.path.join(BASE_DIR, "static", "uploads", folder)
    os.makedirs(target_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(target_dir, name))
    return f"/static/uploads/{folder}/{name}"

@app.route("/admin")
@admin_required
def admin():
    stats = {
        "manga": Manga.query.count(),
        "chapters": Chapter.query.count(),
        "users": User.query.count(),
        "comments": Comment.query.count(),
    }
    mangas = Manga.query.order_by(Manga.updated_at.desc()).all()
    users = User.query.order_by(User.id.desc()).limit(100).all()
    comments = Comment.query.order_by(Comment.id.desc()).limit(100).all()
    return render_template("admin.html", stats=stats, mangas=mangas, users=users, comments=comments)

@app.route("/admin/manga/new", methods=["GET","POST"])
@admin_required
def admin_manga_new():
    if request.method == "POST":
        slug = request.form["slug"].strip()
        if Manga.query.filter_by(slug=slug).first():
            flash("Slug đã tồn tại.","danger")
            return redirect(request.url)
        cover = upload_image(request.files.get("cover"), "covers")
        m = Manga(
            title=request.form["title"].strip(), slug=slug,
            alt_title=request.form.get("alt_title",""), author=request.form.get("author",""),
            artist=request.form.get("artist",""), description=request.form.get("description",""),
            genres=request.form.get("genres",""), status=request.form.get("status","Đang tiến hành"),
            cover=cover, featured=bool(request.form.get("featured"))
        )
        db.session.add(m); db.session.commit()
        flash("Đã thêm truyện.","success")
        return redirect(url_for("admin"))
    return render_template("admin_manga_form.html", m=None)

@app.route("/admin/manga/<int:mid>/edit", methods=["GET","POST"])
@admin_required
def admin_manga_edit(mid):
    m = db.session.get(Manga, mid)
    if not m: abort(404)
    if request.method == "POST":
        m.title = request.form["title"].strip()
        m.slug = request.form["slug"].strip()
        m.alt_title = request.form.get("alt_title","")
        m.author = request.form.get("author","")
        m.artist = request.form.get("artist","")
        m.description = request.form.get("description","")
        m.genres = request.form.get("genres","")
        m.status = request.form.get("status","Đang tiến hành")
        m.featured = bool(request.form.get("featured"))
        cover = upload_image(request.files.get("cover"), "covers")
        if cover: m.cover = cover
        m.updated_at = now()
        db.session.commit()
        flash("Đã cập nhật.","success")
        return redirect(url_for("admin"))
    return render_template("admin_manga_form.html", m=m)

@app.post("/admin/manga/<int:mid>/delete")
@admin_required
def admin_manga_delete(mid):
    m = db.session.get(Manga, mid)
    if m: db.session.delete(m); db.session.commit()
    flash("Đã xóa truyện.","success")
    return redirect(url_for("admin"))

@app.route("/admin/manga/<int:mid>/chapter/new", methods=["GET","POST"])
@admin_required
def admin_chapter_new(mid):
    m = db.session.get(Manga, mid)
    if not m: abort(404)
    if request.method == "POST":
        number = float(request.form["number"])
        if Chapter.query.filter_by(manga_id=mid, number=number).first():
            flash("Chương này đã tồn tại.","danger")
            return redirect(request.url)
        pages = [u.strip() for u in request.form.get("page_urls","").splitlines() if u.strip()]
        for f in request.files.getlist("pages"):
            url = upload_image(f, f"chapters/{mid}/{str(number).replace('.','_')}")
            if url: pages.append(url)
        db.session.add(Chapter(manga_id=mid, number=number, title=request.form.get("title",""),
                               pages_json=json.dumps(pages, ensure_ascii=False)))
        m.updated_at = now()
        db.session.commit()
        flash("Đã thêm chương.","success")
        return redirect(url_for("admin"))
    return render_template("admin_chapter_form.html", m=m)

@app.post("/admin/comment/<int:cid>/delete")
@admin_required
def admin_comment_delete(cid):
    c = db.session.get(Comment, cid)
    if c: db.session.delete(c); db.session.commit()
    return redirect(url_for("admin"))

@app.post("/admin/user/<int:uid>/role")
@admin_required
def admin_user_role(uid):
    if uid == current_user().id:
        flash("Không thể tự hạ quyền tài khoản đang đăng nhập.","warning")
        return redirect(url_for("admin"))
    u = db.session.get(User, uid)
    if u:
        u.role = "admin" if request.form.get("role") == "admin" else "user"
        db.session.commit()
    return redirect(url_for("admin"))

@app.get("/health")
def health():
    return {"status":"ok","app":"Bmanga"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_ENV")!="production")
