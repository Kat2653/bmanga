import os, json, uuid, re, zipfile, tempfile, shutil, io, unicodedata
from pathlib import Path
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, send_file, Response
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
ALLOWED_IMAGES = {'.jpg','.jpeg','.png','.webp','.gif'}

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
db_url = os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'bmanga.db'))
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://','postgresql://',1)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY','dev-change-this'),
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=512*1024*1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('FLASK_ENV')=='production',
)
db=SQLAlchemy(app)
csrf=CSRFProtect(app)

def utcnow(): return datetime.utcnow()

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False,index=True)
    password_hash=db.Column(db.String(255),nullable=False)
    display_name=db.Column(db.String(120),default='')
    role=db.Column(db.String(20),default='user',nullable=False)
    points=db.Column(db.Integer,default=0)
    vip=db.Column(db.Boolean,default=False)
    is_active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=utcnow,nullable=False)

class Team(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),unique=True,nullable=False)
    slug=db.Column(db.String(180),unique=True,nullable=False,index=True)
    description=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=utcnow)

class TeamMember(db.Model):
    team_id=db.Column(db.Integer,db.ForeignKey('team.id'),primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),primary_key=True)
    role=db.Column(db.String(40),default='member')
    user=db.relationship('User')
    team=db.relationship('Team',backref='memberships')

class Manga(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    title=db.Column(db.String(255),nullable=False)
    slug=db.Column(db.String(255),unique=True,nullable=False,index=True)
    alt_title=db.Column(db.String(255),default='')
    author=db.Column(db.String(255),default='')
    artist=db.Column(db.String(255),default='')
    description=db.Column(db.Text,default='')
    genres=db.Column(db.String(700),default='')
    type=db.Column(db.String(30),default='Manga')
    status=db.Column(db.String(50),default='Đang tiến hành')
    cover=db.Column(db.Text,default='')
    featured=db.Column(db.Boolean,default=False)
    mature=db.Column(db.Boolean,default=False)
    views=db.Column(db.Integer,default=0)
    follows=db.Column(db.Integer,default=0)
    team_id=db.Column(db.Integer,db.ForeignKey('team.id'),nullable=True)
    created_at=db.Column(db.DateTime,default=utcnow,nullable=False)
    updated_at=db.Column(db.DateTime,default=utcnow,nullable=False)
    team=db.relationship('Team')

class Chapter(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id',ondelete='CASCADE'),nullable=False,index=True)
    number=db.Column(db.Float,nullable=False)
    title=db.Column(db.String(255),default='')
    pages_json=db.Column(db.Text,default='[]')
    views=db.Column(db.Integer,default=0)
    is_published=db.Column(db.Boolean,default=True)
    published_at=db.Column(db.DateTime,default=utcnow)
    created_at=db.Column(db.DateTime,default=utcnow)
    manga=db.relationship('Manga',backref=db.backref('chapters',cascade='all, delete-orphan'))
    __table_args__=(db.UniqueConstraint('manga_id','number'),)

class Follow(db.Model):
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),primary_key=True)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id'),primary_key=True)
    created_at=db.Column(db.DateTime,default=utcnow)

class History(db.Model):
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),primary_key=True)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id'),primary_key=True)
    chapter_id=db.Column(db.Integer,db.ForeignKey('chapter.id'),nullable=False)
    page_index=db.Column(db.Integer,default=0)
    read_at=db.Column(db.DateTime,default=utcnow)

class Rating(db.Model):
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),primary_key=True)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id'),primary_key=True)
    score=db.Column(db.Integer,nullable=False)

class Comment(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id'),nullable=False)
    chapter_id=db.Column(db.Integer,db.ForeignKey('chapter.id'),nullable=True)
    parent_id=db.Column(db.Integer,db.ForeignKey('comment.id'),nullable=True)
    body=db.Column(db.Text,nullable=False)
    likes=db.Column(db.Integer,default=0)
    hidden=db.Column(db.Boolean,default=False)
    created_at=db.Column(db.DateTime,default=utcnow)
    user=db.relationship('User')
    manga=db.relationship('Manga')
    chapter=db.relationship('Chapter')
    parent=db.relationship('Comment',remote_side=[id])

class CommentLike(db.Model):
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),primary_key=True)
    comment_id=db.Column(db.Integer,db.ForeignKey('comment.id'),primary_key=True)

