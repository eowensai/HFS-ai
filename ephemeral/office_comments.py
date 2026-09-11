"""Recover Word comment attribution omitted by Tika 4's supported SAX parser."""
import io
import zipfile
import xml.etree.ElementTree as ET


COMMENT_XML_LIMIT = 1024 * 1024
WORD_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class _NoDoctypeTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        # Parser-level rejection also covers UTF-16/UTF-32 declarations.
        raise ValueError('Document type declarations are not supported')


def word_comment_attribution(data: bytes) -> tuple[str, bool]:
    """Return a labeled attribution appendix, keeping XML and ZIP data in RAM.

    Tika still owns document extraction. This narrowly reads the standard DOCX
    comment part; it does not replace text in the body, where identical words
    could belong to someone else. Unreadable/oversized comments mark the result
    partial rather than losing the otherwise useful Tika extraction.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                info = archive.getinfo('word/comments.xml')
            except KeyError:
                return '', False
            if info.file_size > COMMENT_XML_LIMIT:
                return '', True
            with archive.open(info) as part:
                xml = part.read(COMMENT_XML_LIMIT + 1)
            if len(xml) > COMMENT_XML_LIMIT or b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                return '', True
            root = ET.fromstring(xml, parser=ET.XMLParser(target=_NoDoctypeTreeBuilder()))
            comments = []
            for comment in root.findall(WORD_NS + 'comment'):
                author = comment.get(WORD_NS + 'author', '').strip() or 'Unknown author'
                pieces = []
                # Visit each node once, even in malformed nested paragraphs.
                for node in comment.iter():
                    if node.tag == WORD_NS + 'p' and pieces:
                        pieces.append('\n')
                    elif node.tag == WORD_NS + 't':
                        pieces.append(node.text or '')
                body = ''.join(pieces).strip()
                if body:
                    # Quoting keeps source comments separate from the document narrative.
                    label = 'Comment by ' + ' '.join(author.split()) + ': ' + body
                    comments.append('\n'.join('> ' + line for line in label.splitlines()))
            if not comments:
                return '', False
            return '\n\n## Word comment attribution\n\n' + '\n\n'.join(comments), False
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError, ET.ParseError, NotImplementedError):
        return '', True
