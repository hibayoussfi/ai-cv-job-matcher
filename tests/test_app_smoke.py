from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_professional_search_workspace_renders():
    app = AppTest.from_file(APP_PATH).run(timeout=20)

    assert not app.exception
    assert len(app.file_uploader) == 1
    assert [widget.label for widget in app.multiselect] == [
        "Preferred countries",
        "Preferred cities",
        "Work mode",
        "Seniority",
        "Job type",
        "Official company sources",
    ]
    assert [button.label for button in app.button] == [
        "Search and rank official jobs"
    ]
    rendered_markdown = " ".join(element.value for element in app.markdown)
    assert "Find roles that fit your real technical strengths" in rendered_markdown
    assert "What happens next" in rendered_markdown
