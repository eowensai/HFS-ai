"""Real Chromium request canaries against pinned Streamlit and the app lifecycle.

All references and responses are synthetic. No outside server is contacted;
external routes are intercepted and a local canary proves request detection.
Only counts/pass results are printed. No traces or content screenshots.
"""
import base64
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reliability_failures import (
    STATE,
    TOKENIZER_METADATA,
    Boundary,
    ThreadingHTTPServer,
    reset,
    submit,
    wait_idle,
)

RELEASE = threading.Event()
CANARY_HITS = []
ANSWER = ''


def examples(url):
    return [
        f'![inline]({url})', f'![angle](<{url}> "title")',
        f'![ref][key]\n\n[key]: {url}', f'![key][]\n\n[key]: {url}',
        f'![key]\n\n[key]: {url}', f'[![nested]({url})]({url})',
        f'\\![escaped]({url})', f'\\\\![active]({url})',
        f'![multi\nline]({url})', f'![![nested]({url})]({url})',
        '![relative](/canary/relative.png)', '![protocol-relative](//media.example.invalid/canary/p.png)',
        '![data](data:image/svg+xml;base64,PHN2Zy8+)', '![blob](blob:synthetic)',
        f'&#33;[entity]({url})', f'!&#91;entity]({url})', f'!\\\n[break]({url})',
        f':help[&#33;&#91;encoded&#93;&#40;{url}&#41;]',
        f':help[!\\[escaped]({url})]',
        f'<img src="{url}" srcset="{url} 2x">',
        f'<picture><source srcset="{url}"><img src="{url}"></picture>',
        f'<video poster="{url}" src="{url}" autoplay></video>',
        f'<audio src="{url}" autoplay></audio><iframe src="{url}"></iframe>',
        f'<style>body{{background-image:url({url})}}</style>',
        f'<svg><image href="{url}"/></svg>',
        f'$\\includegraphics{{{url}}}$',
        f'``![inline code]({url})``', f'```md\n![fenced]({url})\n```',
        f'    ![indented]({url})', f'> - ![list]({url})',
        f'| Cell |\n| --- |\n| ![table]({url}) |',
        '**Bold** and *italic* [manual link](https://media.example.invalid/manual).',
        '```mermaid\ngraph LR\nA-->B\n```',
        f'```mermaid\ngraph LR\nA["<img src=\'{url}\'>"]\n```',
        '> ~~~mermaid\ngraph LR\nA-->B',
        '```&#109;ermaid\ngraph LR\nA-->B\n```',
    ]


class MediaBoundary(Boundary):
    def do_GET(self):
        if self.path.startswith('/canary/'):
            CANARY_HITS.append(True)
            self.send(200, base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6cAAAAABJRU5ErkJggg=='), 'image/png')
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/show':
            return super().do_POST()
        STATE['last'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Connection', 'close')
        self.end_headers()
        def event(text, finish=None):
            return ('data: ' + json.dumps({'id': 'synthetic', 'object': 'chat.completion.chunk',
                'created': 0, 'model': STATE['last']['model'],
                'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': finish}]}) + '\n\n').encode()
        self.wfile.write(event(ANSWER + '\n' + 'Streaming filler. ' * 30))
        self.wfile.flush()
        RELEASE.wait(30)
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(event('\nCompleted.', 'stop') + b'data: [DONE]\n\n')
            self.wfile.flush()


def start_app(path, port, env):
    process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(path),
                                '--server.port=' + str(port), '--server.address=127.0.0.1'],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            if requests.get(f'http://127.0.0.1:{port}/_stcore/health', timeout=1).ok:
                return process
        except requests.RequestException:
            pass
        time.sleep(0.1)
    process.terminate()
    raise AssertionError('Test app did not start')


