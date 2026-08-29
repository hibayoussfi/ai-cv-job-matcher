import pytest

from jobmatch.cv_parser import (
    MAX_CV_BYTES,
    CVParseError,
    anonymize_cv_text,
    extract_cv_text,
)


def test_txt_cv_is_read():
    content = (
        "Electrical engineer with battery management, MATLAB and Simulink experience. "
        "Worked on model-based development, testing, validation, diagnostics, and data analysis."
    ).encode()
    assert "Electrical engineer" in extract_cv_text("cv.txt", content)


def test_unsupported_type_is_rejected():
    with pytest.raises(CVParseError, match="PDF, DOCX, or TXT"):
        extract_cv_text("cv.png", b"not a cv")


def test_oversized_cv_is_rejected():
    with pytest.raises(CVParseError, match="5 MB"):
        extract_cv_text("cv.txt", b"a" * (MAX_CV_BYTES + 1))


def test_personal_identifiers_are_redacted():
    text = (
        "Test Candidate candidate@example.test +1 555 010 9999 "
        "https://example.test/profile"
    )
    redacted = anonymize_cv_text(text, names=("Test", "Candidate"))
    assert "candidate@example.test" not in redacted
    assert "+1 555 010 9999" not in redacted
    assert "example.test/profile" not in redacted
    assert "Candidate" not in redacted
