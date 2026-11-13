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

    vtype, cat = get_video_type_and_category("03 - World's Best Warm up Mobility Flow.mp4")
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


def test_list_exercise_videos_separation(tmp_path, monkeypatch):
    import fleet.core.exercise_manager as em_mod
    if not em_mod.FFD_VIDEOS_DIR.exists():
        (tmp_path / "01 - Anti gravity Exercise.mp4").write_bytes(b"0" * 1024)
        (tmp_path / "02 - Super Green Smoothie.mp4").write_bytes(b"0" * 1024)
        monkeypatch.setattr(em_mod, "FFD_VIDEOS_DIR", tmp_path)
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


def test_all_exercise_videos_accessible_stream_and_open_including_warmup_apostrophes(tmp_path, monkeypatch):
    """
    Verifies that every exercise and diet video—especially:
      1. '03 - Get your whole body warmed up in just 10 mins.mp4' (Category: "World's Best Warm-Up & Mobility")
      2. '03 - World's Best Warm up ... Freedom from Diabetes.mp4'
      3. '03 - World’s Best Warm-Up.mp4'
    is accessible for HTTP Range streaming (/api/health/video/stream), system player launch
    (/api/health/video/open_system via JSON body AND ?file= query param), and that health.js
    properly escapes apostrophes in onclick handlers.
    """
    import io
    from pathlib import Path
    import urllib.parse
    from unittest.mock import MagicMock
    import fleet.core.exercise_manager as em_mod
    import fleet.api.health_api as health_api

    fallback_warmup_files = [
        "03 - Get your whole body warmed up in just 10 mins.mp4",
        "03 - Super Brain Yoga for Diabetes.mp4",
        "03 - World's Best Warm up _ Freedom from Diabetes.mp4",
        "03 - World’s Best Warm-Up.mp4",
    ]

    # If running in headless CI where ./data/videos is not present, seed realistic MP4 files in tmp_path
    if not em_mod.FFD_VIDEOS_DIR.exists() or not list(em_mod.FFD_VIDEOS_DIR.glob("*.mp4")):
        mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + (b"\x00" * 4096)
        for fname in fallback_warmup_files + ["02 - Super Green Smoothie for Diabetics.mp4"]:
            (tmp_path / fname).write_bytes(mp4_header)
        monkeypatch.setattr(em_mod, "FFD_VIDEOS_DIR", tmp_path)
        monkeypatch.setattr(health_api, "FFD_VIDEOS_DIR", tmp_path)

    videos = list_exercise_videos()
    assert len(videos) >= 3
    filenames = [v["filename"] for v in videos]
    assert any("warmed up in just 10 mins" in f.lower() for f in filenames)
    assert any("world's best warm up" in f.lower() and "freedom from diabetes" in f.lower() for f in filenames)
    assert any("world" in f.lower() and "best warm-up" in f.lower() for f in filenames)

    # Verify every single video in the catalog streams (HTTP 206 Range) and opens via API
    for v in videos:
        fname = v["filename"]
        enc_fname = urllib.parse.quote(fname)

        # 1. Stream video with Range header (bytes=0-1023) -> HTTP 206 Partial Content
        h_stream = MagicMock()
        h_stream.headers = {"Range": "bytes=0-511"}
        h_stream.wfile = io.BytesIO()
        parsed_stream = urllib.parse.urlparse(f"/api/health/video/stream?file={enc_fname}")
        health_api.stream_video(h_stream, parsed_stream)
        h_stream.send_response.assert_called_with(206)
        streamed_bytes = h_stream.wfile.getvalue()
        assert len(streamed_bytes) == 512
        assert b"ftyp" in streamed_bytes[:32]

        # 2. Open video in system player via JSON body {"filename": fname}
        h_open_body = MagicMock()
        health_api.open_video_in_system(h_open_body, {"filename": fname})
        res_body = h_open_body._send_json.call_args[0][0]
        assert res_body["status"] in ("opened", "ok")
        assert res_body.get("ok") is True

        # 3. Open video in system player via query string ?file=... (with empty POST body)
        h_open_query = MagicMock()
        h_open_query.path = f"/api/health/video/open_system?file={enc_fname}"
        health_api.open_video_in_system(h_open_query, {})
        res_query = h_open_query._send_json.call_args[0][0]
        assert res_query["status"] in ("opened", "ok")
        assert res_query.get("ok") is True

    # 4. Also verify straight vs curly apostrophe AND legacy numeric prefix ('01 - ' -> '03 - ') fallback resolution
    h_curly = MagicMock()
    health_api.open_video_in_system(h_curly, {"filename": "03 - World's Best Warm-Up.mp4"})
    assert h_curly._send_json.call_args[0][0]["status"] == "opened"

    h_prefix = MagicMock()
    health_api.open_video_in_system(h_prefix, {"filename": "01 - Super Brain Yoga for Diabetes.mp4"})
    assert h_prefix._send_json.call_args[0][0]["status"] == "opened"
    assert h_prefix._send_json.call_args[0][0]["filename"] == "03 - Super Brain Yoga for Diabetes.mp4"

    h_stream_prefix = MagicMock()
    h_stream_prefix.headers = {"Range": "bytes=0-511"}
    h_stream_prefix.wfile = io.BytesIO()
    health_api.stream_video(
        h_stream_prefix,
        urllib.parse.urlparse("/api/health/video/stream?file=" + urllib.parse.quote("01 - Super Brain Yoga for Diabetes.mp4")),
    )
    h_stream_prefix.send_response.assert_called_with(206)

    # 5. Verify frontend health.js properly escapes apostrophes (\\') in onclick handlers
    health_js_path = Path(__file__).resolve().parent.parent / "fleet" / "web" / "static" / "js" / "health.js"
    js_text = health_js_path.read_text(encoding="utf-8")
    assert "function escapeJsAttrStr(" in js_text
    assert '.replace(/\'/g, "\\\'")' not in js_text, "Broken single-backslash replace must not exist in health.js"
    assert "escapeJsAttrStr(v.filename)" in js_text
    assert "escapeJsAttrStr(v.category" in js_text


