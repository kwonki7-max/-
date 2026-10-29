"""Build the Docker image first; validates isolated deployment and persistent data."""
import http.cookiejar
import json
import os
import subprocess
import time
import uuid
from urllib.request import Request, build_opener, HTTPCookieProcessor

name='gijunsil-smoke-'+uuid.uuid4().hex[:8]
volume=name+'-data'
env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')}
def docker(*args,input=None):
    return subprocess.run(['docker','--host=unix:///var/run/docker.sock',*args],env=env,input=input,text=True,capture_output=True,check=True).stdout.strip()
started=False
try:
    docker('volume','create',volume)
    docker('run','-d','--name',name,'-p','127.0.0.1::8000','-e','COOKIE_SECURE=0','-v',volume+':/data','gijunsil-server:dev')
    started=True
    def connect():
        port=docker('port',name,'8000/tcp').rsplit(':',1)[1]
        base='http://127.0.0.1:'+port
        opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for _ in range(100):
            try:
                with opener.open(base+'/health',timeout=1) as r:
                    if json.load(r)['status']=='ok':break
            except OSError:time.sleep(.1)
        else:
            print(docker('logs',name))
            raise RuntimeError('Container did not become healthy')
        return base,opener
    base,opener=connect()
    password='container-test-only-1234'
    docker('exec','-i',name,'flask','--app','wsgi','create-admin','--email','admin@example.test','--name','배포 검증 관리자',input=password+'\n'+password+'\n')
    assert docker('exec',name,'id','-u')=='10001'
    def login():
        with opener.open(base+'/api/session') as r:token=json.load(r)['csrf']
        with opener.open(Request(base+'/api/login',data=json.dumps({'email':'admin@example.test','password':password}).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':token})) as r:return json.load(r)['csrf']
    token=login()
    with opener.open(base+'/api/conditions') as r:rows=json.load(r)
    assert len(rows)==28
    rows[0]['content']='컨테이너 재시작 후에도 유지되어야 하는 기준'
    with opener.open(Request(base+'/api/conditions/1',method='PUT',data=json.dumps(rows[0]).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':token})) as r:assert r.status==200
    docker('restart',name)
    base,opener=connect()
    login()
    with opener.open(base+'/api/conditions') as r:rows=json.load(r)
    assert len(rows)==28 and rows[0]['content']=='컨테이너 재시작 후에도 유지되어야 하는 기준'
    print('PASS: Docker service starts as non-root, admin login and protected records work, and account/edited condition persist across restart.')
finally:
    if started:docker('rm','-f',name)
    docker('volume','rm',volume)
