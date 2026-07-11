# settings.py
FPS = 60
N = 7

EMPTY, RED, BLUE = 0, 1, 2
DIRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

MIN_W, MIN_H = 1280, 780
SIDEBAR_W = 420
TOPBAR_H = 74
PAD = 16

# -------------------------
# Minecraft‑inspired Theme
# -------------------------
BG = (87, 101, 71)           # dark green (forest)
PANEL = (76, 60, 42)         # dark oak wood
PANEL2 = (90, 72, 52)        # lighter wood
GRID_A = (116, 96, 67)       # dirt path
GRID_B = (100, 82, 57)       # coarse dirt
GRIDLINE = (45, 45, 45)      # dark border

TXT = (255, 255, 200)        # off‑white (like paper)
MUTED = (170, 150, 120)      # light brown

RED_C = (255, 100, 100)      # redstone
BLUE_C = (70, 120, 255)      # lapis lazuli
HAZ_C = (255, 120, 0)        # lava / orange

ACC = (255, 255, 85)         # gold (win highlight)
GOOD = (85, 255, 85)         # emerald (good hint)
SUGG = (255, 170, 0)         # orange (suggestion)
WHITE = (255, 255, 255)

# Difficulty settings
DIFFS = {
    "LOW":    {"haz_count": 2, "smart": 0.15},
    "MEDIUM": {"haz_count": 3, "smart": 0.55},
    "HARD":   {"haz_count": 4, "smart": 0.95},
}

# AI Personality Profiles (Added to fix experiment_runner.py)
PERSONALITIES = ["balanced", "aggressive", "defensive", "random"]

# AI defaults
AI_DEPTH_DEFAULT = 4
AI_TIME_LIMIT_DEFAULT = 0.65
AI_DEPTH_MIN, AI_DEPTH_MAX = 2, 6
AI_TIME_MIN, AI_TIME_MAX = 0.2, 1.2
AI_TIME_STEP = 0.1

# Hint knobs
HINT_TIME_LIMIT = 0.22
HINT_DEPTH = 3
HINT_REFRESH = 0.35

# Splash + Transitions
SPLASH_SECONDS = 3.0
FADE_SECONDS = 0.45

GAME_TITLE = "DIAG-TACTICS ARENA"
SUBTITLE = "Minimax vs Alpha-Beta"

# Particle settings
PARTICLE_LIFETIME = 1.0
PARTICLE_SPEED = 100
PARTICLE_COLORS = [(255,200,100), (255,150,50), (255,100,50)]  # for win, etc.

# Stats file
STATS_FILE = "stats.json"