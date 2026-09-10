import os, json, uuid, re
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
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
db_url = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "bmanga.db"))
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-this"),
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=200 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production",
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

def utcnow():
    return datetime.utcnow()

# ---------- MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), default="")
    role = db.Column(db.String(20), default="user", nullable=False)  # user/editor/admin
    points = db.Column(db.Integer, default=0)
    vip = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow)

class TeamMember(db.Model):
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    role = db.Column(db.String(40), default="member")
    user = db.relationship("User")
    team = db.relationship("Team", backref="memberships")

class Manga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    alt_title = db.Column(db.String(255), default="")
    author = db.Column(db.String(255), default="")
    artist = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    genres = db.Column(db.String(700), default="")
    type = db.Column(db.String(30), default="Manga") # Manga/Manhwa/Manhua
    status = db.Column(db.String(50), default="Đang tiến hành")
    cover = db.Column(db.Text, default="")
    featured = db.Column(db.Boolean, default=False)
    mature = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    follows = db.Column(db.Integer, default=0)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    team = db.relationship("Team")

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id", ondelete="CASCADE"), nullable=False, index=True)
    number = db.Column(db.Float, nullable=False)
    title = db.Column(db.String(255), default="")
    pages_json = db.Column(db.Text, default="[]")
    views = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    published_at = db.Column(db.DateTime, default=utcnow)
    created_at = db.Column(db.DateTime, default=utcnow)
    manga = db.relationship("Manga", backref=db.backref("chapters", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("manga_id","number"),)

class Follow(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow)

class History(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    page_index = db.Column(db.Integer, default=0)
    read_at = db.Column(db.DateTime, default=utcnow)

class Rating(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), primary_key=True)
    score = db.Column(db.Integer, nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("comment.id"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    hidden = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship("User")
    manga = db.relationship("Manga")
    chapter = db.relationship("Chapter")
    parent = db.relationship("Comment", remote_side=[id])

class CommentLike(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comment.id"), primary_key=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    url = db.Column(db.Text, default="")
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), nullable=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=True)
    reason = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="open")
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship("User")
    manga = db.relationship("Manga")
    chapter = db.relationship("Chapter")

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.String(500), default="")
    image = db.Column(db.Text, default="")
    link = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

class SiteSetting(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default="")

# ---------- HELPERS ----------
def setting(key, default=""):
    x = db.session.get(SiteSetting, key)
    return x.value if x else default

def set_setting(key, value):
    x = db.session.get(SiteSetting, key)
    if x: x.value = value
    else: db.session.add(SiteSetting(key=key, value=value))

def current_user():
    return db.session.get(User, session.get("uid")) if session.get("uid") else None

def is_staff(u=None):
    u = u or current_user()
    return bool(u and u.role in ("editor","admin"))

def admin_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        u=current_user()
        if not u or u.role!="admin": abort(403)
        return fn(*a,**kw)
    return w

def staff_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not is_staff(): abort(403)
        return fn(*a,**kw)
    return w

def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not current_user():
            flash("Bạn cần đăng nhập.","warning")
            return redirect(url_for("login",next=request.path))
        return fn(*a,**kw)
    return w

def latest_chapter(manga_id):
    return Chapter.query.filter_by(manga_id=manga_id,is_published=True).order_by(Chapter.number.desc()).first()

def safe_next(target):
    if not target: return None
    p=urlparse(target)
    return target if not p.netloc and target.startswith("/") else None

def upload_image(file, folder):
    if not file or not getattr(file,"filename",""): return ""
    ext=os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in [".jpg",".jpeg",".png",".webp",".gif"]: return ""
    if cloudinary and os.getenv("CLOUDINARY_URL"):
        result=cloudinary.uploader.upload(file,folder=f"bmanga/{folder}",resource_type="image")
        return result["secure_url"]
    target=os.path.join(BASE_DIR,"static","uploads",folder)
    os.makedirs(target,exist_ok=True)
    name=f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(target,name))
    return f"/static/uploads/{folder}/{name}"

