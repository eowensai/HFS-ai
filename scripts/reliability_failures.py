#!/usr/bin/env python3
"""Controlled real-browser failures at an isolated app's HTTP boundary.

Starts only local test processes. No shared-service requests, stored content,
traces or content-bearing screenshots. Requires test dependencies/Chromium.
"""
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ephemeral import config as cfg

STATE = {'mode': 'success', 'calls': 0, 'last': None, 'reads': 0}
DETAILS = {'family': cfg.PINNED_LLM_MODEL_FAMILY,
           'parameter_size': cfg.PINNED_LLM_MODEL_PARAMETER_SIZE,
           'quantization_level': cfg.PINNED_LLM_MODEL_QUANTIZATION}


class Boundary(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, value, kind='application/json'):
        raw = json.dumps(value).encode() if kind == 'application/json' else value
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/api/tags':
            self.send(200, {'models': [{'name': cfg.LLM_MODEL_NAME,
                                      'digest': cfg.PINNED_LLM_MODEL_DIGEST, 'details': DETAILS}]})
        elif self.path == '/api/ps':
            if STATE['mode'] == 'metadata_missing':
                self.send(503, {})
            else:
                self.send(200, {'models': [{'name': cfg.LLM_MODEL_NAME,
                    'digest': cfg.PINNED_LLM_MODEL_DIGEST,
                    'context_length': 65536 if STATE['mode'] == 'mismatch' else 131072}]})
        else:
            self.send(200, b'synthetic parser', 'text/plain')

    def do_PUT(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        STATE['reads'] += 1
        if STATE['mode'] == 'slow_parser':
            time.sleep(2)
        if data == b'bad':
            self.send(200, {'X-TIKA:content': ''})
        elif STATE['mode'] == 'failed_parser':
            self.send(500, b'controlled failure', 'text/plain')
        else:
            self.send(200, {'X-TIKA:content': 'Fictional parsed code 731.', 'X-TIKA:EXCEPTION:write_limit_reached': 'true'})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/api/show':
            self.send(200, {'parameters': 'num_ctx 131072\nnum_predict 32768',
                            'details': DETAILS, 'capabilities': ['completion', 'thinking', 'vision']})
            return
        STATE['calls'] += 1
        STATE['last'] = body
        mode = STATE['mode']
        if mode == 'busy':
            self.send(503, {'error': {'message': 'synthetic busy', 'type': 'server_error'}})
            return
        if mode in {'pending', 'timeout'}:
            time.sleep(4)
        def event(text, reason=None):
            return ('data: ' + json.dumps({'id': 'synthetic', 'object': 'chat.completion.chunk',
                'created': 0, 'model': cfg.LLM_MODEL_NAME,
                'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': reason}]}) + '\n\n').encode()
        self.send(200, event('Synthetic boundary answer.', None if mode == 'interrupted' else 'stop') + b'data: [DONE]\n\n', 'text/event-stream')


def wait_idle(page):
    expect(page.get_by_test_id('stChatInputTextArea')).to_be_enabled(timeout=20_000)


def submit(page, text='Synthetic question', files=None):
    wait_idle(page)
    if files:
        page.locator('input[type=file]').set_input_files(files)
        for f in files:
            expect(page.get_by_text(f['name'], exact=True).first).to_be_visible()
    page.get_by_test_id('stChatInputTextArea').fill(text)
    page.get_by_test_id('stChatInputSubmitButton').click()


def reset(page):
    page.get_by_role('button', name='New Chat', exact=True).click()
    expect(page.locator('section.welcome-shell')).to_be_visible(timeout=10_000)
    wait_idle(page)


