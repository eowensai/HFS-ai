"""Bounded attachment preparation. Names and extracted text are always data."""
import base64
import io
import json
import uuid
import warnings

from PIL import Image, ImageOps

from ephemeral import config as cfg


def attachment_record(upload):
    return {
        'id': uuid.uuid4().hex,
        'name': str(getattr(upload, 'name', 'Attachment'))[:240],
        'size': int(getattr(upload, 'size', 0) or 0),
        'kind': 'image' if getattr(upload, 'type', '').startswith('image/') else 'document',
        'status': 'unavailable',
        'reason': 'Not read.',
    }


def status_part(record):
    return {'type': 'text', 'text': json.dumps({'attachment_status': record}, ensure_ascii=True),
            '_attachment': record}


def exclude_content(parts, reason):
    """Keep precise receipts, discard every content/image buffer by identity."""
    result = []
    for part in parts:
        if '_attachment' in part:
            record = dict(part['_attachment'], status='unavailable', reason=reason)
            record.pop('characters', None)
            result.append(status_part(record))
    return result


def available_count(parts):
    return sum(p.get('_attachment', {}).get('status') in {'available', 'partial'} for p in parts)


def batch_rejection(files):
    # Inspect metadata before any seek/read, parse, base64 encoding or image decode.
    if len(files) > cfg.MAX_UPLOAD_COUNT:
        return f'Upload count exceeds the limit of {cfg.MAX_UPLOAD_COUNT}. No files were read.'
    if sum(max(0, int(getattr(f, 'size', 0) or 0)) for f in files) > cfg.MAX_UPLOAD_TOTAL_BYTES:
        return f'Combined uploads exceed {cfg.MAX_UPLOAD_TOTAL_BYTES // (1024 * 1024)} MiB. No files were read.'
    return None


def normalize_image(data):
    """Header limits precede pixel decode; retain only a bounded JPEG rendition."""
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as source:
            w, h = source.size
            if w * h > cfg.MAX_IMAGE_PIXELS or max(w, h) > cfg.MAX_IMAGE_EDGE:
                raise ValueError('Image dimensions exceed the decoding limit.')
            # Pillow handles formats such as PSD that Ollama does not accept directly.
            # Only the first frame is used; explicitly report this as partial content.
            partial = getattr(source, 'n_frames', 1) > 1
            source.thumbnail((min(1024, cfg.MAX_IMAGE_OUTPUT_EDGE), min(1024, cfg.MAX_IMAGE_OUTPUT_EDGE)))
            image = ImageOps.exif_transpose(source).convert('RGB')
            try:
                with io.BytesIO() as out:
                    image.save(out, format='JPEG', quality=85)
                    if out.tell() > cfg.MAX_IMAGE_OUTPUT_BYTES:
                        raise ValueError('Prepared image exceeds the image buffer limit.')
                    encoded = base64.b64encode(out.getvalue()).decode('ascii')
            finally:
                image.close()
    return 'data:image/jpeg;base64,' + encoded, partial, max(w, h) > min(1024, cfg.MAX_IMAGE_OUTPUT_EDGE)