def notify_followers(manga, chapter):
    follows=Follow.query.filter_by(manga_id=manga.id).all()
    for f in follows:
        db.session.add(Notification(
            user_id=f.user_id,
            message=f"{manga.title} vừa có Chương {chapter.number:g}",
            url=url_for("read_chapter",chapter_id=chapter.id)
        ))

def seed():
    db.create_all()
    defaults={
        "site_name":"Bmanga",
        "site_description":"Đọc manga, manhwa, manhua online",
        "allow_register":"1",
        "announcement":"",
    }
    for k,v in defaults.items():
        if not db.session.get(SiteSetting,k): db.session.add(SiteSetting(key=k,value=v))
    au=os.getenv("ADMIN_USERNAME")
    ap=os.getenv("ADMIN_PASSWORD")
    if au and ap:
        u=User.query.filter_by(username=au).first()
        if not u:
            db.session.add(User(username=au,password_hash=generate_password_hash(ap),role="admin",display_name="Administrator"))
        elif u.role!="admin":
            u.role="admin"
    if Manga.query.count()==0:
        m=Manga(title="Kiếm Sĩ Bóng Đêm",slug="kiem-si-bong-dem",author="Bmanga Studio",
                artist="Bmanga Studio",description="Truyện mẫu để kiểm tra hệ thống Bmanga.",
                genres="Hành động,Phiêu lưu",type="Manga",featured=True)
        db.session.add(m); db.session.flush()
        for n in range(1,4):
            db.session.add(Chapter(manga_id=m.id,number=n,title=f"Chương {n}",
                pages_json=json.dumps([f"/static/demo/page-{i}.svg" for i in (1,2,3)])))
    db.session.commit()

with app.app_context():
    seed()

@app.context_processor
def ctx():
    u=current_user()
    unread=Notification.query.filter_by(user_id=u.id,read=False).count() if u else 0
    return dict(me=u, unread_notifications=unread, site_name=setting("site_name","Bmanga"),
                announcement=setting("announcement",""), is_staff=is_staff)

# ---------- PUBLIC ----------
@app.route("/")
def home():
    featured=Manga.query.filter_by(featured=True).order_by(Manga.updated_at.desc()).limit(12).all()
    latest=Manga.query.order_by(Manga.updated_at.desc()).limit(24).all()
    popular=Manga.query.order_by(Manga.views.desc()).limit(12).all()
    banners=Banner.query.filter_by(active=True).order_by(Banner.sort_order.asc()).all()
    for g in (featured,latest,popular):
        for m in g: m.latest=latest_chapter(m.id)
    return render_template("home.html",featured=featured,latest=latest,popular=popular,banners=banners)

@app.route("/search")
def search():
    q=request.args.get("q","").strip()
    genre=request.args.get("genre","").strip()
    status=request.args.get("status","").strip()
    mtype=request.args.get("type","").strip()
    sort=request.args.get("sort","updated")
    page=max(1,request.args.get("page",1,type=int))
    qry=Manga.query
    if q:
        x=f"%{q}%"; qry=qry.filter(db.or_(Manga.title.ilike(x),Manga.alt_title.ilike(x),Manga.author.ilike(x),Manga.artist.ilike(x)))
    if genre: qry=qry.filter(Manga.genres.ilike(f"%{genre}%"))
    if status: qry=qry.filter(Manga.status==status)
    if mtype: qry=qry.filter(Manga.type==mtype)
    order={"views":Manga.views.desc(),"title":Manga.title.asc(),"new":Manga.created_at.desc()}.get(sort,Manga.updated_at.desc())
    pagination=qry.order_by(order).paginate(page=page,per_page=24,error_out=False)
    for m in pagination.items: m.latest=latest_chapter(m.id)
    all_genres=sorted({g.strip() for m in Manga.query.all() for g in (m.genres or "").split(",") if g.strip()})
    return render_template("search.html",pagination=pagination,q=q,genre=genre,status=status,mtype=mtype,sort=sort,all_genres=all_genres)

