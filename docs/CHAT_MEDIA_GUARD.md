# Chat media rendering guard

The inherited chat rendering path allowed user/assistant Markdown images to reach
Streamlit 1.56 unchanged. Its Markdown renderer creates browser image elements
with supplied addresses even when raw HTML is disabled. A local model therefore
does not by itself prevent browser requests containing message-derived URLs.
This is a confirmed rendering behavior, not evidence that a private conversation
leaked or that a malicious document successfully influenced the installed model.

## Local correction

`ephemeral/chat_display.py` supplies one display-only guard used for ordinary and
multipart messages, the pending submitted prompt, and partial streaming answers.
Text containing `![` is rendered literally with native `st.text`; other text keeps
Markdown with `unsafe_allow_html=False` explicitly set. The conservative trigger
also includes escaped/code examples and incomplete image syntax. Whole-message
literal rendering preserves the exact source without attempting to parse or
rewrite Markdown with regular expressions. Such messages lose Markdown styling
in the displayed bubble; no image is fetched and no message text is dropped.

The `:help[` directive also renders literally because Streamlit can pass its
decoded text into another Markdown renderer in a tooltip. HTML attachment labels
escape image openers and directive colons as well as HTML, including names whose
blank lines could terminate a Markdown HTML block. Existing fixed app HTML and
theme assets remain unchanged.

Upload previews accept only bounded in-memory bytes or decoded JPEG/PNG data URLs.
URLs and filesystem paths are never passed to `st.image`. Normal prepared upload
previews still work. This does not add an external image proxy, network allowlist,
CSS hiding, post-render DOM cleanup, content logging or a production dependency.

Retained messages, actual model requests, token admission and copy/export source
are unchanged. Rich clipboard HTML already escapes message content and does not
create image elements. Plain Markdown copy remains the original source; another
application may render that source differently. Ordinary links remain clickable:
explicit navigation is outside the no-automatic-media boundary.

## Verification

`tests/test_chat_display.py` covers literal image/reference/code syntax, incomplete
stream prefixes, raw HTML disabled on normal Markdown, labels, bounded upload data,
URL/path rejection, original copy content and production rendering calls.

Run `TOKENIZER_TEST_METADATA=PATH python scripts/verify_chat_media.py` in the
existing isolated browser-test environment. PATH is the public tokenizer metadata
fixture described in [TOKEN_COUNTING.md](TOKEN_COUNTING.md), not chat content.
The runner starts only local synthetic services. A positive-control renderer must
request a local canary image. Guarded cases then cover image/reference syntax,
relative/protocol-relative URLs, escaped/entities, HTML/SVG/audio/video, math,
code, tables and tooltip directives. Outside requests are intercepted and never
sent to an external server. The real app's user/stream/final/copy paths are checked,
as are narrow rendering and ordinary formatting/click-triggered navigation.
Only pass results/counts are retained; no traces or content screenshots are saved.

The existing real-backend runner additionally verifies uploaded image display,
Tika/OCR/model answers, copy/export, Thinking Mode, long-document follow-up and
session isolation. This is targeted privacy regression testing, not a general
browser security certification or a workstation traffic-history investigation.

Source reference: [pinned Streamlit Markdown renderer](https://github.com/streamlit/streamlit/blob/1.56.0/frontend/lib/src/components/shared/StreamlitMarkdown/StreamlitMarkdown.tsx).
