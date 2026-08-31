from pathlib import Path
from PIL import Image
from story2toon.images import make_storyboard_fallback


def test_fallback_image(tmp_path: Path):
    path = tmp_path / "frame.jpg"
    make_storyboard_fallback("A cartoon traveler in a city", path, (320, 180), 1)
    assert path.exists()
    with Image.open(path) as img:
        assert img.size == (320, 180)
