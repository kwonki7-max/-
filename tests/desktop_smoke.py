"""Exercise the actual Electron shell against an isolated test server.
Linux CI uses --no-sandbox because the container cannot configure SUID helpers.
Distributed Windows apps keep Chromium sandbox enabled; this flag is test-only.
Requires the environment's Python Playwright and project npm dependencies.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
PYTHON=str(ROOT/'.venv/bin/python')
PASSWORD='desktop-test-only-1234'
def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]
def wait_http(url):
    for _ in range(150):
        try:
            with urlopen(url,timeout=1) as r:
                if r.status==200:return
        except OSError:time.sleep(.1)
    raise RuntimeError('Readiness check timed out: '+url)

with tempfile.TemporaryDirectory(prefix='gijunsil-desktop-test-') as directory:
    temp=Path(directory)
    server_port=free_port();cdp_port=free_port()
    env={**os.environ,'ESTIMATE_DATABASE':str(temp/'test.sqlite3')}
    subprocess.run([PYTHON,'-m','flask','--app','wsgi','create-admin','--email','admin@example.test','--name','관리자'],input=PASSWORD+'\n'+PASSWORD+'\n',text=True,cwd=ROOT,env=env,check=True,capture_output=True)
    server=subprocess.Popen([PYTHON,'-m','gunicorn','--bind',f'127.0.0.1:{server_port}','--workers','1','wsgi:app'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    desktop=None
    try:
        wait_http(f'http://127.0.0.1:{server_port}/health')
        with (temp/'electron.log').open('w') as log:
            desktop=subprocess.Popen([str(ROOT/'node_modules/electron/dist/electron'),'--no-sandbox','--ozone-platform=headless','--disable-gpu',f'--remote-debugging-port={cdp_port}',str(ROOT)],cwd=ROOT,env={**os.environ,'GIJUNSIL_DESKTOP_TEST':'1','GIJUNSIL_TEST_SERVER':f'http://127.0.0.1:{server_port}','GIJUNSIL_TEST_USER_DATA':str(temp/'profile'),'XDG_CACHE_HOME':str(temp/'cache')},stdout=log,stderr=log)
            wait_http(f'http://127.0.0.1:{cdp_port}/json/version')
            with sync_playwright() as p:
                browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp_port}')
                page=None
                for _ in range(100):
                    pages=[pg for c in browser.contexts for pg in c.pages if pg.url.startswith(f'http://127.0.0.1:{server_port}')]
                    if pages:
                        page=pages[0];break
                    time.sleep(.1)
                assert page is not None,'Company login window did not open'
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                expect(page.locator('#auth')).to_be_visible()
                expect(page.locator('#desktop-bar')).to_be_visible()
                assert page.evaluate('typeof require')=='undefined'
                assert page.evaluate('typeof process')=='undefined'
                assert page.evaluate('typeof window.desktop.openLocal')=='undefined'
                page.screenshot(path='/tmp/gijunsil-desktop-login.png')
                page.locator('#auth-form [name=email]').fill('admin@example.test')
                page.locator('#auth-form [name=password]').fill(PASSWORD)
                page.locator('#auth-submit').click()
                expect(page.locator('#condition-rows tr')).to_have_count(28)
                expect(page.locator('#users-nav')).to_be_visible()
                page.locator('#search').fill('와이어메쉬')
                expect(page.locator('#condition-rows tr')).to_have_count(1)
                page.locator('#search').fill('')
                page.screenshot(path='/tmp/gijunsil-desktop-workspace.png')
                page.locator('[data-page=calculator]').click()
                page.locator('#calc-form [name=area]').fill('100')
                page.locator('#calc-form [name=price]').fill('1000')
                page.get_by_role('button',name='물량 계산하기',exact=True).click()
                expect(page.locator('#calc-result')).to_contain_text('110,000원')
                page.locator('#add-basket').click()
                page.locator('#quote-form [name=title]').fill('데스크톱 검증 견적')
                page.locator('#quote-form [name=project]').fill('검증 현장')
                page.get_by_role('button',name='견적 저장',exact=True).click()
                expect(page.locator('#content')).to_contain_text('데스크톱 검증 견적')
                # Logout must clear the authenticated session in the desktop partition.
                page.locator('#logout').click()
                expect(page.locator('#auth')).to_be_visible()
                assert not errors,errors
                browser.close()
            print('PASS: Electron automatic company connection, login, admin UI, 28 conditions, search, calculation, quote save, logout, isolated renderer, no local workspace option.')
    finally:
        if (temp/'electron.log').exists():
            Path('/tmp/gijunsil-electron-debug.log').write_text((temp/'electron.log').read_text())
        if desktop:
            desktop.terminate()
            try:desktop.wait(timeout=10)
            except subprocess.TimeoutExpired:desktop.kill();desktop.wait()
        server.terminate();server.wait(timeout=10)