def prepare_attachments(files, parse, vision, progress=lambda _: None, cancelled=lambda: False):
    """Return status receipts and contents; close originals even after rejection."""
    parts = []
    remaining = cfg.MAX_EXTRACTED_TOTAL_BYTES
    rejected = batch_rejection(files)
    try:
        # Count rejection gets one aggregate receipt: bounded even for thousands of files.
        if len(files) > cfg.MAX_UPLOAD_COUNT:
            record = {'id': uuid.uuid4().hex, 'name': 'Upload batch', 'size': 0,
                      'kind': 'document', 'status': 'unavailable', 'reason': rejected}
            return [status_part(record)]
        total = len(files)
        for ordinal, upload in enumerate(files, 1):
            if cancelled():
                break
            record = attachment_record(upload)
            content = None
            try:
                if rejected:
                    record['reason'] = rejected
                elif record['size'] <= 0 or record['size'] > cfg.MAX_UPLOAD_BYTES:
                    record['reason'] = 'Empty file or file exceeds the per-file upload limit.'
                elif record['kind'] == 'image' and not vision:
                    record['reason'] = 'Image input is unsupported or could not be verified.'
                elif record['kind'] == 'document' and remaining <= 0:
                    record['reason'] = 'Excluded: aggregate extracted-text limit reached.'
                else:
                    progress(f'Reading file {ordinal} of {total}…')
                    upload.seek(0)
                    # Bounded read also defends against misleading size metadata.
                    data = upload.read(min(record['size'], cfg.MAX_UPLOAD_BYTES) + 1)
                    if len(data) != record['size']:
                        raise ValueError('File size changed or could not be verified.')
                    try:
                        if record['kind'] == 'image':
                            url, partial, resized = normalize_image(data)
                            record.update(status='partial' if partial or resized else 'available',
                                          reason=('First frame only. ' if partial else '') +
                                          ('Image resized to the configured preview size.' if resized else 'Image available.'))
                            content = {'type': 'image_url', 'image_url': {'url': url},
                                       '_attachment_id': record['id']}
                        else:
                            result = parse(data, record['name'], max_bytes=min(cfg.MAX_EXTRACTED_BYTES, remaining))
                            text = result.text
                            remaining -= len(text.encode('utf-8'))
                            if text:
                                record.update(status='partial' if result.partial else 'available',
                                              reason='Partial extracted text only; the remainder or unreadable sections were excluded.' if result.partial
                                              else 'All extracted text available; extraction may not preserve layout or non-text elements.',
                                              characters=len(text))
                                content = {'type': 'text', '_synthetic': True, '_attachment_content': record['id'],
                                           'text': json.dumps({'attachment_content': {'id': record['id'], 'text': text}}, ensure_ascii=True)}
                            else:
                                record['reason'] = 'No readable text was extracted.'
                    finally:
                        data = None
            except TimeoutError:
                record['reason'] = 'Document reading timed out. Upload again to retry.'
            except Exception:  # noqa: BLE001 - parser/decoder errors must not expose content
                # Never surface backend exception strings or document-bearing diagnostics.
                record['reason'] = 'File could not be read or decoded. Upload again or use a different format.'
            finally:
                upload.close()
            parts.append(status_part(record))
            if content:
                parts.append(content)
        return parts
    finally:
        for upload in files:
            upload.close()
        files.clear()


def api_messages(messages, vision=True):
    """Serialize exactly what is budgeted and sent; unavailable contents never revive."""
    output = []
    for message in messages:
        if message.get('status', 'complete') != 'complete':
            continue  # Pending/failed assistant output is never model history.
        content = message['content']
        if isinstance(content, list):
            parts = []
            for part in content:
                if part['type'] == 'image_url':
                    if vision:
                        parts.append({'type': 'image_url', 'image_url': part['image_url']})
                elif part['type'] == 'text':
                    record = part.get('_attachment')
                    if record and record['kind'] == 'image' and not vision:
                        record = dict(record, status='unavailable', reason='Image omitted from this request: vision unavailable.')
                        parts.append({'type': 'text', 'text': status_part(record)['text']})
                    else:
                        parts.append({'type': 'text', 'text': part['text']})
            content = ('\n\n'.join(p['text'] for p in parts)
                       if all(p['type'] == 'text' for p in parts) else parts)
        output.append({'role': message['role'], 'content': content})
    return output


def retained_bytes(value):
    """Count payload bytes recursively without serializing a duplicate conversation."""
    if isinstance(value, str):
        return len(value.encode('utf-8'))
    if isinstance(value, bytes):
        return len(value)
    if isinstance(value, dict):
        return sum(retained_bytes(k) + retained_bytes(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return sum(retained_bytes(v) for v in value)
    return 16