@app.route("/manga/<slug>")
def manga_detail(slug):
    m=Manga.query.filter_by(slug=slug).first_or_404()
    m.views+=1; db.session.commit()
    chapters=Chapter.query.filter_by(manga_id=m.id,is_published=True).order_by(Chapter.number.desc()).all()
    rs=Rating.query.filter_by(manga_id=m.id).all()
    avg=round(sum(x.score for x in rs)/len(rs),1) if rs else None
    comments=Comment.query.filter_by(manga_id=m.id,hidden=False,parent_id=None).order_by(Comment.id.desc()).limit(100).all()
    u=current_user()
    followed=bool(u and Follow.query.filter_by(user_id=u.id,manga_id=m.id).first())
    my_rating=Rating.query.filter_by(user_id=u.id,manga_id=m.id).first().score if u and Rating.query.filter_by(user_id=u.id,manga_id=m.id).first() else 0
    return render_template("manga.html",m=m,chapters=chapters,comments=comments,rating_avg=avg,rating_count=len(rs),followed=followed,my_rating=my_rating)

@app.route("/read/<int:chapter_id>")
def read_chapter(chapter_id):
    c=db.session.get(Chapter,chapter_id)
    if not c or not c.is_published: abort(404)
    c.views+=1
    prevc=Chapter.query.filter(Chapter.manga_id==c.manga_id,Chapter.is_published==True,Chapter.number<c.number).order_by(Chapter.number.desc()).first()
    nextc=Chapter.query.filter(Chapter.manga_id==c.manga_id,Chapter.is_published==True,Chapter.number>c.number).order_by(Chapter.number.asc()).first()
    all_chapters=Chapter.query.filter_by(manga_id=c.manga_id,is_published=True).order_by(Chapter.number.asc()).all()
    u=current_user()
    if u:
        h=History.query.filter_by(user_id=u.id,manga_id=c.manga_id).first()
        if h: h.chapter_id=c.id; h.read_at=utcnow()
        else: db.session.add(History(user_id=u.id,manga_id=c.manga_id,chapter_id=c.id))
    db.session.commit()
    return render_template("reader.html",c=c,pages=json.loads(c.pages_json or "[]"),prevc=prevc,nextc=nextc,all_chapters=all_chapters)

# ---------- AUTH / USER ----------
@app.route("/register",methods=["GET","POST"])
def register():
    if setting("allow_register","1")!="1": abort(403)
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,30}",username):
            flash("Username chỉ gồm chữ, số, _ và dài 3-30 ký tự.","danger"); return redirect(request.url)
        if len(password)<6:
            flash("Mật khẩu cần ít nhất 6 ký tự.","danger"); return redirect(request.url)
        if User.query.filter_by(username=username).first():
            flash("Username đã tồn tại.","danger"); return redirect(request.url)
        db.session.add(User(username=username,password_hash=generate_password_hash(password),display_name=username))
        db.session.commit()
        flash("Đăng ký thành công.","success"); return redirect(url_for("login"))
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form.get("username","").strip()).first()
        if u and u.is_active and check_password_hash(u.password_hash,request.form.get("password","")):
            session.clear(); session["uid"]=u.id
            return redirect(safe_next(request.args.get("next")) or url_for("home"))
        flash("Sai tài khoản/mật khẩu hoặc tài khoản bị khóa.","danger")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/me")
@login_required
def profile():
    u=current_user()
    follows=Follow.query.filter_by(user_id=u.id).order_by(Follow.created_at.desc()).all()
    mangas=[db.session.get(Manga,x.manga_id) for x in follows]
    hist=History.query.filter_by(user_id=u.id).order_by(History.read_at.desc()).all()
    history=[]
    for h in hist:
        m=db.session.get(Manga,h.manga_id); c=db.session.get(Chapter,h.chapter_id)
        if m and c: history.append({"m":m,"c":c,"read_at":h.read_at})
    return render_template("profile.html",mangas=mangas,history=history)