def test_custom_video_playlists_crud_and_sequential_playback(tmp_path, monkeypatch):
    """
    Verifies custom video playlist creation, saving, updating, deletion, and
    sequential one-by-one playback wiring across health_api.py, health.js, and dashboard.html.
    """
    from pathlib import Path
    import urllib.parse
    from unittest.mock import MagicMock
    import fleet.api.health_api as health_api

    playlist_file = tmp_path / "video_playlists.json"
    monkeypatch.setenv("FLEET_VIDEO_PLAYLISTS_PATH", str(playlist_file))

    # 1. Initial GET seeds default starter playlist
    h = MagicMock()
    health_api.get_video_playlists(h, urllib.parse.urlparse("/api/health/playlists"))
    res_init = h._send_json.call_args[0][0]
    assert res_init["status"] == "ok"
    assert len(res_init["playlists"]) >= 1
    assert playlist_file.exists()

    # 2. Save a new custom playlist (mix of dict and string items)
    h.reset_mock()
    health_api.save_video_playlist_endpoint(h, {
        "name": "Morning Warm-Up & Strength",
        "videos": [
            {
                "filename": "Get your whole body warmed up in just 10 mins.mp4",
                "title": "Get your whole body warmed up in just 10 mins",
                "category": "World's Best Warm-Up & Mobility",
            },
            "04 - Modified Nitric Oxide Dump Exercise for Diabetes.mp4",
        ],
    })
    res_save = h._send_json.call_args[0][0]
    assert res_save["status"] == "saved"
    saved_pl = res_save["playlist"]
    assert saved_pl["name"] == "Morning Warm-Up & Strength"
    assert len(saved_pl["videos"]) == 2
    assert saved_pl["videos"][1]["filename"] == "04 - Modified Nitric Oxide Dump Exercise for Diabetes.mp4"

    # 3. Update existing playlist by id
    h.reset_mock()
    health_api.save_video_playlist_endpoint(h, {
        "id": saved_pl["id"],
        "name": "Morning Warm-Up & Strength (Updated)",
        "videos": [
            {
                "filename": "Get your whole body warmed up in just 10 mins.mp4",
                "title": "Get your whole body warmed up in just 10 mins",
                "category": "World's Best Warm-Up & Mobility",
            },
        ],
    })
    res_upd = h._send_json.call_args[0][0]
    assert res_upd["status"] == "saved"
    assert len(res_upd["playlist"]["videos"]) == 1

    # 4. Validation errors on save and delete
    h.reset_mock()
    health_api.save_video_playlist_endpoint(h, {"name": "", "videos": []})
    assert h._send_json.call_args[0][1] == 400

    h.reset_mock()
    health_api.save_video_playlist_endpoint(h, {"name": "Empty", "videos": []})
    assert h._send_json.call_args[0][1] == 400

    h.reset_mock()
    health_api.save_video_playlist_endpoint(h, {"name": "Invalid Videos", "videos": [{}]})
    assert h._send_json.call_args[0][1] == 400

    h.reset_mock()
    health_api.delete_video_playlist_endpoint(h, {})
    assert h._send_json.call_args[0][1] == 400

    # 5. Delete playlist by id
    h.reset_mock()
    health_api.delete_video_playlist_endpoint(h, {"id": saved_pl["id"]})
    res_del = h._send_json.call_args[0][0]
    assert res_del["status"] == "deleted"
    assert res_del["deleted"] is True

    # 6. Raw list JSON & corrupted JSON fallbacks
    playlist_file.write_text('[{"id": "pl_raw", "name": "Raw List", "videos": []}]', encoding="utf-8")
    assert len(health_api.load_video_playlists()) == 1
    playlist_file.write_text("not-valid-json", encoding="utf-8")
    assert len(health_api.load_video_playlists()) >= 1

    # 7. Verify open_video_vault_folder (/api/health/video/open_folder)
    h.reset_mock()
    health_api.open_video_vault_folder(h, {})
    res_folder = h._send_json.call_args[0][0]
    assert res_folder["status"] == "opened"
    assert res_folder["ok"] is True

    # 8. Verify frontend sequential playback, zero-stream card thumbnails, and playlist builder wiring
    root_dir = Path(__file__).resolve().parent.parent
    js_text = (root_dir / "fleet" / "web" / "static" / "js" / "health.js").read_text(encoding="utf-8")
    html_text = (root_dir / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "function saveCurrentVideoPlaylist()" in js_text
    assert "function playSelectedPlaylist()" in js_text
    assert "function playPlaylistAtIndex(" in js_text
    assert "function playNextInPlaylist()" in js_text
    assert "function playPrevInPlaylist()" in js_text
    assert "function openVideoVaultFolder()" in js_text
    assert "function _getVideoCardTheme(" in js_text
    assert "function _resolveCanonicalVideoItem(" in js_text
    assert "src=\"${streamUrl}#t=1.0\"" not in js_text, "Grid cards must not open 11 simultaneous <video> streams"
    assert "player.onended =" in js_text
    assert 'id="videoPlaylistBar"' in html_text
    assert 'id="videoPlaylistBuilderPanel"' in html_text
    assert 'id="videoModalPlaylistBar"' in html_text


def test_video_thumbnails_youtube_crud_and_oauth_sync(tmp_path, monkeypatch):
    """Verify video thumbnail caching/serving, YouTube video/playlist addition, and Google OAuth YouTube playlist sync."""
    import base64
    import urllib.parse
    from pathlib import Path
    from unittest.mock import MagicMock
    from fleet.api import health_api

    monkeypatch.setenv("FLEET_VIDEO_THUMBNAILS_DIR", str(tmp_path / "video_thumbnails"))
    monkeypatch.setenv("FLEET_YOUTUBE_VIDEOS_PATH", str(tmp_path / "youtube_videos.json"))
    monkeypatch.setenv("FLEET_VIDEO_PLAYLISTS_PATH", str(tmp_path / "video_playlists.json"))
    monkeypatch.setattr(health_api, "_get_youtube_token_file", lambda: tmp_path / "youtube_token.json")

    def _make_handler():
        h = MagicMock()
        h.headers = {}
        h.wfile = MagicMock()
        return h

    # 1. Save and serve a cached JPEG thumbnail
    h = _make_handler()
    sample_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    data_url = "data:image/jpeg;base64," + base64.b64encode(sample_jpeg).decode("ascii")
    health_api.save_video_thumbnail_endpoint(h, {
        "filename": "03 - Super Brain Yoga for Diabetes.mp4",
        "data_url": data_url,
    })
    res_thumb = h._send_json.call_args[0][0]
    assert res_thumb["status"] == "saved"
    assert "/api/health/video/thumbnail?file=" in res_thumb["thumbnail_url"]

    h2 = _make_handler()
    parsed_thumb_url = urllib.parse.urlparse(
        "/api/health/video/thumbnail?file=" + urllib.parse.quote("03 - Super Brain Yoga for Diabetes.mp4")
    )
    health_api.get_video_thumbnail(h2, parsed_thumb_url)
    h2.send_response.assert_called_with(200)
    h2.wfile.write.assert_called_once_with(sample_jpeg)

    # 2. Add a single YouTube video and verify it appears in get_exercise_videos with thumbnail_url
    monkeypatch.setattr(
        health_api,
        "_fetch_youtube_oembed_metadata",
        lambda yt_id: {"title": "Surya Namaskar Guided Practice", "author_name": "FFD Channel"},
    )
    h3 = _make_handler()
    health_api.add_youtube_video_endpoint(h3, {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_type": "exercise",
        "category": "Surya Namaskar Series",
    })
    res_add = h3._send_json.call_args[0][0]
    assert res_add["status"] == "added"
    assert res_add["video"]["youtube_id"] == "dQw4w9WgXcQ"
    assert res_add["video"]["is_youtube"] is True
    assert "hqdefault.jpg" in res_add["video"]["thumbnail_url"]

    h4 = _make_handler()
    health_api.get_exercise_videos(h4, urllib.parse.urlparse("/api/health/videos"))
    res_list = h4._send_json.call_args[0][0]
    assert isinstance(res_list, list)
    yt_matches = [v for v in res_list if v.get("youtube_id") == "dQw4w9WgXcQ"]
    assert len(yt_matches) == 1
    assert yt_matches[0]["title"] == "Surya Namaskar Guided Practice"

    # Also verify cached local thumbnail appears on the local video in get_exercise_videos
    sby_matches = [v for v in res_list if "Super Brain Yoga" in str(v.get("filename", ""))]
    assert len(sby_matches) == 1
    assert "/api/health/video/thumbnail?file=" in sby_matches[0]["thumbnail_url"]

    # 3. Add a YouTube playlist URL
    monkeypatch.setattr(
        health_api,
        "_fetch_public_youtube_playlist_items",
        lambda pl_id: ("Morning Mobility Routine", [
            {"youtube_id": "abc12345678", "title": "Warm Up Step 1", "channel": "Coach"},
            {"youtube_id": "def12345678", "title": "Warm Up Step 2", "channel": "Coach"},
        ]),
    )
    h5 = _make_handler()
    health_api.add_youtube_video_endpoint(h5, {
        "url": "https://www.youtube.com/playlist?list=PL1234567890ABCD",
        "video_type": "exercise",
        "category": "World's Best Warm-Up & Mobility",
    })
    res_pl = h5._send_json.call_args[0][0]
    assert res_pl["status"] == "imported_playlist"
    assert res_pl["added_count"] == 2
    assert res_pl["playlist"]["name"] == "Morning Mobility Routine"

    # 4. Delete a YouTube video
    h6 = _make_handler()
    health_api.delete_youtube_video_endpoint(h6, {"youtube_id": "dQw4w9WgXcQ"})
    res_del = h6._send_json.call_args[0][0]
    assert res_del["status"] == "deleted"
    assert res_del["deleted"] is True

    # 5. Check Google YouTube OAuth status
    h7 = _make_handler()
    health_api.get_youtube_oauth_status(h7, urllib.parse.urlparse("/api/health/youtube/oauth/status"))
    res_status = h7._send_json.call_args[0][0]
    assert res_status["status"] == "ok"
    assert "credentials_file_present" in res_status

    # Verify frontend wiring for thumbnails, YouTube iframe & Google OAuth sync
    root_dir = Path(__file__).resolve().parent.parent
    js_text = (root_dir / "fleet" / "web" / "static" / "js" / "health.js").read_text(encoding="utf-8")
    html_text = (root_dir / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "function _queueMissingVideoThumbnails(" in js_text
    assert "function submitAddYoutubeVideo()" in js_text
    assert "function syncPersonalYoutubePlaylistsOAuth()" in js_text
    assert 'id="exerciseYoutubeIframe"' in html_text
    assert 'id="addYoutubeVideoPanel"' in html_text
    assert 'id="btnSyncGoogleYoutubePlaylists"' in html_text




