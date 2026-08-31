from story2toon.story import plan_scenes


def test_plan_scenes_respects_count_when_possible():
    story = "One. Two. Three. Four. Five."
    scenes = plan_scenes(story, "Luna", "3D cartoon", scene_count=5, target_duration=30)
    assert len(scenes) == 5
    assert scenes[0].index == 1
    assert all(scene.duration >= 3 for scene in scenes)


def test_empty_story_raises():
    try:
        plan_scenes("   ", "Luna", "cartoon")
    except ValueError:
        return
    raise AssertionError("Expected ValueError")
