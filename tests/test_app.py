import json
import sqlite3
from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash
from app import create_app, calculate

PASSWORD = 'test-only-password-1234'

@pytest.fixture()
def app(tmp_path):
    app = create_app({'TESTING':True,'DATABASE':str(tmp_path/'test.sqlite3'),'SECRET_KEY':'test-key-only'})
    with sqlite3.connect(app.config['DATABASE']) as conn:
        for email, role in [('admin@example.test','admin'),('one@example.test','user'),('two@example.test','user')]:
            conn.execute("INSERT INTO users(email,name,password,role,status) VALUES(?,?,?,?,'active')",(email,role,generate_password_hash(PASSWORD),role))
    return app

class Client:
    def __init__(self,app,email=None):
        self.client=app.test_client()
        self.token=self.client.get('/api/session').json['csrf']
        if email:
            result=self.call('login',{'email':email,'password':PASSWORD})
            assert result.status_code == 200
            self.token=result.json['csrf']
    def call(self,path,data,method='POST'):
        return self.client.open('/api/'+path,method=method,json=data,headers={'X-CSRF-Token':self.token})
    def get(self,path):
        return self.client.get('/api/'+path)


def test_private_routes_and_csrf(app):
    anonymous=Client(app)
    for path in ['conditions','quotes','audit','users','quotes/1/csv']:
        assert anonymous.get(path).status_code==401
    assert anonymous.client.post('/api/login',json={}).status_code==403
    assert anonymous.client.post('/api/register',json={}).status_code==403
    assert anonymous.client.get('/').status_code==200
    assert anonymous.client.get('/health').json=={'status':'ok'}


def test_signup_requires_approval_and_cannot_escalate(app):
    member=Client(app)
    assert member.call('register',{'email':'new@example.test','name':'신규','password':PASSWORD,'role':'admin','status':'active'}).status_code==201
    assert member.call('login',{'email':'new@example.test','password':PASSWORD}).status_code==403
    admin=Client(app,'admin@example.test')
    record=next(u for u in admin.get('users').json if u['email']=='new@example.test')
    assert record['role']=='user' and record['status']=='pending'
    assert admin.call('users/'+str(record['id']),{'status':'active'},'PUT').status_code==200
    active=Client(app,'new@example.test')
    assert active.get('conditions').status_code==200
    assert active.get('users').status_code==403
    assert active.call('users/1',{'status':'disabled'},'PUT').status_code==403
    assert admin.call('users/'+str(record['id']),{'status':'disabled'},'PUT').status_code==200
    assert active.get('conditions').status_code==401
    assert admin.call('users/1',{'status':'disabled'},'PUT').status_code==403


def test_shared_edit_audit_and_conflict(app):
    one,two=Client(app,'one@example.test'),Client(app,'two@example.test')
    conditions=one.get('conditions').json
    assert len(conditions)==28
    assert [c['id'] for c in conditions if c['status']=='협의 전']==[1,6,8]
    condition=conditions[1]
    original=dict(condition)
    condition['content']='공동 수정 검증'
    result=one.call('conditions/2',condition,'PUT')
    assert result.status_code==200 and result.json['version']==2
    assert two.get('conditions').json[1]['content']=='공동 수정 검증'
    assert two.call('conditions/2',original,'PUT').status_code==409
    history=two.get('audit').json
    assert len(history)==1
    assert json.loads(history[0]['before_json'])['content']==original['content']
    assert json.loads(history[0]['after_json'])['content']=='공동 수정 검증'
    condition['name']='신규 조건'
    assert two.call('conditions',condition).status_code==201
    assert len(one.get('conditions').json)==29


@pytest.mark.parametrize('data,quantity',[
    ({'kind':'mesh','area':'100','price':1000},'110.000000'),
    ({'kind':'mesh','area':'0.1','price':10},'0.110000'),
    ({'kind':'curtain','width':150,'height':50,'length':1},'0.200000'),
    ({'kind':'curtain','width':150,'height':70,'length':1},'0.220000'),
    ({'kind':'curtain','width':150,'height':50,'length':10},'2.000000'),
])
def test_pdf_examples_and_decimal_calculation(data,quantity):
    assert calculate(data)['quantity']==quantity


@pytest.mark.parametrize('value',['NaN','Infinity','-1','1000001',None,True,{},'1e999999'])
def test_invalid_numbers_rejected(app,value):
    user=Client(app,'one@example.test')
    assert user.call('calculate',{'kind':'mesh','area':value}).status_code==400


def test_quote_ownership_server_calculation_and_csv(app):
    one,two,admin=Client(app,'one@example.test'),Client(app,'two@example.test'),Client(app,'admin@example.test')
    data={'title':'=HYPERLINK("x")','project':'현장','notes':'메모','items':[{'kind':'mesh','area':100,'price':1000,'amount':1}]}
    saved=one.call('quotes',data)
    assert saved.status_code==200 and saved.json['total']=='110000'
    qid=saved.json['id']
    assert len(one.get('quotes').json)==1 and two.get('quotes').json==[]
    assert two.get(f'quotes/{qid}/csv').status_code==404
    assert two.call(f'quotes/{qid}',data,'PUT').status_code==404
    assert len(admin.get('quotes').json)==1
    exported=one.get(f'quotes/{qid}/csv')
    assert exported.status_code==200 and "'=HYPERLINK" in exported.text
    assert '110000' in exported.text
    data['version']=1
    data['items'][0]['area']=200
    assert one.call(f'quotes/{qid}',data,'PUT').json['total']=='220000'
    assert one.call(f'quotes/{qid}',data,'PUT').status_code==409
    assert one.call('quotes',{**data,'items':[]}).status_code==400


def test_persistence_and_seed_idempotence(app):
    one=Client(app,'one@example.test')
    condition=one.get('conditions').json[0]
    condition['content']='유지할 수정 내용'
    one.call('conditions/1',condition,'PUT')
    other=create_app({'TESTING':True,'DATABASE':app.config['DATABASE'],'SECRET_KEY':'test-key-only'})
    records=Client(other,'one@example.test').get('conditions').json
    assert len(records)==28 and records[0]['content']=='유지할 수정 내용'


def test_admin_bootstrap_and_rate_limit(tmp_path):
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'admin.sqlite3'),'SECRET_KEY':'test-key-only'})
    args=['create-admin','--email','owner@example.test','--name','관리자']
    result=app.test_cli_runner().invoke(args=args,input=PASSWORD+'\n'+PASSWORD+'\n')
    assert result.exit_code==0
    repeat=app.test_cli_runner().invoke(args=args,input=PASSWORD+'\n'+PASSWORD+'\n')
    assert repeat.exit_code!=0
    client=Client(app)
    for _ in range(10):
        assert client.call('login',{'email':'nobody@example.test','password':PASSWORD}).status_code==401
    assert client.call('login',{'email':'nobody@example.test','password':PASSWORD}).status_code==429


def test_security_headers_and_logout(app):
    client=Client(app,'one@example.test')
    assert 'frame-ancestors' in client.get('session').headers['Content-Security-Policy']
    assert 'HttpOnly' in client.get('session').headers.get('Set-Cookie','')
    assert client.call('logout',{}).status_code==200
    assert client.get('conditions').status_code==401
