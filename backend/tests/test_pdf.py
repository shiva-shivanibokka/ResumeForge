import pytest

from app.services.pdf import count_pdf_pages, docx_to_pdf, soffice_available


def _make_docx(path: str) -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("ResumeForge PDF conversion test.")
    doc.save(path)


def test_soffice_available_returns_bool():
    assert isinstance(soffice_available(), bool)


def test_docx_to_pdf_missing_source_raises(tmp_path):
    # Independent of LibreOffice availability: a missing source must error clearly.
    if soffice_available():
        with pytest.raises(RuntimeError):
            docx_to_pdf(str(tmp_path / "nope.docx"))
    else:
        with pytest.raises(RuntimeError):
            docx_to_pdf(str(tmp_path / "nope.docx"))


@pytest.mark.skipif(not soffice_available(), reason="LibreOffice not installed")
def test_docx_to_pdf_roundtrip(tmp_path):
    docx = tmp_path / "sample.docx"
    _make_docx(str(docx))
    pdf = docx_to_pdf(str(docx), out_dir=str(tmp_path))
    assert pdf.endswith(".pdf")
    assert count_pdf_pages(pdf) == 1