def main():
    global ANSWER
    TOKENIZER_METADATA.update(json.loads(Path(os.environ['TOKENIZER_TEST_METADATA']).read_text()))
    server = ThreadingHTTPServer(('127.0.0.1', 0), MediaBoundary)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    url = endpoint + '/canary/pixel.png?synthetic=731'
    corpus = examples(url)
    env = dict(os.environ, LLM_BASE_URL=endpoint + '/v1', TIKA_URL=endpoint,
               MEDIA_CANARY_URL=url, PYTHONPATH=str(Path.cwd()))
    processes = []
    try:
        with tempfile.TemporaryDirectory() as temp:
            # Fixture code only, not persisted generated output or operational content.
            fixture = Path(temp) / 'probe.py'
            fixture.write_text('''import os
import streamlit as st
from ephemeral.chat_display import render_chat_text, label_html
from scripts.verify_chat_media import examples
body = examples(os.environ['MEDIA_CANARY_URL'])[int(st.query_params.get('case', '0'))]
mode = st.query_params.get('mode', 'guarded')
if mode == 'control':
    st.markdown(body)
elif mode == 'label':
    st.markdown('<div>\\n\\n' + label_html(body) + '\\n\\n</div>', unsafe_allow_html=True)
else:
    render_chat_text(body, st)
st.caption('Probe ready')
''')
            processes.append(start_app(fixture, 18504, env))
            processes.append(start_app('ephemeral_app.py', 18503, env))
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                attempted = []
                def route(request):
                    address = urlsplit(request.request.url)
                    if address.hostname not in ('127.0.0.1', 'localhost'):
                        attempted.append(True)
                        request.abort()
                    elif address.path.startswith('/canary/'):
                        attempted.append(True)
                        if address.port == server.server_port:
                            request.continue_()
                        else:
                            request.fulfill(status=200, body=b'')
                    else:
                        request.continue_()
                context.route('**/*', route)
                page = context.new_page()
                page.goto('http://127.0.0.1:18504/?mode=control')
                expect(page.get_by_text('Probe ready', exact=True)).to_be_visible()
                for _ in range(40):
                    if CANARY_HITS:
                        break
                    page.wait_for_timeout(50)
                assert attempted and CANARY_HITS, 'Positive control failed to detect image request'
                print('PASS unguarded pinned Streamlit automatically requests the synthetic local canary', flush=True)
                attempted.clear()
                CANARY_HITS.clear()
                for mode in ('guarded', 'label'):
                    for index in range(len(corpus)):
                        page.goto(f'http://127.0.0.1:18504/?case={index}&mode={mode}')
                        expect(page.get_by_text('Probe ready', exact=True)).to_be_visible()
                        page.wait_for_timeout(100)
                        assert not attempted and not CANARY_HITS, f'Media request in {mode} case {index}'
                print(f'PASS {len(corpus)*2} guarded text/HTML-label renderer cases: zero media requests', flush=True)
                # The real app, SDK, output filter, polling fragment, final render and copy iframe.
                page.goto('http://127.0.0.1:18503')
                expect(page.locator('section.welcome-shell')).to_be_visible()
                ANSWER = '\n\n'.join(corpus)
                user_text = 'Synthetic user media reference: ![user](' + url + ')'
                submit(page, user_text)
                partial = page.locator('[class*="st-key-assistant-"] [data-testid="stText"]')
                expect(partial.filter(has_text='Streaming filler.')).to_be_visible(timeout=20_000)
                assert not attempted and not CANARY_HITS
                assert STATE['last']['messages'][-1]['content'] == user_text
                RELEASE.set()
                wait_idle(page)
                expect(page.get_by_text('Completed.', exact=False).first).to_be_visible()
                assert not attempted and not CANARY_HITS
                assert page.locator('[class*="st-key-user-"] img, [class*="st-key-assistant-"] img').count() == 0
                assert all(not frame.locator('img,video,audio,source').count() for frame in page.frames[1:])
                page.set_viewport_size({'width': 390, 'height': 844})
                box = page.get_by_test_id('stChatInputTextArea').bounding_box()
                assert box and box['x'] >= 0 and box['x'] + box['width'] <= 391
                print('PASS user, active stream, final answer, copy frames and mobile: zero media requests', flush=True)
                # Copy stays literal, including code/image examples; no display rewrite enters history.
                frame = next(f for f in page.frames if f.locator('#copy-btn').count())
                raw_copy = frame.locator('textarea').input_value()
                assert user_text in raw_copy and ANSWER in raw_copy
                print('PASS copy source preserved; no media elements in rich clipboard DOM', flush=True)
                page.set_viewport_size({'width': 1280, 'height': 900})
                reset(page)
                ANSWER = '**Ordinary formatting** with [manual link](https://media.example.invalid/manual).'
                submit(page, 'A normal text question')
                wait_idle(page)
                expect(page.locator('[class*="st-key-assistant-"] strong')).to_contain_text('Ordinary formatting')
                link = page.get_by_role('link', name='manual link', exact=True)
                expect(link).to_be_visible()
                assert not attempted
                with context.expect_page() as popup:
                    link.click()
                popup.value.wait_for_timeout(250)
                assert attempted, 'Explicit link click should attempt navigation'
                print('PASS ordinary formatting and links retained; navigation requires explicit click', flush=True)
                context.close()
                browser.close()
    finally:
        RELEASE.set()
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        STATE['last'] = None


if __name__ == '__main__':
    main()
