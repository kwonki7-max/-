"""Run on Windows after silent installation. No company credentials required."""
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

executable=Path(os.environ['LOCALAPPDATA'])/'Programs'/'Gijunsil'/'Gijunsil.exe'
assert executable.is_file()
with socket.socket() as s:
    s.bind(('127.0.0.1',0));port=s.getsockname()[1]
process=subprocess.Popen([str(executable),f'--remote-debugging-port={port}'])
try:
    for _ in range(150):
        try:
            with urlopen(f'http://127.0.0.1:{port}/json/version',timeout=1) as r:
                if r.status==200:break
        except OSError:time.sleep(.2)
    else:raise RuntimeError('Installed desktop application failed to start')
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        page=browser.contexts[0].pages[0]
        expect(page.locator('#version')).to_contain_text('0.1.0')
        expect(page.locator('#state-title')).to_have_text('회사 연결 준비 중')
        assert page.evaluate('typeof require')=='undefined'
        assert page.evaluate('typeof window.desktop.openLocal')=='undefined'
        Path('dist').mkdir(exist_ok=True)
        page.screenshot(path='dist/windows-installed.png')
        page.locator('#close').click()
        process.wait(timeout=15)
        print('PASS: installed Windows app starts, shows the honest unconfigured state, keeps renderer isolated, and exits.')
finally:
    if process.poll() is None:
        process.terminate();process.wait(timeout=15)
