import csv
import functools
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import click
from flask import Flask, g, jsonify, render_template, request, session, Response
from werkzeug.security import check_password_hash, generate_password_hash
from seed import ROWS

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conditions(id INTEGER PRIMARY KEY, area TEXT NOT NULL, trade TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL, unit TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, before_json TEXT, after_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL, project TEXT NOT NULL, notes TEXT NOT NULL, items_json TEXT NOT NULL, total TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, started REAL NOT NULL);
'''
FIELDS = ('area', 'trade', 'name', 'spec', 'unit', 'content', 'status')
STATUSES = ('협의 전', '이후 전공사 반영', '내부 협의 완료')

class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(g.app_database, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise Problem('올바른 입력을 보내주세요.')
    return data

def text_value(data, key, maximum=200, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise Problem(f'{key}: 입력값을 확인해주세요. (최대 {maximum}자)')
    return value.strip()

def number(data, key, default=None, maximum='1000000'):
    try:
        raw = data.get(key, default)
        if isinstance(raw, bool):
            raise ValueError()
        value = Decimal(str(raw))
        if not value.is_finite() or value < 0 or value > Decimal(maximum):
            raise ValueError()
        return value
    except (InvalidOperation, ValueError, TypeError):
        raise Problem(f'{key}: 0 이상 {maximum} 이하 숫자를 입력해주세요.')

def calculate(data):
    kind = data.get('kind')
    price = number(data, 'price', 0)
    if kind == 'mesh':
        area = number(data, 'area')
        quantity = area * Decimal('1.10')
        name, unit = '와이어메쉬', 'M²'
        formula = f'{area} M² × 1.10 (10% 할증)'
        source = 'PDF 2번 · #10-150-150 · 부자재 별도 반영'
    elif kind == 'curtain':
        width, height = number(data, 'width', maximum='10000'), number(data, 'height', maximum='10000')
        length = number(data, 'length')
        quantity = (width + height) / 1000 * length
        name, unit = '커튼박스 석고보드 ㄱ자면', 'M²'
        formula = f'({width} + {height}) mm ÷ 1,000 × {length} M'
        source = 'PDF 7번 · ㄱ자면 1겹 면적 · 천정틀 차감은 별도 검토'
    else:
        raise Problem('지원하지 않는 계산입니다.')
    quantity = quantity.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
    amount = (quantity * price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return dict(kind=kind, name=name, unit=unit, quantity=format(quantity, 'f'), price=str(price), amount=str(amount), formula=formula, source=source, inputs={k:v for k,v in data.items() if k in ('kind','price','area','width','height','length')})

def protected(admin=False):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            user = db().execute('SELECT * FROM users WHERE id=?', (session.get('uid'),)).fetchone()
            if not user or user['status'] != 'active':
                raise Problem('로그인이 필요하거나 이용이 승인되지 않았습니다.', 401)
            if admin and user['role'] != 'admin':
                raise Problem('관리자만 이용할 수 있습니다.', 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapped
    return decorate

def audit(action, target, before=None, after=None):
    db().execute('INSERT INTO audit(user_id,action,target,before_json,after_json) VALUES(?,?,?,?,?)', (g.user['id'], action, str(target), json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(DATABASE=os.environ.get('ESTIMATE_DATABASE', str(Path(app.instance_path)/'estimate.sqlite3')), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=256*1024)
    if config:
        app.config.update(config)
    Path(app.config['DATABASE']).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        key_path = Path(app.config['DATABASE']).parent / 'session.key'
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = key_path.read_text()
    with sqlite3.connect(app.config['DATABASE']) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(SCHEMA)
        # Seed once; IDs remain stable. Existing edited records are never overwritten.
        if not conn.execute('SELECT 1 FROM conditions LIMIT 1').fetchone():
            conn.executemany('INSERT INTO conditions(area,trade,name,spec,unit,content,status) VALUES(?,?,?,?,?,?,?)', ROWS)
    @app.before_request
    def before():
        g.app_database = app.config['DATABASE']
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            token = session.get('csrf')
            if not token or not secrets.compare_digest(token, request.headers.get('X-CSRF-Token','')):
                raise Problem('세션이 만료되었습니다. 새로고침 후 다시 시도해주세요.', 403)
    @app.after_request
    def security(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
    @app.teardown_appcontext
    def close(_):
        conn = g.pop('db', None)
        if conn:
            conn.close()
    @app.errorhandler(Problem)
    def problem(error):
        return jsonify(error=error.message), error.status
    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='입력 데이터가 너무 큽니다.'), 413
    @app.get('/')
    def index():
        return render_template('index.html')
    @app.get('/health')
    def health():
        db().execute('SELECT 1').fetchone()
        return jsonify(status='ok')
    @app.get('/api/session')
    def get_session():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        user = db().execute("SELECT id,email,name,role,status FROM users WHERE id=? AND status='active'", (session.get('uid'),)).fetchone()
        return jsonify(user=dict(user) if user else None, csrf=session['csrf'])
    def limit(key, maximum=10):
        now = time.time()
        conn = db()
        conn.execute('DELETE FROM attempts WHERE started < ?', (now-900,))
        conn.execute('INSERT INTO attempts(key,count,started) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key,now))
        row = conn.execute('SELECT count FROM attempts WHERE key=?',(key,)).fetchone()
        conn.commit()
        if row['count'] > maximum:
            raise Problem('시도가 너무 많습니다. 15분 후 다시 시도해주세요.',429)
    @app.post('/api/register')
    def register():
        limit('register:'+str(request.remote_addr), 20)
        data = payload()
        email = text_value(data,'email',254).lower()
        name = text_value(data,'name',80)
        password = text_value(data,'password',128)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(password) < 12:
            raise Problem('올바른 이메일과 12자 이상의 비밀번호를 입력해주세요.')
        try:
            db().execute('INSERT INTO users(email,name,password) VALUES(?,?,?)', (email,name,generate_password_hash(password)))
            db().commit()
        except sqlite3.IntegrityError:
            raise Problem('이미 사용 중인 이메일입니다.',409)
        return jsonify(message='가입 신청이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다.'),201
    @app.post('/api/login')
    def login():
        data = payload()
        email = text_value(data,'email',254).lower()
        password = text_value(data,'password',128)
        limit('login-ip:'+str(request.remote_addr), 40)
        limit('login:'+email)
        user = db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        # Always perform a password hash check, including unknown users.
        valid = check_password_hash(user['password'] if user else app.config['DUMMY_HASH'], password)
        if not user or not valid:
            raise Problem('이메일 또는 비밀번호를 확인해주세요.',401)
        if user['status'] != 'active':
            raise Problem('관리자 승인 대기 중이거나 이용이 중지된 계정입니다.',403)
        session.clear()
        session.update(uid=user['id'],csrf=secrets.token_hex(32))
        session.permanent = True
        db().execute('DELETE FROM attempts WHERE key=?',('login:'+email,))
        db().commit()
        return get_session()
    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)
    @app.get('/api/conditions')
    @protected()
    def conditions():
        return jsonify([dict(r) for r in db().execute('SELECT * FROM conditions ORDER BY id')])
    @app.route('/api/conditions/<int:cid>', methods=['PUT'])
    @protected()
    def update_condition(cid):
        data = payload()
        values = {key:text_value(data,key,4000 if key=='content' else 200, key in ('name','content','status')) for key in FIELDS}
        if values['status'] not in STATUSES:
            raise Problem('적용 상태를 확인해주세요.')
        before = db().execute('SELECT * FROM conditions WHERE id=?',(cid,)).fetchone()
        if not before:
            raise Problem('조건을 찾을 수 없습니다.',404)
        changed = db().execute('UPDATE conditions SET '+','.join(f'{key}=?' for key in FIELDS)+',version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?', (*values.values(),cid,data.get('version')))
        if changed.rowcount != 1:
            raise Problem('다른 사용자가 먼저 수정했습니다. 목록을 새로고침한 뒤 다시 수정해주세요.',409)
        after = dict(db().execute('SELECT * FROM conditions WHERE id=?',(cid,)).fetchone())
        audit('견적조건 수정',cid,dict(before),after)
        db().commit()
        return jsonify(after)
    @app.post('/api/conditions')
    @protected()
    def add_condition():
        data = payload()
        values = {key:text_value(data,key,4000 if key=='content' else 200,key in ('name','content','status')) for key in FIELDS}
        if values['status'] not in STATUSES:
            raise Problem('적용 상태를 확인해주세요.')
        cid = db().execute('INSERT INTO conditions('+','.join(FIELDS)+') VALUES(?,?,?,?,?,?,?)',tuple(values.values())).lastrowid
        audit('견적조건 추가',cid,None,values)
        db().commit()
        return jsonify(id=cid),201
    @app.post('/api/calculate')
    @protected()
    def calculation():
        return jsonify(calculate(payload()))
    def accessible_quote(qid):
        quote = db().execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
        if not quote or (quote['user_id'] != g.user['id'] and g.user['role'] != 'admin'):
            raise Problem('견적을 찾을 수 없습니다.',404)
        return dict(quote)
    @app.get('/api/quotes')
    @protected()
    def quotes():
        query = 'SELECT q.*,u.name AS owner FROM quotes q JOIN users u ON u.id=q.user_id'
        rows = db().execute(query+('' if g.user['role']=='admin' else ' WHERE q.user_id=?')+' ORDER BY q.updated_at DESC,q.id DESC',() if g.user['role']=='admin' else (g.user['id'],))
        return jsonify([dict(r) for r in rows])
    @app.route('/api/quotes',methods=['POST'])
    @app.route('/api/quotes/<int:qid>',methods=['PUT'])
    @protected()
    def save_quote(qid=None):
        before = accessible_quote(qid) if qid else None
        data = payload()
        title, project, notes = text_value(data,'title'), text_value(data,'project'), text_value(data,'notes',4000,False)
        inputs = data.get('items')
        if not isinstance(inputs,list) or not 1 <= len(inputs) <= 100 or any(not isinstance(i,dict) for i in inputs):
            raise Problem('계산 항목을 1~100개 추가해주세요.')
        items = [calculate(item) for item in inputs]
        total = str(sum((Decimal(item['amount']) for item in items),Decimal(0)))
        values = (title,project,notes,json.dumps(items,ensure_ascii=False),total)
        if qid:
            cursor = db().execute('UPDATE quotes SET title=?,project=?,notes=?,items_json=?,total=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?',(*values,qid,data.get('version')))
            if cursor.rowcount != 1:
                raise Problem('견적이 변경되었습니다. 다시 열어주세요.',409)
        else:
            qid = db().execute('INSERT INTO quotes(title,project,notes,items_json,total,user_id) VALUES(?,?,?,?,?,?)',(*values,g.user['id'])).lastrowid
        audit('견적 저장',f'견적 {qid}',before,dict(title=title,project=project,items=items,total=total))
        db().commit()
        return jsonify(id=qid,total=total)
    @app.get('/api/quotes/<int:qid>/csv')
    @protected()
    def export_quote(qid):
        quote = accessible_quote(qid)
        stream = io.StringIO()
        writer = csv.writer(stream)
        def safe(value):
            s = str(value)
            return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s
        writer.writerow(['견적명','현장','품명','산식','수량','단위','단가(원)','금액(원)'])
        for item in json.loads(quote['items_json']):
            writer.writerow([safe(v) for v in [quote['title'],quote['project'],item['name'],item['formula'],item['quantity'],item['unit'],item['price'],item['amount']]])
        return Response('\ufeff'+stream.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="estimate-{qid}.csv"'})
    @app.get('/api/audit')
    @protected()
    def history():
        return jsonify([dict(r) for r in db().execute("SELECT a.*,u.name AS author FROM audit a JOIN users u ON u.id=a.user_id WHERE a.action LIKE '견적조건%' ORDER BY a.id DESC LIMIT 200")])
    @app.get('/api/users')
    @protected(admin=True)
    def users():
        return jsonify([dict(r) for r in db().execute('SELECT id,name,email,role,status,created_at FROM users ORDER BY id DESC')])
    @app.put('/api/users/<int:uid>')
    @protected(admin=True)
    def update_user(uid):
        status = payload().get('status')
        if status not in ('active','disabled'):
            raise Problem('계정 상태를 확인해주세요.')
        user = db().execute('SELECT id,name,email,role,status FROM users WHERE id=?',(uid,)).fetchone()
        if not user:
            raise Problem('회원을 찾을 수 없습니다.',404)
        if user['role']=='admin':
            raise Problem('관리자 계정은 여기서 변경할 수 없습니다.',403)
        db().execute('UPDATE users SET status=? WHERE id=?',(status,uid))
        audit('회원 상태 변경',uid,dict(user),{'status':status})
        db().commit()
        return jsonify(ok=True)
    @app.cli.command('create-admin')
    @click.option('--email',prompt=True)
    @click.option('--name',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(email,name,password):
        """서버 운영자만 실행하는 최초 관리자 생성. 기존 계정을 승격하지 않음."""
        if len(password)<12 or len(password)>128 or password != password.strip() or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not name.strip():
            raise click.ClickException('올바른 이메일, 이름, 앞뒤 공백 없는 12~128자 비밀번호가 필요합니다.')
        conn = sqlite3.connect(app.config['DATABASE'])
        try:
            if conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
                raise click.ClickException('관리자가 이미 존재합니다.')
            conn.execute("INSERT INTO users(email,name,password,role,status) VALUES(?,?,?,'admin','active')",(email.strip().lower(),name.strip(),generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            raise click.ClickException('이미 가입한 이메일입니다. 별도 관리자 이메일을 사용해주세요.')
        finally:
            conn.close()
        click.echo('관리자 계정이 생성되었습니다.')
    app.config['DUMMY_HASH'] = generate_password_hash(secrets.token_hex(24))
    return app