@app.post("/follow/<int:manga_id>")
@login_required
def follow(manga_id):
    u=current_user(); m=db.session.get(Manga,manga_id) or abort(404)
    x=Follow.query.filter_by(user_id=u.id,manga_id=manga_id).first()
    if x: db.session.delete(x); m.follows=max(0,m.follows-1)
    else: db.session.add(Follow(user_id=u.id,manga_id=manga_id)); m.follows+=1
    db.session.commit()
    return redirect(request.referrer or url_for("manga_detail",slug=m.slug))

@app.post("/rate/<int:manga_id>")
@login_required
def rate(manga_id):
    score=max(1,min(5,int(request.form.get("score",5))))
    u=current_user()
    r=Rating.query.filter_by(user_id=u.id,manga_id=manga_id).first()
    if r: r.score=score
    else: db.session.add(Rating(user_id=u.id,manga_id=manga_id,score=score))
    db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.post("/comment/<int:manga_id>")
@login_required
def comment(manga_id):
    body=request.form.get("body","").strip()
    chapter_id=request.form.get("chapter_id",type=int)
    parent_id=request.form.get("parent_id",type=int)
    if body:
        db.session.add(Comment(user_id=current_user().id,manga_id=manga_id,chapter_id=chapter_id,parent_id=parent_id,body=body[:2000]))
        current_user().points += 1
        db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.post("/comment/<int:cid>/like")
@login_required
def comment_like(cid):
    c=db.session.get(Comment,cid) or abort(404)
    u=current_user()
    x=CommentLike.query.filter_by(user_id=u.id,comment_id=cid).first()
    if x: db.session.delete(x); c.likes=max(0,c.likes-1)
    else: db.session.add(CommentLike(user_id=u.id,comment_id=cid)); c.likes+=1
    db.session.commit()
    return redirect(request.referrer or url_for("home"))

@app.route("/notifications")
@login_required
def notifications():
    u=current_user()
    rows=Notification.query.filter_by(user_id=u.id).order_by(Notification.id.desc()).limit(100).all()
    Notification.query.filter_by(user_id=u.id,read=False).update({"read":True})
    db.session.commit()
    return render_template("notifications.html",rows=rows)

@app.post("/report")
def report():
    reason=request.form.get("reason","").strip()
    if reason:
        db.session.add(Report(user_id=current_user().id if current_user() else None,
                              manga_id=request.form.get("manga_id",type=int),
                              chapter_id=request.form.get("chapter_id",type=int),
                              reason=reason[:255],details=request.form.get("details","")[:2000]))
        db.session.commit()
        flash("Đã gửi báo lỗi. Cảm ơn bạn.","success")
    return redirect(request.referrer or url_for("home"))

@app.post("/api/progress/<int:chapter_id>")
@login_required
def save_progress(chapter_id):
    h=History.query.filter_by(user_id=current_user().id,chapter_id=chapter_id).first()
    if not h:
        c=db.session.get(Chapter,chapter_id) or abort(404)
        h=History.query.filter_by(user_id=current_user().id,manga_id=c.manga_id).first()
    if h:
        h.page_index=max(0,request.json.get("page_index",0) if request.is_json else 0)
        h.read_at=utcnow(); db.session.commit()
    return jsonify(ok=True)

# ---------- ADMIN ----------
@app.route("/admin")
@staff_required
def admin():
    stats={"manga":Manga.query.count(),"chapters":Chapter.query.count(),"users":User.query.count(),
           "comments":Comment.query.count(),"reports":Report.query.filter_by(status="open").count()}
    recent=Manga.query.order_by(Manga.updated_at.desc()).limit(20).all()
    return render_template("admin/dashboard.html",stats=stats,recent=recent)

@app.route("/admin/manga")
@staff_required
def admin_manga():
    rows=Manga.query.order_by(Manga.updated_at.desc()).all()
    return render_template("admin/manga_list.html",rows=rows)