def fixture(name, content=b'ok'):
    return {'name': name, 'mimeType': 'text/plain', 'buffer': content}


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Boundary)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    env = dict(os.environ, LLM_BASE_URL=endpoint + '/v1', TIKA_URL=endpoint,
               LLM_SUPPORTS_VISION='false', TIKA_TIMEOUT_S='1', LLM_REQUEST_TIMEOUT_S='3',
               MAX_UPLOAD_COUNT='2', MAX_UPLOAD_TOTAL_BYTES='30', MAX_EXTRACTED_BYTES='12')
    proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'ephemeral_app.py',
                             '--server.port=18502', '--server.address=127.0.0.1'],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import requests
        for _ in range(100):
            try:
                if requests.get('http://127.0.0.1:18502/_stcore/health', timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            a = context.new_page(); a.goto('http://127.0.0.1:18502')
            for mode in ['busy', 'interrupted', 'timeout']:
                STATE['mode'] = mode
                before = STATE['calls']
                submit(a)
                expect(a.get_by_role('button', name='Retry response')).to_be_visible(timeout=15_000)
                assert STATE['calls'] == before + 1
                assert not a.locator('[class*="st-key-assistant-"]').count() or mode == 'interrupted'
                STATE['mode'] = 'success'
                a.get_by_role('button', name='Retry response').click()
                expect(a.get_by_text('Synthetic boundary answer.', exact=True)).to_be_visible(timeout=15_000)
                wait_idle(a)
                assert STATE['calls'] == before + 2
                assert len([m for m in STATE['last']['messages'] if m['role'] == 'user']) == 1
                assert all(m['role'] != 'assistant' for m in STATE['last']['messages'])
                reset(a)
                print(f'PASS browser {mode}, explicit retry, no duplicate user turn', flush=True)
            for mode in ['slow_parser', 'failed_parser']:
                STATE['mode'] = mode
                before = STATE['calls']
                submit(a, '', [fixture('synthetic.txt')])
                expect(a.get_by_text('No attachment content was available', exact=False)).to_be_visible(timeout=15_000)
                assert STATE['calls'] == before
                assert 'unavailable' in a.locator('.attachment-meta').inner_text()
                if mode == 'slow_parser':
                    assert 'timed out' in a.locator('.attachment-meta').inner_text()
                reset(a)
                print(f'PASS browser {mode}, all-failed prevents automatic inference', flush=True)
            STATE['mode'] = 'success'
            submit(a, 'Read these', [fixture('same.txt'), fixture('same.txt', b'bad')])
            expect(a.get_by_text('Synthetic boundary answer.', exact=True)).to_be_visible(timeout=15_000)
            wait_idle(a)
            receipts = a.locator('.attachment-meta').all_text_contents()
            assert len(receipts) == 2 and 'partial' in receipts[0] and 'unavailable' in receipts[1]
            submit(a, 'What was unavailable?')
            expect(a.locator('[class*="st-key-assistant-"]')).to_have_count(2, timeout=15_000)
            wait_idle(a)
            assert 'unavailable' in str(STATE['last']['messages'])
            reset(a)
            print('PASS browser mixed/same-name/partial and follow-up statuses', flush=True)
            before = STATE['reads']
            submit(a, '', [fixture('one.txt'), fixture('two.txt'), fixture('three.txt')])
            expect(a.get_by_text('No attachment content was available', exact=False)).to_be_visible(timeout=15_000)
            assert STATE['reads'] == before
            reset(a)
            print('PASS browser aggregate upload rejection before parser calls', flush=True)
            for mode in ['mismatch', 'metadata_missing']:
                STATE['mode'] = mode
                before = STATE['calls']
                submit(a)
                expect(a.get_by_test_id('stAlert').filter(has_text='Request not sent')).to_be_visible(timeout=15_000)
                wait_idle(a)
                assert STATE['calls'] == before
                reset(a)
                print(f'PASS browser {mode} prevents inference', flush=True)
            STATE['mode'] = 'pending'
            submit(a)
            expect(a.get_by_test_id('stAlert').filter(has_text='Waiting for model response')).to_be_visible(timeout=10_000)
            a.get_by_role('button', name='New Chat', exact=True).click()
            expect(a.locator('section.welcome-shell')).to_be_visible(timeout=10_000)
            wait_idle(a)
            assert a.locator('[class*="st-key-assistant-"]').count() == 0
            STATE['mode'] = 'success'
            submit(a, 'Fresh synthetic conversation')
            expect(a.get_by_text('Synthetic boundary answer.', exact=True)).to_be_visible(timeout=15_000)
            assert len(STATE['last']['messages']) == 2
            print('PASS browser New Chat while pending; stale reply excluded', flush=True)
            context.close(); browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=5)
        server.shutdown(); server.server_close()
        STATE['last'] = None


if __name__ == '__main__':
    main()
