"""Synthetic browser acceptance for the Python 3.14 / Streamlit 1.63 upgrade.

Starts isolated local services only. Run in the validation container with /tmp
mounted as tmpfs: Chromium's native file-drop test needs a temporary filesystem
entry. No conversation screenshots, traces or content logs are saved.
"""
import contextlib
import http.client
import io
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reliability_failures import Boundary, STATE, TOKENIZER_METADATA, reset, submit, wait_idle
from scripts.verify_chat_media import start_app
from http.server import ThreadingHTTPServer

RELEASED = threading.Event()
RELEASE_RESULT = {}


class UpgradeBoundary(Boundary):
    def do_POST(self):
        if self.path == '/released':
            RELEASE_RESULT.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            RELEASED.set()
            self.send(200, {})
        else:
            super().do_POST()


def add_file(locator, name, *, size=20, content=None, mime='text/plain', event='change'):
    if event == 'drop':
        # An untrusted JS DragEvent does not reproduce an OS file drop. CDP
        # supplies native filesystem metadata and browser drag event semantics.
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / name
            file.write_bytes(bytes(content) if content is not None else bytes(size))
            box = locator.bounding_box()
            cdp = locator.page.context.new_cdp_session(locator.page)
            try:
                for action in ('dragEnter', 'dragOver', 'drop'):
                    cdp.send('Input.dispatchDragEvent', {
                        'type': action, 'x': box['x'] + 40, 'y': box['y'] + 30,
                        'data': {'items': [], 'files': [str(file)], 'dragOperationsMask': 1}})
                    if action == 'dragOver':
                        expect(locator.page.get_by_text('Drag and drop files here', exact=True)).to_be_visible()
                expect(locator.page.get_by_role('button', name=f'Remove {name}', exact=True)).to_be_visible()
                expect(locator.page.get_by_test_id('stChatInputSubmitButton')).to_be_enabled()
            finally:
                cdp.detach()
        return
    locator.evaluate('''(e, o) => {
        const data = new DataTransfer();
        data.items.add(new File([new Uint8Array(o.content ?? o.size)], o.name, {type:o.mime}));
        if (o.event === 'change') {
            e.files = data.files; e.dispatchEvent(new Event('change', {bubbles:true}));
        } else if (o.event === 'paste') {
            e.focus(); e.dispatchEvent(new ClipboardEvent('paste', {
                clipboardData:data, bubbles:true, cancelable:true}));
        }
    }''', dict(name=name, size=size, content=content, mime=mime, event=event))


def upload_status(upload, *, length=None, xsrf=True):
    address = urlsplit(upload['url'])
    assert address.hostname == '127.0.0.1'
    headers = {k: v for k, v in upload['headers'].items()
               if k not in ('content-length', 'connection')}
    if not xsrf:
        headers = {k: v for k, v in headers.items() if 'xsrf' not in k and k != 'cookie'}
    headers['Content-Length'] = str(length or 0)
    # Oversized length is rejected before body consumption. No large wire buffer.
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=10)
    try:
        connection.request('PUT', address.path, headers=headers)
        response = connection.getresponse()
        status = response.status
        response.read()
        return status
    finally:
        connection.close()