@app.route("/admin/manga/new",methods=["GET","POST"])
@staff_required
def admin_manga_new():
    if request.method=="POST":
        slug=request.form["slug"].strip()
        if Manga.query.filter_by(slug=slug).first():
            flash("Slug đã tồn tại.","danger"); return redirect(request.url)
        m=Manga(title=request.form["title"].strip(),slug=slug,alt_title=request.form.get("alt_title",""),
                author=request.form.get("author",""),artist=request.form.get("artist",""),description=request.form.get("description",""),
                genres=request.form.get("genres",""),type=request.form.get("type","Manga"),status=request.form.get("status","Đang tiến hành"),
                featured=bool(request.form.get("featured")),mature=bool(request.form.get("mature")),
                cover=upload_image(request.files.get("cover"),"covers"))
        db.session.add(m); db.session.commit()
        flash("Đã thêm truyện.","success"); return redirect(url_for("admin_manga"))
    return render_template("admin/manga_form.html",m=None)

@app.route("/admin/manga/<int:mid>/edit",methods=["GET","POST"])
@staff_required
def admin_manga_edit(mid):
    m=db.session.get(Manga,mid) or abort(404)
    if request.method=="POST":
        for attr in ["title","slug","alt_title","author","artist","description","genres","type","status"]:
            setattr(m,attr,request.form.get(attr,getattr(m,attr)))
        m.featured=bool(request.form.get("featured")); m.mature=bool(request.form.get("mature"))
        cover=upload_image(request.files.get("cover"),"covers")
        if cover: m.cover=cover
        m.updated_at=utcnow(); db.session.commit()
        flash("Đã cập nhật.","success"); return redirect(url_for("admin_manga"))
    return render_template("admin/manga_form.html",m=m)

@app.post("/admin/manga/<int:mid>/delete")
@admin_required
def admin_manga_delete(mid):
    m=db.session.get(Manga,mid) or abort(404)
    db.session.delete(m); db.session.commit(); flash("Đã xóa truyện.","success")
    return redirect(url_for("admin_manga"))

@app.route("/admin/manga/<int:mid>/chapters")
@staff_required
def admin_chapters(mid):
    m=db.session.get(Manga,mid) or abort(404)
    rows=Chapter.query.filter_by(manga_id=mid).order_by(Chapter.number.desc()).all()
    return render_template("admin/chapter_list.html",m=m,rows=rows)

@app.route("/admin/manga/<int:mid>/chapter/new",methods=["GET","POST"])
@staff_required
def admin_chapter_new(mid):
    m=db.session.get(Manga,mid) or abort(404)
    if request.method=="POST":
        try: number=float(request.form["number"])
        except: flash("Số chương không hợp lệ.","danger"); return redirect(request.url)
        if Chapter.query.filter_by(manga_id=mid,number=number).first():
            flash("Chương này đã tồn tại.","danger"); return redirect(request.url)
        pages=[x.strip() for x in request.form.get("page_urls","").splitlines() if x.strip()]
        for f in request.files.getlist("pages"):
            u=upload_image(f,f"chapters/{mid}/{str(number).replace('.','_')}")
            if u: pages.append(u)
        c=Chapter(manga_id=mid,number=number,title=request.form.get("title",""),pages_json=json.dumps(pages,ensure_ascii=False),
                  is_published=bool(request.form.get("is_published","1")))
        db.session.add(c); db.session.flush()
        m.updated_at=utcnow()
        if c.is_published: notify_followers(m,c)
        db.session.commit(); flash("Đã đăng chương.","success")
        return redirect(url_for("admin_chapters",mid=mid))
    return render_template("admin/chapter_form.html",m=m,c=None)

@app.route("/admin/chapter/<int:cid>/edit",methods=["GET","POST"])
@staff_required
def admin_chapter_edit(cid):
    c=db.session.get(Chapter,cid) or abort(404); m=c.manga
    if request.method=="POST":
        c.number=float(request.form["number"]); c.title=request.form.get("title","")
        urls=[x.strip() for x in request.form.get("page_urls","").splitlines() if x.strip()]
        if urls: c.pages_json=json.dumps(urls,ensure_ascii=False)
        for f in request.files.getlist("pages"):
            u=upload_image(f,f"chapters/{m.id}/{str(c.number).replace('.','_')}")
            if u:
                cur=json.loads(c.pages_json or "[]"); cur.append(u); c.pages_json=json.dumps(cur,ensure_ascii=False)
        c.is_published=bool(request.form.get("is_published"))
        m.updated_at=utcnow(); db.session.commit(); flash("Đã cập nhật chương.","success")
        return redirect(url_for("admin_chapters",mid=m.id))
    return render_template("admin/chapter_form.html",m=m,c=c)

