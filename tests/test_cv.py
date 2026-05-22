"""Tests for jobhunt.cv.

The sentence-transformers dependency is optional. Embedding tests are skipped
gracefully when it isn't installed, so this suite still passes on a slim setup.
"""

from __future__ import annotations

import pytest

from jobhunt.cv import cosine, parse_cv


def _minimal_pdf(text: str) -> bytes:
    """Build a tiny valid PDF byte string with a single line of extractable text.

    Hand-rolled because pypdf's PdfWriter can clone/manipulate pages but doesn't
    have a high-level "draw text" API. A real reportlab/fpdf dep would be
    overkill for one test fixture.
    """
    content = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode("ascii")
    content_obj = (
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        content_obj,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode("ascii")
    return bytes(out)


def test_parse_cv_pdf():
    pdf_bytes = _minimal_pdf("Senior Python Engineer")
    text = parse_cv("resume.pdf", pdf_bytes)
    assert "Python" in text
    assert "Engineer" in text


def test_parse_cv_txt():
    text = parse_cv("resume.txt", b"Hello CV from a text file.")
    assert "Hello CV" in text


def test_parse_cv_unsupported_extension():
    with pytest.raises(ValueError):
        parse_cv("resume.rtf", b"whatever")


def test_cosine_identical_vectors():
    v = [0.1, 0.2, 0.3, 0.4]
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-9)


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine(a, b) == pytest.approx(0.0, abs=1e-9)


def test_cosine_empty_or_zero():
    assert cosine([], [1.0, 2.0]) == 0.0
    assert cosine([0.0, 0.0, 0.0], [1.0, 2.0, 3.0]) == 0.0


def test_cosine_mismatched_lengths_safe():
    # Defensive: shouldn't blow up on accidental mismatch.
    assert cosine([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_embed_text_when_available():
    pytest.importorskip("sentence_transformers")
    from jobhunt.cv import embed_text

    vec, model = embed_text("python developer with fastapi experience")
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(x, float) for x in vec)
    assert model == "all-MiniLM-L6-v2"
