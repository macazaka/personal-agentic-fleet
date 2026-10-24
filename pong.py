"""
Ping Pong Game - Player vs Automated AI (Easy Mode)
Control: Mouse cursor (vertical movement)
"""

import io
import math
import os
import random
import struct
import sys
import wave

# Suppress Pygame welcome message
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

# --- Game Configuration ---
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
FPS = 60

# Colors (Modern Neon-Retro Theme)
COLOR_BG = (16, 21, 36)            # Deep slate blue
COLOR_COURT_LINE = (38, 48, 77)    # Subtle center line
COLOR_PLAYER = (0, 230, 200)       # Vibrant Cyan
COLOR_PLAYER_GLOW = (0, 150, 130)  # Darker cyan for accents
COLOR_AI = (255, 99, 132)          # Coral / Neon Pink
COLOR_AI_GLOW = (180, 50, 80)
COLOR_BALL = (255, 255, 255)       # Crisp White
COLOR_TEXT = (230, 235, 245)
COLOR_MUTED = (130, 145, 175)
COLOR_WIN = (74, 222, 128)         # Soft Green
COLOR_LOSE = (248, 113, 113)       # Soft Red

# Gameplay Settings
PADDLE_WIDTH = 14
PADDLE_HEIGHT = 90
PADDLE_PADDING = 32
PADDLE_BORDER_RADIUS = 7

BALL_RADIUS = 9
BALL_INITIAL_SPEED = 6.2
BALL_MAX_SPEED = 11.5
BALL_ACCELERATION = 1.03

# Easy AI Settings
AI_SPEED_MAX = 4.0                 # Capped lower than ball speed
AI_REACTION_BOUNDARY = SCREEN_WIDTH * 0.30  # Doesn't react until ball crosses 30% court
AI_DEADZONE = 18                   # Prevents jitter / allows corner shots
WINNING_SCORE = 5


# --- Procedural Audio Generator ---
def create_beep_sound(frequency: float, duration_ms: int, volume: float = 0.3) -> pygame.mixer.Sound | None:
    """Generate a retro tone in memory without external audio files."""
    try:
        sample_rate = 44100
        n_samples = int(sample_rate * (duration_ms / 1000.0))
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for i in range(n_samples):
                t = float(i) / sample_rate
                # Smooth linear decay envelope to avoid speaker clicks
                envelope = max(0.0, 1.0 - (i / n_samples))
                val = int(volume * 32767.0 * envelope * math.sin(2.0 * math.pi * frequency * t))
                frames.extend(struct.pack("<h", val))
            wav.writeframes(frames)
        bio.seek(0)
        return pygame.mixer.Sound(bio)
    except Exception:
        return None


class SoundManager:
    def __init__(self):
        self.enabled = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self.hit_player = create_beep_sound(540, 50, 0.25)
            self.hit_ai = create_beep_sound(460, 50, 0.25)
            self.hit_wall = create_beep_sound(330, 40, 0.2)
            self.score = create_beep_sound(780, 180, 0.3)
            self.miss = create_beep_sound(220, 240, 0.3)
            self.win = create_beep_sound(880, 300, 0.35)
            self.enabled = True
        except Exception:
            self.enabled = False

    def play(self, sound_name: str):
        if not self.enabled:
            return
        sound = getattr(self, sound_name, None)
        if sound:
            try:
                sound.play()
            except Exception:
                pass


# --- Ball Object ---
class Ball:
    def __init__(self, x: float, y: float):
        self.reset(x, y, serve_to_player=True)

    def reset(self, x: float, y: float, serve_to_player: bool):
        self.x = float(x)
        self.y = float(y)
        self.radius = BALL_RADIUS
        self.speed = BALL_INITIAL_SPEED
        
        # Initial angle between -30 and +30 degrees
        angle = math.radians(random.uniform(-30, 30))
        direction = -1.0 if serve_to_player else 1.0
        self.vx = direction * self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)
        self.trail = []

    def update(self):
        # Store previous positions for trailing effect
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)

        self.x += self.vx
        self.y += self.vy

    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x - self.radius),
            int(self.y - self.radius),
            self.radius * 2,
            self.radius * 2
        )