@app.post("/admin/chapter/<int:cid>/delete")
@staff_required
def admin_chapter_delete(cid):
    c=db.session.get(Chapter,cid) or abort(404); mid=c.manga_id
    db.session.delete(c); db.session.commit(); flash("Đã xóa chương.","success")
    return redirect(url_for("admin_chapters",mid=mid))

@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin/users.html",rows=User.query.order_by(User.id.desc()).all())

@app.post("/admin/user/<int:uid>/update")
@admin_required
def admin_user_update(uid):
    u=db.session.get(User,uid) or abort(404)
    if u.id==current_user().id and request.form.get("role")!="admin":
        flash("Không thể tự hạ quyền admin đang đăng nhập.","warning"); return redirect(url_for("admin_users"))
    u.role=request.form.get("role","user")
    u.vip=bool(request.form.get("vip"))
    u.is_active=bool(request.form.get("is_active"))
    u.points=request.form.get("points",u.points,type=int)
    db.session.commit()
    return redirect(url_for("admin_users"))

@app.route("/admin/comments")
@staff_required
def admin_comments():
    return render_template("admin/comments.html",rows=Comment.query.order_by(Comment.id.desc()).limit(300).all())

@app.post("/admin/comment/<int:cid>/toggle")
@staff_required
def admin_comment_toggle(cid):
    c=db.session.get(Comment,cid) or abort(404); c.hidden=not c.hidden; db.session.commit()
    return redirect(url_for("admin_comments"))

@app.post("/admin/comment/<int:cid>/delete")
@admin_required
def admin_comment_delete(cid):
    c=db.session.get(Comment,cid) or abort(404); db.session.delete(c); db.session.commit()
    return redirect(url_for("admin_comments"))

@app.route("/admin/reports")
@staff_required
def admin_reports():
    return render_template("admin/reports.html",rows=Report.query.order_by(Report.id.desc()).all())

@app.post("/admin/report/<int:rid>/status")
@staff_required
def admin_report_status(rid):
    r=db.session.get(Report,rid) or abort(404); r.status=request.form.get("status","open"); db.session.commit()
    return redirect(url_for("admin_reports"))

@app.route("/admin/banners",methods=["GET","POST"])
@admin_required
def admin_banners():
    if request.method=="POST":
        db.session.add(Banner(title=request.form["title"],subtitle=request.form.get("subtitle",""),
                              image=request.form.get("image",""),link=request.form.get("link",""),
                              active=bool(request.form.get("active")),sort_order=request.form.get("sort_order",0,type=int)))
        db.session.commit()
    return render_template("admin/banners.html",rows=Banner.query.order_by(Banner.sort_order).all())

@app.post("/admin/banner/<int:bid>/delete")
@admin_required
def admin_banner_delete(bid):
    b=db.session.get(Banner,bid) or abort(404); db.session.delete(b); db.session.commit()
    return redirect(url_for("admin_banners"))

@app.route("/admin/settings",methods=["GET","POST"])
@admin_required
def admin_settings():
    if request.method=="POST":
        for k in ["site_name","site_description","announcement","allow_register"]:
            set_setting(k,request.form.get(k,""))
        db.session.commit(); flash("Đã lưu cài đặt.","success")
    return render_template("admin/settings.html",settings={k:setting(k,"") for k in ["site_name","site_description","announcement","allow_register"]})

@app.get("/health")
def health():
    return jsonify(status="ok",app="Bmanga")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")),debug=os.getenv("FLASK_ENV")!="production")
