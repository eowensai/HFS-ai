import io
import zipfile

from ephemeral.office_comments import COMMENT_XML_LIMIT, word_comment_attribution


def docx(xml, name='word/comments.xml'):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, xml)
    return output.getvalue()


def test_authors_stay_associated_with_their_own_multiline_comments():
    xml = '''<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:comment w:author="Reviewer One"><w:p><w:r><w:t>Shared </w:t></w:r>
      <w:r><w:t>words</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:comment>
      <w:comment w:author="Reviewer Two"><w:p><w:r><w:t>Shared words</w:t></w:r></w:p></w:comment>
    </w:comments>'''
    text, partial = word_comment_attribution(docx(xml))
    assert not partial
    assert '> Comment by Reviewer One: Shared words\n> Second paragraph' in text
    assert '> Comment by Reviewer Two: Shared words' in text


def test_missing_comments_are_normal():
    assert word_comment_attribution(docx('<document/>', 'word/document.xml')) == ('', False)


def test_malformed_nested_paragraphs_do_not_multiply_content():
    xml = ('<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:comment w:author="Mira">' + '<w:p>' * 2000 +
           '<w:t>Single occurrence</w:t>' + '</w:p>' * 2000 + '</w:comment></w:comments>')
    text, partial = word_comment_attribution(docx(xml))
    assert not partial and text.count('Single occurrence') == 1 and len(text) < 100


def test_oversized_compressed_comment_part_is_not_inflated():
    assert word_comment_attribution(docx('x' * (COMMENT_XML_LIMIT + 1))) == ('', True)


def test_unreadable_and_entity_documents_mark_partial():
    for data in [b'bad zip', docx('<unclosed>'), docx('<!DOCTYPE x><x/>'),
                 docx('<!ENTITY x "expanded"><x/>'),
                 docx('<!DOCTYPE x [<!ENTITY y "expanded">]><x>&y;</x>'.encode('utf-16'))]:
        assert word_comment_attribution(data) == ('', True)
