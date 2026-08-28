import pytest

from jobmatch.cv_parser import CVParseError, extract_cv_text


def test_txt_cv_is_read():
    content = (
        "Electrical engineer with battery management, MATLAB and Simulink experience. "
        "Worked on model-based development, testing, validation, diagnostics, and data analysis."
    ).encode()
    assert "Electrical engineer" in extract_cv_text("cv.txt", content)


def test_unsupported_type_is_rejected():
    with pytest.raises(CVParseError, match="PDF, DOCX, or TXT"):
        extract_cv_text("cv.png", b"not a cv")