class Notification(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    message=db.Column(db.String(500),nullable=False)
    url=db.Column(db.Text,default='')
    read=db.Column(db.Boolean,default=False)
    created_at=db.Column(db.DateTime,default=utcnow)

class Report(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=True)
    manga_id=db.Column(db.Integer,db.ForeignKey('manga.id'),nullable=True)
    chapter_id=db.Column(db.Integer,db.ForeignKey('chapter.id'),nullable=True)
    reason=db.Column(db.String(255),nullable=False)
    details=db.Column(db.Text,default='')
    status=db.Column(db.String(30),default='open')
    created_at=db.Column(db.DateTime,default=utcnow)
    user=db.relationship('User')
    manga=db.relationship('Manga')
    chapter=db.relationship('Chapter')

class Banner(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    title=db.Column(db.String(255),nullable=False)
    subtitle=db.Column(db.String(500),default='')
    image=db.Column(db.Text,default='')
    link=db.Column(db.Text,default='')
    active=db.Column(db.Boolean,default=True)
    sort_order=db.Column(db.Integer,default=0)

class SiteSetting(db.Model):
    key=db.Column(db.String(100),primary_key=True)
    value=db.Column(db.Text,default='')

def setting(key,default=''):
    x=db.session.get(SiteSetting,key); return x.value if x else default

def set_setting(key,value):
    x=db.session.get(SiteSetting,key)
    if x: x.value=value
    else: db.session.add(SiteSetting(key=key,value=value))

def current_user():
    return db.session.get(User,session.get('uid')) if session.get('uid') else None

def is_staff(u=None):
    u=u or current_user(); return bool(u and u.role in ('editor','admin'))

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not current_user():
            flash('Bạn cần đăng nhập.','warning'); return redirect(url_for('login',next=request.path))
        return fn(*a,**kw)
    return w

def staff_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not is_staff(): abort(403)
        return fn(*a,**kw)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        u=current_user()
        if not u or u.role!='admin': abort(403)
        return fn(*a,**kw)
    return w

def slugify(text):
    text=(text or '').strip().lower().replace('đ','d')
    text=unicodedata.normalize('NFD',text)
    text=''.join(c for c in text if unicodedata.category(c)!='Mn')
    text=re.sub(r'[^a-z0-9]+','-',text).strip('-')
    return text or uuid.uuid4().hex[:10]

def unique_slug(base,ignore_id=None):
    base=slugify(base); candidate=base; n=2
    while True:
        q=Manga.query.filter_by(slug=candidate)
        if ignore_id: q=q.filter(Manga.id!=ignore_id)
        if not q.first(): return candidate
        candidate=f'{base}-{n}'; n+=1

def safe_next(target):
    if not target: return None
    p=urlparse(target)
    return target if not p.netloc and target.startswith('/') else None

def latest_chapter(manga_id):
    return Chapter.query.filter_by(manga_id=manga_id,is_published=True).order_by(Chapter.number.desc()).first()

def chapter_count(manga_id):
    return Chapter.query.filter_by(manga_id=manga_id,is_published=True).count()

def upload_image(file_or_path,folder):
    if not file_or_path: return ''
    if isinstance(file_or_path,(str,Path)):
        filename=str(file_or_path)
        ext=Path(filename).suffix.lower()
    else:
        filename=getattr(file_or_path,'filename','')
        ext=Path(secure_filename(filename)).suffix.lower()
    if ext not in ALLOWED_IMAGES: return ''
    if cloudinary and os.getenv('CLOUDINARY_URL'):
        result=cloudinary.uploader.upload(file_or_path,folder=f'bmanga/{folder}',resource_type='image')
        return result['secure_url']
    target=Path(BASE_DIR)/'static'/'uploads'/folder
    target.mkdir(parents=True,exist_ok=True)
    name=f'{uuid.uuid4().hex}{ext}'
    out=target/name
    if isinstance(file_or_path,(str,Path)): shutil.copyfile(file_or_path,out)
    else: file_or_path.save(out)
    return f'/static/uploads/{folder}/{name}'

def notify_followers(manga,chapter):
    for f in Follow.query.filter_by(manga_id=manga.id).all():
        db.session.add(Notification(user_id=f.user_id,message=f'{manga.title} vừa có Chương {chapter.number:g}',url=url_for('read_chapter',chapter_id=chapter.id)))

def _natural_key(name):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',name)]

def _chapter_number_from_path(path):
    parts=path.replace('\\','/').split('/')
    for part in reversed(parts[:-1]):
        m=re.search(r'(?:chap(?:ter)?|chương|chuong|ch)?[\s._-]*(\d+(?:\.\d+)?)',part,re.I)
        if m: return float(m.group(1))
    return None

def _zip_infos(z):
    infos=[i for i in z.infolist() if not i.is_dir()]
    if len(infos)>10000: raise ValueError('ZIP có quá nhiều file.')
    if any(i.file_size>30*1024*1024 for i in infos): raise ValueError('Có ảnh lớn hơn 30MB.')
    if sum(i.file_size for i in infos)>500*1024*1024: raise ValueError('Tổng dung lượng giải nén vượt 500MB.')
    return infos

def _safe_member(name):
    p=Path(name)
    return not p.is_absolute() and '..' not in p.parts and not name.startswith('__MACOSX/')

def _import_chapter_groups(z,infos,manga,td,publish=True):
    groups={}
    for info in infos:
        if not _safe_member(info.filename): continue
        if Path(info.filename).suffix.lower() not in ALLOWED_IMAGES: continue
        if Path(info.filename).name.lower().startswith('cover.'): continue
        num=_chapter_number_from_path(info.filename)
        if num is not None: groups.setdefault(num,[]).append(info)
    created=0; skipped=[]
    for num in sorted(groups):
        if Chapter.query.filter_by(manga_id=manga.id,number=num).first():
            skipped.append(f'{num:g}'); continue
        pages=[]
        for idx,info in enumerate(sorted(groups[num],key=lambda x:_natural_key(x.filename))):
            ext=Path(info.filename).suffix.lower()
            tmp=Path(td)/f'{manga.id}_{num}_{idx}{ext}'
            with z.open(info) as src, open(tmp,'wb') as out: shutil.copyfileobj(src,out)
            url=upload_image(tmp,f'chapters/{manga.id}/{str(num).replace(".","_")}')
            if url: pages.append(url)
        if pages:
            c=Chapter(manga_id=manga.id,number=num,title='',pages_json=json.dumps(pages,ensure_ascii=False),is_published=publish)
            db.session.add(c); db.session.flush()
            if publish: notify_followers(manga,c)
            created+=1
    manga.updated_at=utcnow()
    return created,skipped

def init_db():
    db.create_all()
    defaults={'site_name':'Bmanga','site_description':'Đọc manga, manhwa, manhua online','allow_register':'1','announcement':'','footer_text':'Bmanga','facebook_url':'','discord_url':'','telegram_url':''}
    for k,v in defaults.items():
        if not db.session.get(SiteSetting,k): db.session.add(SiteSetting(key=k,value=v))
    au=os.getenv('ADMIN_USERNAME'); ap=os.getenv('ADMIN_PASSWORD')
    if au and ap:
        u=User.query.filter_by(username=au).first()
        if not u:
            db.session.add(User(username=au,password_hash=generate_password_hash(ap),role='admin',display_name='Administrator'))
        else:
            u.role='admin'; u.is_active=True
            if os.getenv('RESET_ADMIN_PASSWORD')=='1': u.password_hash=generate_password_hash(ap)
    db.session.commit()

with app.app_context(): init_db()

@app.context_processor
def ctx():
    u=current_user(); unread=Notification.query.filter_by(user_id=u.id,read=False).count() if u else 0
    return dict(me=u,unread_notifications=unread,site_name=setting('site_name','Bmanga'),site_description=setting('site_description',''),announcement=setting('announcement',''),footer_text=setting('footer_text','Bmanga'),is_staff=is_staff)

@app.route('/')
def home():
    featured=Manga.query.filter_by(featured=True).order_by(Manga.updated_at.desc()).limit(14).all()
    latest=Manga.query.order_by(Manga.updated_at.desc()).limit(30).all()
    popular=Manga.query.order_by(Manga.views.desc()).limit(10).all()
    followed=Manga.query.order_by(Manga.follows.desc()).limit(10).all()
    banners=Banner.query.filter_by(active=True).order_by(Banner.sort_order.asc()).all()
    for group in (featured,latest,popular,followed):
        for m in group:
            m.latest=latest_chapter(m.id); m.chapter_count=chapter_count(m.id)
    return render_template('home.html',featured=featured,latest=latest,popular=popular,followed=followed,banners=banners)

@app.route('/search')
def search():
    q=request.args.get('q','').strip(); genre=request.args.get('genre','').strip(); status=request.args.get('status','').strip(); mtype=request.args.get('type','').strip(); sort=request.args.get('sort','updated'); page=max(1,request.args.get('page',1,type=int))
    qry=Manga.query
    if q:
        x=f'%{q}%'; qry=qry.filter(db.or_(Manga.title.ilike(x),Manga.alt_title.ilike(x),Manga.author.ilike(x),Manga.artist.ilike(x)))
    if genre: qry=qry.filter(Manga.genres.ilike(f'%{genre}%'))
    if status: qry=qry.filter(Manga.status==status)
    if mtype: qry=qry.filter(Manga.type==mtype)
    orders={'views':Manga.views.desc(),'follows':Manga.follows.desc(),'title':Manga.title.asc(),'new':Manga.created_at.desc(),'updated':Manga.updated_at.desc()}
    pagination=qry.order_by(orders.get(sort,Manga.updated_at.desc())).paginate(page=page,per_page=24,error_out=False)
    for m in pagination.items: m.latest=latest_chapter(m.id)
    genres=sorted({g.strip() for m in Manga.query.all() for g in (m.genres or '').split(',') if g.strip()})
    return render_template('search.html',pagination=pagination,q=q,genre=genre,status=status,mtype=mtype,sort=sort,all_genres=genres)

@app.route('/rankings')
def rankings():
    by=request.args.get('by','views')
    order=Manga.follows.desc() if by=='follows' else Manga.updated_at.desc() if by=='updated' else Manga.views.desc()
    rows=Manga.query.order_by(order).limit(100).all()
    for m in rows: m.latest=latest_chapter(m.id)
    return render_template('rankings.html',rows=rows,by=by)

@app.route('/manga/<slug>')
def manga_detail(slug):
    m=Manga.query.filter_by(slug=slug).first_or_404(); m.views+=1; db.session.commit()
    chapters=Chapter.query.filter_by(manga_id=m.id,is_published=True).order_by(Chapter.number.desc()).all()
    ratings=Rating.query.filter_by(manga_id=m.id).all(); avg=round(sum(x.score for x in ratings)/len(ratings),1) if ratings else None
    comments=Comment.query.filter_by(manga_id=m.id,hidden=False,parent_id=None).order_by(Comment.id.desc()).limit(100).all()
    replies={c.id:Comment.query.filter_by(parent_id=c.id,hidden=False).order_by(Comment.id.asc()).all() for c in comments}
    u=current_user(); followed=bool(u and Follow.query.filter_by(user_id=u.id,manga_id=m.id).first())
    mine=Rating.query.filter_by(user_id=u.id,manga_id=m.id).first() if u else None
    return render_template('manga.html',m=m,chapters=chapters,comments=comments,replies=replies,rating_avg=avg,rating_count=len(ratings),followed=followed,my_rating=mine.score if mine else 0)

@app.route('/read/<int:chapter_id>')
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
    try: pages=json.loads(c.pages_json or '[]')
    except Exception: pages=[]
    return render_template('reader.html',c=c,pages=pages,prevc=prevc,nextc=nextc,all_chapters=all_chapters)

@app.route('/team/<slug>')
def team_detail(slug):
    team=Team.query.filter_by(slug=slug).first_or_404(); rows=Manga.query.filter_by(team_id=team.id).order_by(Manga.updated_at.desc()).all()
    for m in rows: m.latest=latest_chapter(m.id)
    return render_template('team.html',team=team,rows=rows)

@app.route('/register',methods=['GET','POST'])
def register():
    if setting('allow_register','1')!='1': abort(403)
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password',''); confirm=request.form.get('confirm','')
        if not re.fullmatch(r'[A-Za-z0-9_]{3,30}',username): flash('Username chỉ gồm chữ, số, _ và dài 3-30 ký tự.','danger'); return redirect(request.url)
        if len(password)<6: flash('Mật khẩu cần ít nhất 6 ký tự.','danger'); return redirect(request.url)
        if password!=confirm: flash('Hai mật khẩu không khớp.','danger'); return redirect(request.url)
        if User.query.filter_by(username=username).first(): flash('Username đã tồn tại.','danger'); return redirect(request.url)
        db.session.add(User(username=username,password_hash=generate_password_hash(password),display_name=request.form.get('display_name','').strip() or username)); db.session.commit(); flash('Đăng ký thành công.','success'); return redirect(url_for('login'))
    return render_template('auth.html',mode='register')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip()).first()
        if u and u.is_active and check_password_hash(u.password_hash,request.form.get('password','')):
            session.clear(); session['uid']=u.id; return redirect(safe_next(request.args.get('next')) or url_for('home'))
        flash('Sai tài khoản/mật khẩu hoặc tài khoản bị khóa.','danger')
    return render_template('auth.html',mode='login')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/me')
@login_required
def profile():
    u=current_user(); fs=Follow.query.filter_by(user_id=u.id).order_by(Follow.created_at.desc()).all(); mangas=[db.session.get(Manga,x.manga_id) for x in fs]
    hist=History.query.filter_by(user_id=u.id).order_by(History.read_at.desc()).all(); history=[]
    for h in hist:
        m=db.session.get(Manga,h.manga_id); c=db.session.get(Chapter,h.chapter_id)
        if m and c: history.append({'m':m,'c':c,'read_at':h.read_at,'page_index':h.page_index})
    return render_template('profile.html',mangas=[m for m in mangas if m],history=history)

@app.post('/me/history/clear')
@login_required
def clear_history():
    History.query.filter_by(user_id=current_user().id).delete(); db.session.commit(); flash('Đã xóa lịch sử đọc.','success'); return redirect(url_for('profile'))

@app.route('/me/password',methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        u=current_user()
        if not check_password_hash(u.password_hash,request.form.get('old_password','')): flash('Mật khẩu hiện tại không đúng.','danger')
        elif len(request.form.get('new_password',''))<6: flash('Mật khẩu mới cần ít nhất 6 ký tự.','danger')
        elif request.form.get('new_password')!=request.form.get('confirm'): flash('Hai mật khẩu mới không khớp.','danger')
        else: u.password_hash=generate_password_hash(request.form['new_password']); db.session.commit(); flash('Đã đổi mật khẩu.','success'); return redirect(url_for('profile'))
    return render_template('change_password.html')

@app.post('/follow/<int:manga_id>')
@login_required
def follow(manga_id):
    u=current_user(); m=db.session.get(Manga,manga_id) or abort(404); x=Follow.query.filter_by(user_id=u.id,manga_id=manga_id).first()
    if x: db.session.delete(x); m.follows=max(0,m.follows-1)
    else: db.session.add(Follow(user_id=u.id,manga_id=manga_id)); m.follows+=1
    db.session.commit(); return redirect(request.referrer or url_for('manga_detail',slug=m.slug))

@app.post('/rate/<int:manga_id>')
@login_required
def rate(manga_id):
    try: score=max(1,min(5,int(request.form.get('score',5))))
    except Exception: score=5
    u=current_user(); r=Rating.query.filter_by(user_id=u.id,manga_id=manga_id).first()
    if r: r.score=score
    else: db.session.add(Rating(user_id=u.id,manga_id=manga_id,score=score))
    db.session.commit(); return redirect(request.referrer or url_for('home'))

@app.post('/comment/<int:manga_id>')
@login_required
def comment(manga_id):
    body=request.form.get('body','').strip(); chapter_id=request.form.get('chapter_id',type=int); parent_id=request.form.get('parent_id',type=int)
    if body:
        db.session.add(Comment(user_id=current_user().id,manga_id=manga_id,chapter_id=chapter_id,parent_id=parent_id,body=body[:2000])); current_user().points+=1; db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.post('/comment/<int:cid>/like')
@login_required
def comment_like(cid):
    c=db.session.get(Comment,cid) or abort(404); u=current_user(); x=CommentLike.query.filter_by(user_id=u.id,comment_id=cid).first()
    if x: db.session.delete(x); c.likes=max(0,c.likes-1)
    else: db.session.add(CommentLike(user_id=u.id,comment_id=cid)); c.likes+=1
    db.session.commit(); return redirect(request.referrer or url_for('home'))

@app.route('/notifications')
@login_required
def notifications():
    u=current_user(); rows=Notification.query.filter_by(user_id=u.id).order_by(Notification.id.desc()).limit(100).all(); Notification.query.filter_by(user_id=u.id,read=False).update({'read':True}); db.session.commit(); return render_template('notifications.html',rows=rows)

@app.post('/report')
def report():
    reason=request.form.get('reason','').strip()
    if reason:
        db.session.add(Report(user_id=current_user().id if current_user() else None,manga_id=request.form.get('manga_id',type=int),chapter_id=request.form.get('chapter_id',type=int),reason=reason[:255],details=request.form.get('details','')[:2000])); db.session.commit(); flash('Đã gửi báo lỗi.','success')
    return redirect(request.referrer or url_for('home'))

@app.post('/api/progress/<int:chapter_id>')
def save_progress(chapter_id):
    u=current_user()
    if not u: return jsonify(ok=False),401
    c=db.session.get(Chapter,chapter_id) or abort(404); h=History.query.filter_by(user_id=u.id,manga_id=c.manga_id).first()
    if not h: h=History(user_id=u.id,manga_id=c.manga_id,chapter_id=c.id); db.session.add(h)
    h.chapter_id=c.id; h.page_index=max(0,(request.get_json(silent=True) or {}).get('page_index',0)); h.read_at=utcnow(); db.session.commit(); return jsonify(ok=True)

@app.route('/admin')
@staff_required
def admin():
    stats={'manga':Manga.query.count(),'chapters':Chapter.query.count(),'users':User.query.count(),'comments':Comment.query.count(),'reports':Report.query.filter_by(status='open').count(),'views':sum(x.views for x in Manga.query.all())}
    recent=Manga.query.order_by(Manga.updated_at.desc()).limit(12).all(); return render_template('admin/dashboard.html',stats=stats,recent=recent)

@app.route('/admin/manga')
@staff_required
def admin_manga():
    q=request.args.get('q','').strip(); qry=Manga.query
    if q: qry=qry.filter(Manga.title.ilike(f'%{q}%'))
    return render_template('admin/manga_list.html',rows=qry.order_by(Manga.updated_at.desc()).all(),q=q)

@app.route('/admin/manga/new',methods=['GET','POST'])
@staff_required
def admin_manga_new():
    if request.method=='POST':
        title=request.form.get('title','').strip()
        if not title: flash('Tên truyện không được trống.','danger'); return redirect(request.url)
        slug=unique_slug(request.form.get('slug') or title)
        cover=upload_image(request.files.get('cover'),'covers') or request.form.get('cover_url','').strip()
        m=Manga(title=title,slug=slug,alt_title=request.form.get('alt_title',''),author=request.form.get('author',''),artist=request.form.get('artist',''),description=request.form.get('description',''),genres=request.form.get('genres',''),type=request.form.get('type','Manga'),status=request.form.get('status','Đang tiến hành'),featured=bool(request.form.get('featured')),mature=bool(request.form.get('mature')),cover=cover,team_id=request.form.get('team_id',type=int) or None)
        db.session.add(m); db.session.commit(); flash('Đã thêm truyện.','success'); return redirect(url_for('admin_chapters',mid=m.id))
    return render_template('admin/manga_form.html',m=None,teams=Team.query.order_by(Team.name).all())

@app.route('/admin/manga/<int:mid>/edit',methods=['GET','POST'])
@staff_required
def admin_manga_edit(mid):
    m=db.session.get(Manga,mid) or abort(404)
    if request.method=='POST':
        m.title=request.form.get('title',m.title).strip(); m.slug=unique_slug(request.form.get('slug') or m.title,ignore_id=m.id)
        for attr in ['alt_title','author','artist','description','genres','type','status']: setattr(m,attr,request.form.get(attr,getattr(m,attr)))
        m.featured=bool(request.form.get('featured')); m.mature=bool(request.form.get('mature')); m.team_id=request.form.get('team_id',type=int) or None
        cover=upload_image(request.files.get('cover'),'covers') or request.form.get('cover_url','').strip()
        if cover: m.cover=cover
        m.updated_at=utcnow(); db.session.commit(); flash('Đã cập nhật.','success'); return redirect(url_for('admin_manga'))
    return render_template('admin/manga_form.html',m=m,teams=Team.query.order_by(Team.name).all())

@app.post('/admin/manga/<int:mid>/delete')
@admin_required
def admin_manga_delete(mid):
    m=db.session.get(Manga,mid) or abort(404); db.session.delete(m); db.session.commit(); flash('Đã xóa truyện.','success'); return redirect(url_for('admin_manga'))

@app.route('/admin/manga/<int:mid>/chapters')
@staff_required
def admin_chapters(mid):
    m=db.session.get(Manga,mid) or abort(404); rows=Chapter.query.filter_by(manga_id=mid).order_by(Chapter.number.desc()).all(); return render_template('admin/chapter_list.html',m=m,rows=rows)

@app.route('/admin/manga/<int:mid>/chapter/new',methods=['GET','POST'])
@staff_required
def admin_chapter_new(mid):
    m=db.session.get(Manga,mid) or abort(404)
    if request.method=='POST':
        try: number=float(request.form['number'])
        except Exception: flash('Số chương không hợp lệ.','danger'); return redirect(request.url)
        if Chapter.query.filter_by(manga_id=mid,number=number).first(): flash('Chương này đã tồn tại.','danger'); return redirect(request.url)
        pages=[x.strip() for x in request.form.get('page_urls','').splitlines() if x.strip()]
        for f in request.files.getlist('pages'):
            u=upload_image(f,f'chapters/{mid}/{str(number).replace(".","_")}')
            if u: pages.append(u)
        c=Chapter(manga_id=mid,number=number,title=request.form.get('title',''),pages_json=json.dumps(pages,ensure_ascii=False),is_published=bool(request.form.get('is_published','1')))
        db.session.add(c); db.session.flush(); m.updated_at=utcnow()
        if c.is_published: notify_followers(m,c)
        db.session.commit(); flash('Đã đăng chương.','success'); return redirect(url_for('admin_chapters',mid=mid))
    return render_template('admin/chapter_form.html',m=m,c=None,pages=[])

@app.route('/admin/manga/<int:mid>/chapters/import-zip',methods=['GET','POST'])
@staff_required
def admin_chapter_zip_import(mid):
    m=db.session.get(Manga,mid) or abort(404)
    if request.method=='POST':
        zf=request.files.get('zip_file')
        if not zf or not zf.filename.lower().endswith('.zip'): flash('Hãy chọn file ZIP.','danger'); return redirect(request.url)
        with tempfile.TemporaryDirectory() as td:
            zp=Path(td)/'upload.zip'; zf.save(zp)
            try:
                with zipfile.ZipFile(zp) as z:
                    infos=_zip_infos(z); created,skipped=_import_chapter_groups(z,infos,m,td,bool(request.form.get('is_published','1'))); db.session.commit()
                msg=f'Đã import {created} chương.' + (f' Bỏ qua: {", ".join(skipped)}.' if skipped else '')
                flash(msg,'success')
            except (zipfile.BadZipFile,ValueError) as e: db.session.rollback(); flash(str(e) or 'ZIP không hợp lệ.','danger')
        return redirect(url_for('admin_chapters',mid=mid))
    return render_template('admin/chapter_zip_import.html',m=m)

@app.route('/admin/import-series',methods=['GET','POST'])
@staff_required
def admin_import_series():
    if request.method=='POST':
        zf=request.files.get('zip_file')
        if not zf or not zf.filename.lower().endswith('.zip'): flash('Hãy chọn file ZIP.','danger'); return redirect(request.url)
        with tempfile.TemporaryDirectory() as td:
            zp=Path(td)/'series.zip'; zf.save(zp)
            try:
                with zipfile.ZipFile(zp) as z:
                    infos=_zip_infos(z); meta={}
                    metadata=next((i for i in infos if Path(i.filename).name.lower()=='metadata.json' and _safe_member(i.filename)),None)
                    if metadata:
                        meta=json.loads(z.read(metadata).decode('utf-8-sig'))
                    title=(meta.get('title') or request.form.get('title') or Path(zf.filename).stem).strip()
                    if not title: raise ValueError('Thiếu tên truyện.')
                    m=Manga(title=title,slug=unique_slug(meta.get('slug') or title),alt_title=meta.get('alt_title',''),author=meta.get('author',''),artist=meta.get('artist',''),description=meta.get('description',''),genres=','.join(meta.get('genres',[])) if isinstance(meta.get('genres'),list) else meta.get('genres',''),type=meta.get('type','Manga'),status=meta.get('status','Đang tiến hành'),featured=bool(meta.get('featured',False)),mature=bool(meta.get('mature',False)))
                    db.session.add(m); db.session.flush()
                    coverinfo=next((i for i in infos if Path(i.filename).name.lower() in {'cover.jpg','cover.jpeg','cover.png','cover.webp'} and _safe_member(i.filename)),None)
                    if coverinfo:
                        ext=Path(coverinfo.filename).suffix.lower(); cp=Path(td)/f'cover{ext}'
                        with z.open(coverinfo) as src, open(cp,'wb') as out: shutil.copyfileobj(src,out)
                        m.cover=upload_image(cp,'covers')
                    created,skipped=_import_chapter_groups(z,infos,m,td,True); db.session.commit(); flash(f'Đã tạo {m.title} và import {created} chương.','success'); return redirect(url_for('admin_chapters',mid=m.id))
            except Exception as e:
                db.session.rollback(); flash(f'Import thất bại: {e}','danger')
        return redirect(request.url)
    return render_template('admin/import_series.html')

@app.route('/admin/chapter/<int:cid>/edit',methods=['GET','POST'])
@staff_required
def admin_chapter_edit(cid):
    c=db.session.get(Chapter,cid) or abort(404); m=c.manga
    try: pages=json.loads(c.pages_json or '[]')
    except Exception: pages=[]
    if request.method=='POST':
        try: new_number=float(request.form['number'])
        except Exception: flash('Số chương không hợp lệ.','danger'); return redirect(request.url)
        exists=Chapter.query.filter(Chapter.manga_id==m.id,Chapter.number==new_number,Chapter.id!=c.id).first()
        if exists: flash('Số chương đã tồn tại.','danger'); return redirect(request.url)
        c.number=new_number; c.title=request.form.get('title',''); c.is_published=bool(request.form.get('is_published'))
        urls=[x.strip() for x in request.form.get('page_urls','').splitlines() if x.strip()]
        if request.form.get('replace_urls')=='1': pages=urls
        elif urls: pages.extend(urls)
        for f in request.files.getlist('pages'):
            u=upload_image(f,f'chapters/{m.id}/{str(c.number).replace(".","_")}')
            if u: pages.append(u)
        c.pages_json=json.dumps(pages,ensure_ascii=False); m.updated_at=utcnow(); db.session.commit(); flash('Đã cập nhật chương.','success'); return redirect(url_for('admin_chapters',mid=m.id))
    return render_template('admin/chapter_form.html',m=m,c=c,pages=pages)

@app.post('/admin/chapter/<int:cid>/delete')
@staff_required
def admin_chapter_delete(cid):
    c=db.session.get(Chapter,cid) or abort(404); mid=c.manga_id; db.session.delete(c); db.session.commit(); flash('Đã xóa chương.','success'); return redirect(url_for('admin_chapters',mid=mid))

@app.route('/admin/users')
@admin_required
def admin_users():
    q=request.args.get('q','').strip(); qry=User.query
    if q: qry=qry.filter(db.or_(User.username.ilike(f'%{q}%'),User.display_name.ilike(f'%{q}%')))
    return render_template('admin/users.html',rows=qry.order_by(User.id.desc()).all(),q=q)

@app.post('/admin/user/<int:uid>/update')
@admin_required
def admin_user_update(uid):
    u=db.session.get(User,uid) or abort(404)
    if u.id==current_user().id and request.form.get('role')!='admin': flash('Không thể tự hạ quyền admin đang đăng nhập.','warning'); return redirect(url_for('admin_users'))
    u.role=request.form.get('role','user'); u.vip=bool(request.form.get('vip')); u.is_active=bool(request.form.get('is_active')); u.points=request.form.get('points',u.points,type=int); db.session.commit(); flash('Đã cập nhật tài khoản.','success'); return redirect(url_for('admin_users'))

@app.route('/admin/comments')
@staff_required
def admin_comments(): return render_template('admin/comments.html',rows=Comment.query.order_by(Comment.id.desc()).limit(500).all())

@app.post('/admin/comment/<int:cid>/toggle')
@staff_required
def admin_comment_toggle(cid):
    c=db.session.get(Comment,cid) or abort(404); c.hidden=not c.hidden; db.session.commit(); return redirect(url_for('admin_comments'))

@app.post('/admin/comment/<int:cid>/delete')
@admin_required
def admin_comment_delete(cid):
    c=db.session.get(Comment,cid) or abort(404); db.session.delete(c); db.session.commit(); return redirect(url_for('admin_comments'))

@app.route('/admin/reports')
@staff_required
def admin_reports(): return render_template('admin/reports.html',rows=Report.query.order_by(Report.id.desc()).all())

@app.post('/admin/report/<int:rid>/status')
@staff_required
def admin_report_status(rid):
    r=db.session.get(Report,rid) or abort(404); r.status=request.form.get('status','open'); db.session.commit(); return redirect(url_for('admin_reports'))

@app.route('/admin/banners',methods=['GET','POST'])
@admin_required
def admin_banners():
    if request.method=='POST':
        image=upload_image(request.files.get('image_file'),'banners') or request.form.get('image','').strip()
        db.session.add(Banner(title=request.form.get('title','').strip() or 'Banner',subtitle=request.form.get('subtitle',''),image=image,link=request.form.get('link',''),active=bool(request.form.get('active')),sort_order=request.form.get('sort_order',0,type=int))); db.session.commit(); flash('Đã thêm banner.','success')
    return render_template('admin/banners.html',rows=Banner.query.order_by(Banner.sort_order).all())

@app.post('/admin/banner/<int:bid>/delete')
@admin_required
def admin_banner_delete(bid):
    b=db.session.get(Banner,bid) or abort(404); db.session.delete(b); db.session.commit(); return redirect(url_for('admin_banners'))

@app.route('/admin/teams',methods=['GET','POST'])
@admin_required
def admin_teams():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if name:
            base=slugify(request.form.get('slug') or name); candidate=base; n=2
            while Team.query.filter_by(slug=candidate).first(): candidate=f'{base}-{n}'; n+=1
            db.session.add(Team(name=name,slug=candidate,description=request.form.get('description',''))); db.session.commit(); flash('Đã thêm nhóm.','success')
    return render_template('admin/teams.html',rows=Team.query.order_by(Team.name).all())

@app.post('/admin/team/<int:tid>/delete')
@admin_required
def admin_team_delete(tid):
    t=db.session.get(Team,tid) or abort(404); Manga.query.filter_by(team_id=t.id).update({'team_id':None}); db.session.delete(t); db.session.commit(); return redirect(url_for('admin_teams'))

@app.route('/admin/settings',methods=['GET','POST'])
@admin_required
def admin_settings():
    keys=['site_name','site_description','announcement','footer_text','allow_register','facebook_url','discord_url','telegram_url']
    if request.method=='POST':
        for k in keys: set_setting(k,request.form.get(k,''))
        db.session.commit(); flash('Đã lưu cài đặt.','success')
    return render_template('admin/settings.html',settings={k:setting(k,'') for k in keys})

@app.get('/admin/export')
@admin_required
def admin_export():
    payload={'exported_at':utcnow().isoformat()+'Z','settings':{x.key:x.value for x in SiteSetting.query.all()},'manga':[]}
    for m in Manga.query.order_by(Manga.id).all():
        payload['manga'].append({'title':m.title,'slug':m.slug,'alt_title':m.alt_title,'author':m.author,'artist':m.artist,'description':m.description,'genres':m.genres,'type':m.type,'status':m.status,'cover':m.cover,'featured':m.featured,'mature':m.mature,'chapters':[{'number':c.number,'title':c.title,'pages':json.loads(c.pages_json or '[]'),'is_published':c.is_published} for c in Chapter.query.filter_by(manga_id=m.id).order_by(Chapter.number).all()]})
    data=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8'); return send_file(io.BytesIO(data),mimetype='application/json',as_attachment=True,download_name=f'bmanga-backup-{datetime.utcnow().strftime("%Y%m%d-%H%M")}.json')

@app.get('/sitemap.xml')
def sitemap():
    urls=[url_for('home',_external=True),url_for('search',_external=True),url_for('rankings',_external=True)]
    urls += [url_for('manga_detail',slug=m.slug,_external=True) for m in Manga.query.all()]
    xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{u}</loc></url>' for u in urls)+'</urlset>'
    return Response(xml,mimetype='application/xml')

@app.get('/robots.txt')
def robots(): return Response('User-agent: *\nAllow: /\nSitemap: '+url_for('sitemap',_external=True)+'\n',mimetype='text/plain')

@app.get('/health')
def health():
    try: db.session.execute(db.text('SELECT 1')); database='ok'
    except Exception: database='error'
    return jsonify(status='ok',app='Bmanga',database=database)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='Bạn không có quyền truy cập trang này.'),403
@app.errorhandler(404)
def not_found(e): return render_template('error.html',code=404,message='Không tìm thấy nội dung.'),404
@app.errorhandler(413)
def too_large(e): return render_template('error.html',code=413,message='File tải lên quá lớn.'),413

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=os.getenv('FLASK_ENV')!='production')
