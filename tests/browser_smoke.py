"""Optional browser verification. Uses a temporary DB and test-only accounts.
Run with a Python containing Playwright: python tests/browser_smoke.py
Set APP_PYTHON to the Python containing the project's dependencies.
"""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get('APP_PYTHON',str(ROOT/'.venv/bin/python'))
PASSWORD = 'browser-test-only-12345'
with tempfile.TemporaryDirectory(prefix='estimate-browser-') as temporary:
    env={**os.environ,'ESTIMATE_DATABASE':str(Path(temporary)/'test.sqlite3')}
    subprocess.run([PYTHON,'-m','flask','--app','wsgi','create-admin','--email','admin@example.test','--name','테스트 관리자'],input=PASSWORD+'\n'+PASSWORD+'\n',text=True,cwd=ROOT,env=env,check=True,capture_output=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    server=subprocess.Popen([PYTHON,'-m','gunicorn','--bind',f'127.0.0.1:{port}','--workers','1','wsgi:app'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        base=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                with urlopen(base+'/health',timeout=1) as response:
                    if response.status==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server did not start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(base)
            page.locator('#register-tab').click()
            page.locator('#auth-form [name=name]').fill('현장 담당자')
            page.locator('#auth-form [name=email]').fill('member@example.test')
            page.locator('#auth-form [name=password]').fill(PASSWORD)
            page.locator('#auth-submit').click()
            expect(page.locator('#auth-message')).to_contain_text('가입 신청이 완료')
            def login(email):
                page.locator('#auth-form [name=email]').fill(email)
                page.locator('#auth-form [name=password]').fill(PASSWORD)
                page.locator('#auth-submit').click()
                expect(page.locator('#workspace')).to_be_visible()
                expect(page.locator('#condition-rows tr')).to_have_count(28)
            login('admin@example.test')
            page.locator('[data-page=users]').click()
            page.on('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='이용 승인',exact=True).click()
            expect(page.get_by_role('button',name='이용 중지',exact=True)).to_be_visible()
            page.locator('#logout').click()
            expect(page.locator('#auth')).to_be_visible()
            login('member@example.test')
            expect(page.locator('#users-nav')).to_be_hidden()
            page.locator('#search').fill('와이어메쉬')
            expect(page.locator('#condition-rows tr')).to_have_count(1)
            page.get_by_role('button',name='보기 / 수정 ↗',exact=True).click()
            page.locator('#condition-form [name=content]').fill('브라우저에서 일반 사용자 공동 수정 확인')
            page.get_by_role('button',name='변경사항 저장',exact=True).click()
            expect(page.locator('#editor')).not_to_be_visible()
            expect(page.locator('#condition-rows tr')).to_have_count(28)
            page.screenshot(path='/tmp/estimate-desktop.png',full_page=True)
            page.locator('[data-page=history]').click()
            expect(page.locator('.history-entry')).to_have_count(1)
            page.get_by_text('변경 전·후 보기',exact=True).click()
            expect(page.locator('.diff')).to_contain_text('브라우저에서 일반 사용자 공동 수정 확인')
            page.locator('[data-page=calculator]').click()
            page.locator('#calc-form [name=area]').fill('100')
            page.locator('#calc-form [name=price]').fill('1000')
            page.get_by_role('button',name='물량 계산하기',exact=True).click()
            expect(page.locator('#calc-result')).to_contain_text('110,000원')
            page.locator('#add-basket').click()
            page.locator('#calc-kind').select_option('curtain')
            page.locator('#calc-form [name=length]').fill('10')
            page.locator('#calc-form [name=price]').fill('5000')
            page.get_by_role('button',name='물량 계산하기',exact=True).click()
            expect(page.locator('#calc-result')).to_contain_text('10,000원')
            page.locator('#add-basket').click()
            page.locator('#quote-form [name=title]').fill('브라우저 검증 견적')
            page.locator('#quote-form [name=project]').fill('검증 현장')
            page.get_by_role('button',name='견적 저장',exact=True).click()
            expect(page.locator('#content')).to_contain_text('120,000원')
            with page.expect_download() as download:
                page.get_by_role('link',name='CSV',exact=True).click()
            path=download.value.path()
            assert '110000' in Path(path).read_text(encoding='utf-8-sig')
            page.get_by_role('button',name='열기 / 수정',exact=True).click()
            expect(page.locator('.quote-item')).to_have_count(2)
            page.locator('#quote-form [name=title]').fill('수정한 견적')
            page.get_by_role('button',name='견적 저장',exact=True).click()
            expect(page.locator('#content')).to_contain_text('수정한 견적')
            page.reload()
            expect(page.locator('#condition-rows tr')).to_have_count(28)
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path='/tmp/estimate-mobile.png',full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert not errors, errors
            browser.close()
            print('PASS: signup, approval, login, member editing, audit, both calculations, quote create/edit, CSV, session persistence, mobile layout; no browser JS errors.')
    finally:
        server.terminate()
        server.wait(timeout=10)
