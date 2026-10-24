import pytest
from fleet.core.exercise_manager import (
    get_video_type_and_category,
    list_exercise_videos,
    get_strength_training_plan,
    get_ffd_exercise_protocol,
)


def test_video_type_and_category_classification():
    # Exercise videos
    vtype, cat = get_video_type_and_category("05 - Importance of Anti gravity Exercise for Diabetics!.mp4")
    assert vtype == "exercise"
    assert "Anti-Gravity" in cat

    vtype, cat = get_video_type_and_category("03 - World's Best Warm up by Dr. Pramod Tripathi.mp4")
    assert vtype == "exercise"
    assert "Warm-Up" in cat

    vtype, cat = get_video_type_and_category("04 - Modified Nitric Oxide Dump Exercise for Diabetes.mp4")
    assert vtype == "exercise"
    assert "Nitric Oxide Dump" in cat

    # Diet videos
    vtype, cat = get_video_type_and_category("02 - Super Green Smoothie for Diabetics.mp4")
    assert vtype == "diet"
    assert "Smoothie" in cat

    vtype, cat = get_video_type_and_category("07 - Tea, Coffee & Diabetes.mp4")
    assert vtype == "diet"
    assert "Tea" in cat


def test_list_exercise_videos_separation():
    all_videos = list_exercise_videos()
    assert len(all_videos) > 0

    exercise_videos = list_exercise_videos(video_type_filter="exercise")
    diet_videos = list_exercise_videos(video_type_filter="diet")

    assert len(exercise_videos) > 0
    assert len(diet_videos) > 0
    assert len(exercise_videos) + len(diet_videos) == len(all_videos)

    for ev in exercise_videos:
        assert ev["video_type"] == "exercise"
        assert "filename" in ev
        assert "category" in ev

    for dv in diet_videos:
        assert dv["video_type"] == "diet"
        assert "filename" in dv
        assert "category" in dv


def test_strength_training_plan_6_days_and_sunday_rest():
    plan = get_strength_training_plan()

    assert plan["rest_day"] == "Sunday"
    days = plan["days"]
    assert len(days) == 7

    # Day 1: Monday - Mudgal
    assert days[0]["day_name"] == "Monday"
    assert "Mudgal" in days[0]["primary_tool"]
    assert "World's Best Warm-up" in days[0]["mandatory_warmup"]

    # Day 2: Tuesday - Active FFD Reversal
    assert days[1]["day_name"] == "Tuesday"
    assert "World's Best Warm-up" in days[1]["mandatory_warmup"]

    # Day 3: Wednesday - Samtola
    assert days[2]["day_name"] == "Wednesday"
    assert "Samtola" in days[2]["primary_tool"]
    assert "World's Best Warm-up" in days[2]["mandatory_warmup"]

    # Day 4: Thursday - FFD Conditioning / NOD / Weighted Walking
    assert days[3]["day_name"] == "Thursday"
    assert "World's Best Warm-up" in days[3]["mandatory_warmup"]

    # Day 5: Friday - Bhim Gadha
    assert days[4]["day_name"] == "Friday"
    assert "Bhim Gadha" in days[4]["primary_tool"]
    assert "World's Best Warm-up" in days[4]["mandatory_warmup"]

    # Day 6: Saturday - Akhada Flow Integration
    assert days[5]["day_name"] == "Saturday"
    assert "World's Best Warm-up" in days[5]["mandatory_warmup"]

    # Day 7: Sunday - Rest
    assert days[6]["day_name"] == "Sunday"
    assert days[6]["tool"] == "Rest"

    # Playlists
    playlists = plan["youtube_playlists"]
    assert len(playlists) >= 4
    tags = [p["tag"] for p in playlists]
    assert any("Mudgal" in t for t in tags)
    assert any("Samtola" in t for t in tags)
    assert any("Bhim Gadha" in t for t in tags)


def test_ffd_exercise_protocol():
    proto = get_ffd_exercise_protocol()
    assert "non_negotiables" in proto
    assert "antigravity_step_climbing" in proto
    assert "nitric_oxide_dump" in proto
    assert "hypoglycemia_protocol" in proto
    assert "mandatory_warmup" in proto