# --- Game Engine ---
class PingPongGame:
    def __init__(self):
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Ping Pong — Cursor vs AI (Easy Mode)")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_score = pygame.font.SysFont("segoeui,helvetica,arial", 56, bold=True)
        self.font_ui = pygame.font.SysFont("segoeui,helvetica,arial", 20, bold=True)
        self.font_sub = pygame.font.SysFont("segoeui,helvetica,arial", 16)
        self.font_title = pygame.font.SysFont("segoeui,helvetica,arial", 42, bold=True)

        self.sounds = SoundManager()

        # Positions
        self.player_x = PADDLE_PADDING
        self.player_y = (SCREEN_HEIGHT - PADDLE_HEIGHT) // 2
        self.ai_x = SCREEN_WIDTH - PADDLE_PADDING - PADDLE_WIDTH
        self.ai_y = (SCREEN_HEIGHT - PADDLE_HEIGHT) // 2

        self.ball = Ball(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        # AI tracking attributes
        self.ai_target_offset = 0.0  # Intentional error for Easy AI
        self.pick_new_ai_offset()

        # Game State
        self.player_score = 0
        self.ai_score = 0
        self.state = "START"  # "START", "PLAYING", "PAUSED", "POINT_SCORED", "GAME_OVER"
        self.winner = ""
        self.point_timer = 0
        self.running = True

    def pick_new_ai_offset(self):
        """Easy AI aims for imperfect contact with an offset from paddle center."""
        self.ai_target_offset = random.uniform(-26, 26)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.running = False

                elif event.key == pygame.K_SPACE:
                    if self.state in ("START", "POINT_SCORED"):
                        self.state = "PLAYING"
                    elif self.state == "PLAYING":
                        self.state = "PAUSED"
                    elif self.state == "PAUSED":
                        self.state = "PLAYING"
                    elif self.state == "GAME_OVER":
                        self.reset_match()

                elif event.key == pygame.K_r:
                    self.reset_match()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.state in ("START", "POINT_SCORED"):
                        self.state = "PLAYING"
                    elif self.state == "GAME_OVER":
                        self.reset_match()

    def update_player(self):
        """Directly track cursor vertical position."""
        _, mouse_y = pygame.mouse.get_pos()
        target_y = mouse_y - (PADDLE_HEIGHT // 2)
        # Clamp to screen bounds
        self.player_y = max(10, min(SCREEN_HEIGHT - PADDLE_HEIGHT - 10, target_y))

    def update_ai(self):
        """
        Easy AI logic:
        - Reaction delay: Doesn't track until ball moves towards AI and past boundary.
        - Speed capped at AI_SPEED_MAX (slower than fast ball shots).
        - Deadzone prevents twitching.
        - Random offset causes occasional misses on steep angle shots.
        """
        paddle_center_y = self.ai_y + (PADDLE_HEIGHT / 2)

        if self.ball.vx > 0 and self.ball.x >= AI_REACTION_BOUNDARY:
            # Ball is heading towards AI and is on its side of the table
            target_y = self.ball.y + self.ai_target_offset
        else:
            # Drift gently towards the center
            target_y = SCREEN_HEIGHT / 2

        diff = target_y - paddle_center_y

        if abs(diff) > AI_DEADZONE:
            step = min(AI_SPEED_MAX, abs(diff))
            if diff > 0:
                self.ai_y += step
            else:
                self.ai_y -= step

        # Clamp AI paddle to court
        self.ai_y = max(10, min(SCREEN_HEIGHT - PADDLE_HEIGHT - 10, self.ai_y))

    def update_ball(self):
        self.ball.update()

        # Bounce off top and bottom walls
        if self.ball.y - self.ball.radius <= 10:
            self.ball.y = 10 + self.ball.radius
            self.ball.vy = abs(self.ball.vy)
            self.sounds.play("hit_wall")
        elif self.ball.y + self.ball.radius >= SCREEN_HEIGHT - 10:
            self.ball.y = SCREEN_HEIGHT - 10 - self.ball.radius
            self.ball.vy = -abs(self.ball.vy)
            self.sounds.play("hit_wall")

        # Paddle Collision Hitboxes
        player_rect = pygame.Rect(self.player_x, self.player_y, PADDLE_WIDTH, PADDLE_HEIGHT)
        ai_rect = pygame.Rect(self.ai_x, self.ai_y, PADDLE_WIDTH, PADDLE_HEIGHT)
        ball_rect = self.ball.rect()

        # Collide with Player Paddle (Left)
        if self.ball.vx < 0 and ball_rect.colliderect(player_rect):
            self.ball.x = self.player_x + PADDLE_WIDTH + self.ball.radius
            self.handle_paddle_bounce(player_rect, is_player=True)
            self.sounds.play("hit_player")
            self.pick_new_ai_offset()

        # Collide with AI Paddle (Right)
        elif self.ball.vx > 0 and ball_rect.colliderect(ai_rect):
            self.ball.x = self.ai_x - self.ball.radius
            self.handle_paddle_bounce(ai_rect, is_player=False)
            self.sounds.play("hit_ai")

        # Check Scoring (Passed Left or Right bounds)
        if self.ball.x < -self.ball.radius:
            # AI scored
            self.ai_score += 1
            self.sounds.play("miss")
            self.check_score(serve_to_player=True)

        elif self.ball.x > SCREEN_WIDTH + self.ball.radius:
            # Player scored
            self.player_score += 1
            self.sounds.play("score")
            self.check_score(serve_to_player=False)

    def handle_paddle_bounce(self, paddle_rect: pygame.Rect, is_player: bool):
        """Angle reflection based on hit distance from paddle center."""
        paddle_center_y = paddle_rect.y + (PADDLE_HEIGHT / 2)
        relative_intersect = (self.ball.y - paddle_center_y) / (PADDLE_HEIGHT / 2)
        # Clamp relative intersect between -1.0 and 1.0
        relative_intersect = max(-1.0, min(1.0, relative_intersect))

        # Max reflection angle of 50 degrees
        max_angle = math.radians(50)
        bounce_angle = relative_intersect * max_angle

        # Accelerate ball slightly on every return
        self.ball.speed = min(self.ball.speed * BALL_ACCELERATION, BALL_MAX_SPEED)

        direction = 1.0 if is_player else -1.0
        self.ball.vx = direction * self.ball.speed * math.cos(bounce_angle)
        self.ball.vy = self.ball.speed * math.sin(bounce_angle)

    def check_score(self, serve_to_player: bool):
        if self.player_score >= WINNING_SCORE:
            self.winner = "Player"
            self.state = "GAME_OVER"
            self.sounds.play("win")
        elif self.ai_score >= WINNING_SCORE:
            self.winner = "AI"
            self.state = "GAME_OVER"
            self.sounds.play("miss")
        else:
            self.state = "POINT_SCORED"
            self.point_timer = pygame.time.get_ticks()
            self.ball.reset(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, serve_to_player=serve_to_player)

    def reset_match(self):
        self.player_score = 0
        self.ai_score = 0
        self.winner = ""
        self.ball.reset(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, serve_to_player=True)
        self.state = "PLAYING"
        self.pick_new_ai_offset()

    def draw(self):
        self.screen.fill(COLOR_BG)

        # Draw Court Boundaries (Subtle top & bottom border lines)
        pygame.draw.line(self.screen, COLOR_COURT_LINE, (0, 8), (SCREEN_WIDTH, 8), 2)
        pygame.draw.line(self.screen, COLOR_COURT_LINE, (0, SCREEN_HEIGHT - 8), (SCREEN_WIDTH, SCREEN_HEIGHT - 8), 2)

        # Draw Dashed Center Divider
        center_x = SCREEN_WIDTH // 2
        segment_height = 14
        gap = 10
        for y in range(16, SCREEN_HEIGHT - 16, segment_height + gap):
            pygame.draw.line(self.screen, COLOR_COURT_LINE, (center_x, y), (center_x, y + segment_height), 3)

        # Draw Ball Trail
        for idx, (tx, ty) in enumerate(self.ball.trail):
            alpha_ratio = (idx + 1) / (len(self.ball.trail) + 1)
            trail_radius = int(self.ball.radius * alpha_ratio * 0.8)
            if trail_radius > 1:
                trail_color = (
                    int(COLOR_BALL[0] * alpha_ratio * 0.4),
                    int(COLOR_BALL[1] * alpha_ratio * 0.4),
                    int(COLOR_BALL[2] * alpha_ratio * 0.4),
                )
                pygame.draw.circle(self.screen, trail_color, (int(tx), int(ty)), trail_radius)

        # Draw Ball
        pygame.draw.circle(
            self.screen,
            COLOR_BALL,
            (int(self.ball.x), int(self.ball.y)),
            self.ball.radius
        )

        # Draw Player Paddle (Cyan with glowing accents)
        player_rect = pygame.Rect(self.player_x, int(self.player_y), PADDLE_WIDTH, PADDLE_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_PLAYER_GLOW, player_rect.inflate(4, 4), border_radius=PADDLE_BORDER_RADIUS)
        pygame.draw.rect(self.screen, COLOR_PLAYER, player_rect, border_radius=PADDLE_BORDER_RADIUS)

        # Draw AI Paddle (Coral/Pink with accents)
        ai_rect = pygame.Rect(self.ai_x, int(self.ai_y), PADDLE_WIDTH, PADDLE_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_AI_GLOW, ai_rect.inflate(4, 4), border_radius=PADDLE_BORDER_RADIUS)
        pygame.draw.rect(self.screen, COLOR_AI, ai_rect, border_radius=PADDLE_BORDER_RADIUS)

        # Draw Scoreboard
        p_surf = self.font_score.render(str(self.player_score), True, COLOR_PLAYER)
        ai_surf = self.font_score.render(str(self.ai_score), True, COLOR_AI)
        self.screen.blit(p_surf, (center_x - 90 - p_surf.get_width() // 2, 24))
        self.screen.blit(ai_surf, (center_x + 90 - ai_surf.get_width() // 2, 24))

        # Header Badges
        p_label = self.font_sub.render("YOU (CURSOR)", True, COLOR_PLAYER)
        ai_label = self.font_sub.render("AI (EASY)", True, COLOR_AI)
        self.screen.blit(p_label, (center_x - 90 - p_label.get_width() // 2, 85))
        self.screen.blit(ai_label, (center_x + 90 - ai_label.get_width() // 2, 85))

        # Target Score Badge
        first_to = self.font_sub.render(f"First to {WINNING_SCORE} Wins", True, COLOR_MUTED)
        self.screen.blit(first_to, (center_x - first_to.get_width() // 2, SCREEN_HEIGHT - 32))

        # Overlay text according to State
        if self.state == "START":
            self.draw_overlay_card(
                title="PING PONG",
                subtitle="Move your cursor up and down to control your paddle",
                hint="Click anywhere or press SPACE to Serve"
            )
        elif self.state == "PAUSED":
            self.draw_overlay_card(
                title="PAUSED",
                subtitle="Take a breather!",
                hint="Press SPACE to Resume • Press R to Restart"
            )
        elif self.state == "POINT_SCORED":
            # Automatically resume after 0.8s or prompt
            elapsed = pygame.time.get_ticks() - self.point_timer
            if elapsed > 900:
                self.state = "PLAYING"
            else:
                hint_surf = self.font_ui.render("Ready...", True, COLOR_TEXT)
                self.screen.blit(hint_surf, (center_x - hint_surf.get_width() // 2, SCREEN_HEIGHT // 2 + 60))

        elif self.state == "GAME_OVER":
            if self.winner == "Player":
                self.draw_overlay_card(
                    title="VICTORY!",
                    subtitle="Outstanding game! You defeated the AI.",
                    hint="Click anywhere or press SPACE to Play Again",
                    title_color=COLOR_WIN
                )
            else:
                self.draw_overlay_card(
                    title="GAME OVER",
                    subtitle="The AI took this match. Ready for a rematch?",
                    hint="Click anywhere or press SPACE to Try Again",
                    title_color=COLOR_LOSE
                )

        pygame.display.flip()

    def draw_overlay_card(self, title: str, subtitle: str, hint: str, title_color=COLOR_TEXT):
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2

        card_width = 540
        card_height = 180
        card_rect = pygame.Rect(
            center_x - card_width // 2,
            center_y - card_height // 2 - 10,
            card_width,
            card_height
        )

        # Translucent dark backdrop card
        card_surface = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
        card_surface.fill((12, 16, 28, 220))
        self.screen.blit(card_surface, card_rect.topleft)
        pygame.draw.rect(self.screen, COLOR_COURT_LINE, card_rect, width=2, border_radius=12)

        # Render texts
        title_surf = self.font_title.render(title, True, title_color)
        sub_surf = self.font_sub.render(subtitle, True, COLOR_TEXT)
        hint_surf = self.font_ui.render(hint, True, COLOR_PLAYER)

        self.screen.blit(title_surf, (center_x - title_surf.get_width() // 2, card_rect.y + 24))
        self.screen.blit(sub_surf, (center_x - sub_surf.get_width() // 2, card_rect.y + 82))
        self.screen.blit(hint_surf, (center_x - hint_surf.get_width() // 2, card_rect.y + 124))

    def run(self):
        while self.running:
            self.handle_events()

            # Always track cursor for seamless responsiveness
            self.update_player()

            if self.state == "PLAYING":
                self.update_ai()
                self.update_ball()

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    game = PingPongGame()
    game.run()