def main():
    TOKENIZER_METADATA.update(json.loads(Path(os.environ['TOKENIZER_TEST_METADATA']).read_text()))
    server = ThreadingHTTPServer(('127.0.0.1', 0), UpgradeBoundary)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    env = dict(os.environ, LLM_BASE_URL=endpoint + '/v1', TIKA_URL=endpoint,
               RELEASE_URL=endpoint + '/released', PYTHONPATH=str(Path.cwd()))
    processes = []
    try:
        processes.append(start_app('ephemeral_app.py', 18505, env))
        with tempfile.TemporaryDirectory() as temp:
            probe = Path(temp) / 'release_probe.py'
            probe.write_text('''import io, os, requests
import streamlit as st
from ephemeral.privacy import ConversationPayloads, ConversationMessages
def release(resource):
    owner, messages, upload = resource
    owner.release()
    messages.append({'content':'Late synthetic response'})
    requests.post(os.environ['RELEASE_URL'], json={
        'released':owner.released, 'empty':not messages, 'closed':upload.closed,
        'detached':not owner._owned}, timeout=3)
@st.cache_resource(scope='session', on_release=release, show_spinner=False)
def resource():
    owner=ConversationPayloads()
    return owner, ConversationMessages(owner,[{'content':'Synthetic'}]), owner.own(io.BytesIO(b'Synthetic'))
resource()
st.caption('Release probe ready')
''')
            processes.append(start_app(probe, 18506, env))
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                uploads = []
                def observe(request):
                    if request.method == 'PUT' and '/upload_file/' in request.url:
                        uploads.append({'url': request.url, 'headers': request.all_headers()})
                page.on('request', observe)
                page.goto('http://127.0.0.1:18505')
                wait_idle(page)
                for size in (50 * 1024 * 1024 - 1, 50 * 1024 * 1024):
                    with page.expect_response(lambda r: '/upload_file/' in r.url
                                              and r.request.method == 'PUT', timeout=60_000) as sent:
                        add_file(page.locator('input[type=file]'), 'boundary.txt', size=size)
                    assert sent.value.ok, f'Upload status {sent.value.status}'
                    remove = page.get_by_role('button', name='Remove boundary.txt', exact=True)
                    expect(remove).to_be_visible(timeout=30_000)
                    expect(page.get_by_test_id('stChatInputSubmitButton')).to_be_enabled(timeout=30_000)
                    remove.click()
                    expect(remove).to_have_count(0)
                assert len(uploads) == 2
                with page.expect_response(lambda r: '/upload_file/' in r.url
                                          and r.request.method == 'PUT', timeout=60_000) as sent:
                    add_file(page.locator('input[type=file]'), 'too-large.txt', size=50 * 1024 * 1024 + 1)
                assert sent.value.ok
                submit(page, '')
                expect(page.locator('.attachment-meta')).to_contain_text('exceeds the per-file upload limit')
                wait_idle(page)
                assert STATE['reads'] == STATE['calls'] == 0
                reset(page)
                # Integer-only widget uses a rounded decimal allowance; exact
                # 50 MiB remains enforced by Python before parsing/inference.
                add_file(page.locator('input[type=file]'), 'widget-large.txt', size=53_000_001)
                expect(page.get_by_text(re.compile(r'53.*MB.*smaller'))).to_be_visible(timeout=10_000)
                assert len(uploads) == 3, 'Widget dispatched an oversized file'
                assert upload_status(uploads[-1], length=51 * 1024 * 1024 + 1) == 413
                assert upload_status(uploads[-1], xsrf=False) == 403
                # allowedHosts protects WebSocket admission, not static HTTP GETs.
                response = requests.get('http://127.0.0.1:18505/_stcore/stream', headers={
                    'Host':'invalid.example', 'Origin':'http://localhost:18505',
                    'Upgrade':'websocket', 'Connection':'Upgrade',
                    'Sec-WebSocket-Version':'13',
                    'Sec-WebSocket-Key':'YWJjZGVmZ2hpamtsbW5vcA=='}, timeout=5)
                assert response.status_code == 403
                reset(page)
                print('PASS exact 50 MiB uploads, widget/server over-limit rejection, XSRF and Host checks', flush=True)

                for event, name, mime, data in (
                    ('paste', 'pasted.txt', 'text/plain', list(b'Fictional pasted document')),
                    ('drop', 'dropped.txt', 'text/plain', list(b'Fictional dropped document')),
                ):
                    target = page.get_by_test_id('stChatInputTextArea' if event == 'paste' else 'stChatInput')
                    add_file(target, name, content=data, mime=mime, event=event)
                    expect(page.get_by_role('button', name=f'Remove {name}', exact=True)).to_be_visible()
                    submit(page, 'Synthetic attachment check')
                    expect(page.get_by_text('Synthetic boundary answer.', exact=True)).to_be_visible(timeout=20_000)
                    wait_idle(page)
                    expect(page.locator('.attachment-meta')).to_contain_text('partial')
                    reset(page)
                raw = io.BytesIO()
                Image.new('RGB', (12, 12), 'blue').save(raw, format='PNG')
                add_file(page.get_by_test_id('stChatInputTextArea'), 'pasted.png',
                         content=list(raw.getvalue()), mime='image/png', event='paste')
                expect(page.get_by_role('button', name='Remove pasted.png', exact=True)).to_be_visible()
                submit(page, 'Synthetic image check')
                expect(page.get_by_text('Synthetic boundary answer.', exact=True)).to_be_visible(timeout=20_000)
                wait_idle(page)
                image = page.locator('[class*="st-key-user-"] img').last
                expect(image).to_be_visible()
                assert image.evaluate('e=>e.complete && e.naturalWidth>0')
                print('PASS native file/image paste and drag/drop through application processing', flush=True)
                context.close()
                assert upload_status(uploads[-1]) == 400

                lifecycle = browser.new_context()
                probe_page = lifecycle.new_page()
                probe_page.goto('http://127.0.0.1:18506')
                expect(probe_page.get_by_text('Release probe ready', exact=True)).to_be_visible()
                assert not RELEASED.is_set()
                lifecycle.close()
                assert RELEASED.wait(10), 'Real WebSocket disconnect did not release the resource'
                assert RELEASE_RESULT == dict(released=True, empty=True, closed=True, detached=True)
                print('PASS real disconnect closes owned buffers, clears messages and rejects late state', flush=True)
                browser.close()
    finally:
        for process in processes:
            process.terminate()
            with contextlib.suppress(Exception):
                process.wait(timeout=10)
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
