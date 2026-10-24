"""Unit tests for pong.py."""
import os
import math
from unittest.mock import MagicMock, patch

# Configure headless SDL for Pygame before import
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest
pygame = pytest.importorskip("pygame", reason="pygame is not installed, skipping pong tests")
pong = pytest.importorskip("pong", reason="pong module requires pygame")


def test_pong_sound_and_ball():
    # 1. Beep sound generator
    sound = pong.create_beep_sound(440, 50, volume=0.1)
    # May be Sound or None depending on driver
    bad_sound = pong.create_beep_sound(-1, -1)

    # 2. SoundManager
    sm = pong.SoundManager()
    sm.play("hit_player")
    sm.play("non_existent_sound")

    # 3. Ball
    ball = pong.Ball(450, 300)
    assert ball.x == 450.0
    assert ball.y == 300.0
    assert isinstance(ball.rect(), pygame.Rect)

    # Update ball position and trail
    for _ in range(10):
        ball.update()
    assert len(ball.trail) == 6


def test_pong_game_engine():
    game = pong.PingPongGame()

    # 1. Player tracking
    with patch("pygame.mouse.get_pos", return_value=(100, 250)):
        game.update_player()
        assert 10 <= game.player_y <= pong.SCREEN_HEIGHT - pong.PADDLE_HEIGHT

    # 2. AI Tracking
    # Ball moving towards AI
    game.ball.x = pong.SCREEN_WIDTH * 0.5
    game.ball.vx = 5.0
    game.ball.y = 300
    game.update_ai()

    # Ball moving away from AI
    game.ball.vx = -5.0
    game.update_ai()

    # 3. Ball wall bounce and paddle collision
    game.ball.y = 8  # Top wall collision
    game.ball.vy = -3
    game.update_ball()
    assert game.ball.vy > 0

    game.ball.y = pong.SCREEN_HEIGHT - 5  # Bottom wall collision
    game.ball.vy = 3
    game.update_ball()
    assert game.ball.vy < 0

    # Paddle bounce
    p_rect = pygame.Rect(game.player_x, game.player_y, pong.PADDLE_WIDTH, pong.PADDLE_HEIGHT)
    game.handle_paddle_bounce(p_rect, is_player=True)
    assert game.ball.vx > 0

    ai_rect = pygame.Rect(game.ai_x, game.ai_y, pong.PADDLE_WIDTH, pong.PADDLE_HEIGHT)
    game.handle_paddle_bounce(ai_rect, is_player=False)
    assert game.ball.vx < 0

    # 4. Scoring and states
    game.player_score = 4
    game.ball.x = pong.SCREEN_WIDTH + 20
    game.update_ball()
    assert game.winner == "Player"
    assert game.state == "GAME_OVER"

    game.reset_match()
    assert game.player_score == 0
    assert game.state == "PLAYING"

    game.ai_score = 4
    game.ball.x = -20
    game.update_ball()
    assert game.winner == "AI"
    assert game.state == "GAME_OVER"

    # 5. Drawing across all states
    for state in ["START", "PLAYING", "PAUSED", "POINT_SCORED", "GAME_OVER"]:
        game.state = state
        game.draw()

    # 6. Events handling comprehensive
    # 6a. QUIT event
    game.running = True
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.QUIT)]):
        game.handle_events()
        assert game.running is False

    # 6b. K_q key
    game.running = True
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)]):
        game.handle_events()
        assert game.running is False

    # 6c. K_SPACE toggles through all states
    game.running = True
    game.state = "START"
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]):
        game.handle_events()
        assert game.state == "PLAYING"

    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]):
        game.handle_events()
        assert game.state == "PAUSED"

    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]):
        game.handle_events()
        assert game.state == "PLAYING"

    game.state = "GAME_OVER"
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]):
        game.handle_events()
        assert game.state == "PLAYING"

    # 6d. Mouse click in START and GAME_OVER
    game.state = "START"
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)]):
        game.handle_events()
        assert game.state == "PLAYING"

    game.state = "GAME_OVER"
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)]):
        game.handle_events()
        assert game.state == "PLAYING"

    # 6e. K_r resets match
    with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)]):
        game.player_score = 3
        game.handle_events()
        assert game.player_score == 0

    # 6f. AI paddle moving upwards
    game.ai_y = 500
    game.ball.vx = -10.0  # Heading away, drifts toward center (300)
    game.update_ai()
    assert game.ai_y < 500

    # 7. Ball paddle collisions in update_ball
    # Hit player paddle
    game.state = "PLAYING"
    game.ball.vx = -4.0
    game.ball.vy = 0.0
    game.ball.x = game.player_x + pong.PADDLE_WIDTH + 2
    game.ball.y = game.player_y + 20
    game.update_ball()
    assert game.ball.vx > 0

    # Hit AI paddle
    game.ball.vx = 4.0
    game.ball.vy = 0.0
    game.ball.x = game.ai_x - 2
    game.ball.y = game.ai_y + 20
    game.update_ball()
    assert game.ball.vx < 0

    # 8. Check score point scored state
    game.player_score = 1
    game.ai_score = 1
    game.check_score(serve_to_player=True)
    assert game.state == "POINT_SCORED"

    # Draw game over screens for Player and AI winner
    game.state = "GAME_OVER"
    game.winner = "Player"
    game.draw()
    game.winner = "AI"
    game.draw()

    # 9. SoundManager disabled & exceptions
    sm = pong.SoundManager()
    sm.enabled = False
    sm.play("hit_wall")

    sm.enabled = True
    mock_bad_snd = MagicMock()
    mock_bad_snd.play.side_effect = Exception("Audio fail")
    sm.hit_wall = mock_bad_snd
    sm.play("hit_wall")

    # 10. Run loop single iteration in PLAYING state
    game.state = "PLAYING"
    game.running = True
    tick_count = 0
    def _stop_after_tick(*args):
        nonlocal tick_count
        tick_count += 1
        if tick_count >= 2:
            game.running = False

    mock_clock = MagicMock()
    mock_clock.tick.side_effect = _stop_after_tick
    game.clock = mock_clock
    game.run()
    assert game.running is False

    # 11. SoundManager __init__ failure (lines 91-92)
    with patch("pygame.mixer.init", side_effect=Exception("No audio device")):
        sm_failed = pong.SoundManager()
        assert sm_failed.enabled is False




