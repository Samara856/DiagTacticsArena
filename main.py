# main.py
import pygame
import time
import random
import math
import json
import os

from settings import *
from ui import *
from game_logic import *
from ai import (
    minimax_move, alphabeta_move, ai_choose_drop,
    explain_action, AIStats
)
from audio import SFX

# Helper for clamping
def clamp(value, low, high):
    return max(low, min(value, high))

# -------------------------
# Hazard logic
# -------------------------
def hazard_choose(board, diff_name, rng):
    conf = DIFFS[diff_name]
    k = conf["haz_count"]
    smart = conf["smart"]

    empties = [(r, c) for r in range(N) for c in range(N) if board[r][c] == EMPTY]
    if not empties:
        return set()

    def threat_cells_for_player(player):
        out = set()
        for seg in DIAG_SEGS:
            vals = [board[r][c] for r, c in seg]
            p = vals.count(player)
            o = vals.count(other(player))
            e = vals.count(EMPTY)
            if o == 0 and p >= 2 and e >= 1:
                for (r, c) in seg:
                    if board[r][c] == EMPTY:
                        out.add((r, c))
        return out

    hot = list(threat_cells_for_player(RED) | threat_cells_for_player(BLUE))
    ring = set()
    for (r, c) in hot:
        for dr, dc in DIRS4:
            nr, nc = r + dr, c + dc
            if inb(nr, nc) and board[nr][nc] == EMPTY:
                ring.add((nr, nc))

    pool_hot = [x for x in hot if board[x[0]][x[1]] == EMPTY]
    pool_ring = list(ring)

    used, out = set(), set()
    for _ in range(k):
        pick = None
        roll = rng.random()
        if roll < smart and pool_hot:
            pick = pool_hot.pop(rng.randrange(len(pool_hot)))
        elif roll < smart and pool_ring:
            pick = pool_ring.pop(rng.randrange(len(pool_ring)))
        else:
            tries = 0
            while tries < 40:
                cand = empties[rng.randrange(len(empties))]
                if cand not in used:
                    pick = cand
                    break
                tries += 1
        if pick is None:
            break
        used.add(pick)
        out.add(pick)
    return out


class Fade:
    def __init__(self):
        self.enabled = True
        self.active = False
        self.t = 0.0
        self.dur = FADE_SECONDS
        self.phase = "OUT"
        self.next_scene = None

    def start(self, next_scene):
        if not self.enabled:
            self.active = False
            self.next_scene = next_scene
            return
        self.active = True
        self.t = 0.0
        self.phase = "OUT"
        self.next_scene = next_scene

    def alpha(self, dt):
        if not self.active:
            return 0, False
        self.t += dt
        p = min(1.0, self.t / self.dur)
        if self.phase == "OUT":
            a = int(255 * p)
            done = (p >= 1.0)
            return a, done
        else:
            a = int(255 * (1.0 - p))
            done = (p >= 1.0)
            return a, done


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(GAME_TITLE)

        self.windowed = (max(MIN_W, 1320), max(MIN_H, 860))
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 16)
        self.font_b = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 34, bold=True)

        # audio
        self.sfx = SFX()

        # scenes
        self.scene = "SPLASH"
        self.menu_tab = "HOME"
        self.splash_start = time.perf_counter()
        self.splash_done = False

        # fade
        self.fade = Fade()
        self.fade.enabled = True

        # menu settings
        self.mode = "AGENT_VS_AGENT"   # "AGENT_VS_AGENT", "HUMAN_VS_AI", "HUMAN_VS_HUMAN"
        self.human_side = RED
        self.diff = "MEDIUM"
        self.best_of = 1                # 1, 3, or 5 games to win a match
        self.sidebar_on = True

        # runtime editable AI settings
        self.ai_depth = AI_DEPTH_DEFAULT
        self.ai_time = AI_TIME_LIMIT_DEFAULT

        # pulse animation for start button and pruning panel
        self.pulse_timer = 0.0

        # stats
        self.stats = self.load_stats()
        self.achievements = set(self.stats.get("achievements", []))
        self.notification = None  # (text, timer)

        # series tracking
        self.series_wins = {RED: 0, BLUE: 0}
        self.series_winner = EMPTY

        self.reset_match()

    def load_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"total_games": 0, "red_wins": 0, "blue_wins": 0, "achievements": []}

    def save_stats(self):
        self.stats["achievements"] = list(self.achievements)
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def show_notification(self, text, duration=3.0):
        self.notification = (text, duration)

    def check_achievements(self, winner):
        if winner == RED:
            if self.stats["red_wins"] == 0:
                if "first_red_win" not in self.achievements:
                    self.achievements.add("first_red_win")
                    self.show_notification("🏆 Achievement: First Red Victory!")
        elif winner == BLUE:
            if self.stats["blue_wins"] == 0:
                if "first_blue_win" not in self.achievements:
                    self.achievements.add("first_blue_win")
                    self.show_notification("🏆 Achievement: First Blue Victory!")

        if self.stats["total_games"] == 1:
            if "first_game" not in self.achievements:
                self.achievements.add("first_game")
                self.show_notification("🏆 Achievement: First Game Played!")
        elif self.stats["total_games"] == 10:
            if "ten_games" not in self.achievements:
                self.achievements.add("ten_games")
                self.show_notification("🏆 Achievement: 10 Games Played!")

    def request_scene(self, next_scene):
        if self.fade.enabled:
            self.fade.start(next_scene)
        else:
            self.scene = next_scene

    def reset_match(self, keep_series=False):
        """Reset the board and turn, but optionally keep series wins."""
        self.rng = random.Random(int(time.time() * 1000) ^ 0xC0DE)
        self.board = [[EMPTY for _ in range(N)] for _ in range(N)]
        self.hazards = hazard_choose(self.board, self.diff, self.rng)

        self.turn = RED
        self.phase = "DROP"
        self.drop_count = {RED: 0, BLUE: 0}
        self.max_drop = 4

        self.paused = False
        self.step_once = False
        self.speed = 1.0

        self.selected = None
        self.valid_targets = set()

        self.last_move = "—"
        self.last_haz = "—"
        self.last_ai = None

        self.winner = EMPTY
        self.win_cells = []

        self.anim = None
        self.anim_q = []
        self.ai_timer = 0.0
        self.ai_interval = 0.45

        # hint
        self.hint_timer = 0.0
        self.hint_text = "—"
        self.hint_reasons = []
        self.hint_target_cell = None
        self.hint_drop_col = None

        if not keep_series:
            self.series_wins = {RED: 0, BLUE: 0}
            self.series_winner = EMPTY

    def is_human_turn(self):
        """Return True if current player is human (should receive hints)."""
        if self.mode == "HUMAN_VS_HUMAN":
            return True
        elif self.mode == "HUMAN_VS_AI":
            return self.turn == self.human_side
        else:
            return False

    def layout(self):
        w, h = self.screen.get_size()
        w = max(w, MIN_W)
        h = max(h, MIN_H)
        sidebar_w = SIDEBAR_W if self.sidebar_on else 0
        board_w = w - sidebar_w

        avail_w = board_w - PAD * 2
        avail_h = h - TOPBAR_H - PAD * 2
        tile = int(min(avail_w / N, avail_h / N))
        tile = max(34, tile)

        gx = PAD + (avail_w - tile * N) // 2
        gy = TOPBAR_H + PAD + (avail_h - tile * N) // 2
        return w, h, board_w, sidebar_w, tile, gx, gy

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed, pygame.RESIZABLE)

    def handle_resize(self, w, h):
        w = max(MIN_W, w)
        h = max(MIN_H, h)
        self.windowed = (w, h)
        if not self.fullscreen:
            self.screen = pygame.display.set_mode(self.windowed, pygame.RESIZABLE)

    # -------------------------
    # mechanics
    # -------------------------
    def check_win(self):
        w, cells = winner_diagonal(self.board)
        if w != EMPTY:
            self.winner = w
            self.win_cells = cells
            # Update series
            self.series_wins[w] += 1
            needed = (self.best_of + 1) // 2
            if self.series_wins[w] >= needed:
                self.series_winner = w
            # stats (global)
            self.stats["total_games"] += 1
            if w == RED:
                self.stats["red_wins"] += 1
            else:
                self.stats["blue_wins"] += 1
            self.check_achievements(w)
            self.save_stats()
            # Change scene to WIN (we'll handle overlay)
            self.scene = "WIN"
            self.sfx.win()

    def relocate_hazards(self):
        self.hazards = hazard_choose(self.board, self.diff, self.rng)
        self.last_haz = "HAZARD -> " + ", ".join([f"({r+1},{c+1})" for r, c in sorted(self.hazards)])

    def end_turn(self):
        self.check_win()
        if self.scene == "WIN":
            return
        self.relocate_hazards()
        self.turn = other(self.turn)

        if self.phase == "DROP":
            if self.drop_count[RED] >= self.max_drop and self.drop_count[BLUE] >= self.max_drop:
                self.phase = "MOVE"
                self.last_move = "DROP finished → MOVE phase started"
                self.selected = None
                self.valid_targets.clear()

        self.hint_text = "—"
        self.hint_reasons = []
        self.hint_target_cell = None
        self.hint_drop_col = None
        self.hint_timer = 0.0

    def do_drop(self, col, player):
        nb, land = drop_in_column(self.board, col, player, self.hazards)
        if nb is None:
            return False
        self.board = nb
        self.drop_count[player] += 1
        self.last_move = f"{'RED' if player==RED else 'BLUE'} DROP col {col+1} -> ({land[0]+1},{land[1]+1})"
        self.anim_q.append({"type": "DROP", "dur": 0.22, "col": col, "to": land, "p": player, "t": 0.0})
        self.sfx.drop()
        self.end_turn()
        return True

    def do_move(self, mv, player, stats=None):
        self.board = apply_move(self.board, mv)
        self.last_move = f"{'RED' if player==RED else 'BLUE'} MOVE {mv[1]}->{mv[2]}"
        self.last_ai = stats
        self.anim_q.append({"type": "MOVE", "dur": 0.16, "frm": mv[1], "to": mv[2], "p": player, "t": 0.0})
        self.sfx.click()
        self.end_turn()

    def compute_valid_targets(self, src):
        self.valid_targets.clear()
        if src is None:
            return
        r, c = src
        if self.board[r][c] != self.turn:
            return
        for dr, dc in DIRS4:
            nr, nc = r + dr, c + dc
            if not inb(nr, nc):
                continue
            if (nr, nc) in self.hazards:
                continue
            if self.board[nr][nc] != EMPTY:
                continue
            self.valid_targets.add((nr, nc))

    def cell_from_mouse(self, mx, my, tile, gx, gy):
        c = (mx - gx) // tile
        r = (my - gy) // tile
        if 0 <= r < N and 0 <= c < N:
            return int(r), int(c)
        return None

    # -------------------------
    # AI turn
    # -------------------------
    def ai_take_turn(self):
        p = self.turn
        if self.phase == "DROP":
            col, _ = ai_choose_drop(self.board, p, self.hazards)
            if col is None:
                self.winner = other(p)
                self.scene = "WIN"
                self.sfx.win()
                return
            self.do_drop(col, p)
            return

        if p == RED:
            mv, st = minimax_move(self.board, p, self.hazards, self.ai_depth, self.ai_time)
        else:
            mv, st = alphabeta_move(self.board, p, self.hazards, self.ai_depth, self.ai_time)

        if mv is None:
            self.winner = other(p)
            self.scene = "WIN"
            self.sfx.win()
            return
        self.do_move(mv, p, st)

    # -------------------------
    # Human hint
    # -------------------------
    def update_human_hint(self, dt):
        if not self.is_human_turn() or self.paused:
            return
        if self.anim is not None or self.anim_q:
            return

        self.hint_timer -= dt
        if self.hint_timer > 0:
            return
        self.hint_timer = HINT_REFRESH

        p = self.turn
        if self.phase == "DROP":
            col, _ = ai_choose_drop(self.board, p, self.hazards)
            if col is None:
                self.hint_text = "No legal drop found."
                self.hint_drop_col = None
                self.hint_reasons = []
                return
            self.hint_text = f"Suggestion: DROP column {col+1}"
            self.hint_drop_col = col
            self.hint_target_cell = None
            self.hint_reasons = explain_action(self.board, p, self.hazards, "DROP", col)
            return

        if p == RED:
            mv, _ = minimax_move(self.board, p, self.hazards, HINT_DEPTH, HINT_TIME_LIMIT)
            algo = "Minimax"
        else:
            mv, _ = alphabeta_move(self.board, p, self.hazards, HINT_DEPTH, HINT_TIME_LIMIT)
            algo = "Alpha-Beta"

        if mv is None:
            self.hint_text = f"Suggestion ({algo}): No legal move"
            self.hint_reasons = []
            self.hint_target_cell = None
            self.hint_drop_col = None
            return

        frm, to = mv[1], mv[2]
        self.hint_text = f"Suggestion ({algo}): {frm} -> {to}"
        self.hint_target_cell = to
        self.hint_drop_col = None
        self.hint_reasons = explain_action(self.board, p, self.hazards, "MOVE", mv)

    # -------------------------
    # DRAW: Splash
    # -------------------------
    def draw_splash(self):
        self.screen.fill(BG)
        w, h = self.screen.get_size()
        t = time.perf_counter() - self.splash_start
        pulse = 0.5 + 0.5 * (1 + math.sin(t * 3.2)) / 2
        glow = int(140 + 80 * pulse)

        title = self.font_big.render(GAME_TITLE, True, (glow, glow, glow))
        sub = self.font_b.render(SUBTITLE, True, MUTED)

        self.screen.blit(title, ((w - title.get_width()) // 2, h // 2 - 54))
        self.screen.blit(sub, ((w - sub.get_width()) // 2, h // 2 + 10))

        tip = self.font.render("Loading…", True, MUTED)
        self.screen.blit(tip, (w - tip.get_width() - 20, h - 30))

    # -------------------------
    # Enhanced Pruning Visual Panel
    # -------------------------
    def draw_pruning_panel(self, x0, y0, w, h, stats):
        """Draw a visually appealing panel showing pruning intensity and a mini search tree."""
        # Panel background
        pygame.draw.rect(self.screen, PANEL2, (x0, y0, w, h), border_radius=12)
        pygame.draw.rect(self.screen, (100,80,60), (x0+2, y0+2, w-4, 20), border_radius=10)  # top bar

        # Title with player color accent
        if stats and hasattr(stats, 'algo'):
            title_color = RED_C if "Minimax" in stats.algo else BLUE_C
        else:
            title_color = ACC
        title = self.font_b.render("🔍 Alpha-Beta Pruning", True, title_color)
        self.screen.blit(title, (x0+10, y0+5))

        if not stats:
            self.screen.blit(self.font.render("— No data —", True, MUTED), (x0+10, y0+40))
            return

        # Compute pruning intensity
        nodes = max(1, stats.nodes)
        prunes = max(0, stats.prunes)
        intensity = clamp(prunes / max(1, prunes + nodes/6), 0.0, 1.0)

        # Intensity meter
        bar_x, bar_y = x0+10, y0+32
        bar_w, bar_h = w-20, 16
        # background
        pygame.draw.rect(self.screen, (30,30,40), (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        # filled gradient
        fill_w = int(bar_w * intensity)
        for i in range(fill_w):
            t = i / max(1, fill_w)
            if t < 0.5:
                r = int(255 * (t*2))
                g = 255
                b = 0
            else:
                r = 255
                g = int(255 * (1 - (t-0.5)*2))
                b = 0
            pygame.draw.rect(self.screen, (r,g,b), (bar_x + i, bar_y, 1, bar_h))
        # label
        self.screen.blit(self.font.render(f"Pruning intensity: {intensity*100:.0f}%", True, TXT), (bar_x, bar_y+bar_h+2))

        # Tree dimensions
        tree_y_start = bar_y + bar_h + 20
        tree_height = h - (tree_y_start - y0) - 50  # leave room for legend and footer
        if tree_height < 60:
            tree_height = 60  # minimum

        level_h = tree_height // 3
        node_r = 8

        # Positions
        tree_center_x = x0 + w // 2
        root_y = tree_y_start
        l1_y = root_y + level_h
        l2_y = l1_y + level_h

        root = (tree_center_x, root_y)
        l1 = [
            (tree_center_x - w//6, l1_y),
            (tree_center_x, l1_y),
            (tree_center_x + w//6, l1_y)
        ]
        l2 = []
        for (px, py) in l1:
            l2.append((px - 30, l2_y))
            l2.append((px + 30, l2_y))

        # Determine pruned edges
        total_edges = 9
        pruned_count = int(total_edges * intensity)
        edges = []
        for p in l1:
            edges.append((root, p))
        for i, p in enumerate(l1):
            edges.append((p, l2[2*i]))
            edges.append((p, l2[2*i+1]))

        # Draw edges
        for idx, (a, b) in enumerate(edges):
            if idx < pruned_count:
                pygame.draw.line(self.screen, (255,80,80), a, b, 2)
                mx = (a[0]+b[0])//2
                my = (a[1]+b[1])//2
                pygame.draw.line(self.screen, (255,0,0), (mx-6, my-6), (mx+6, my+6), 3)
                pygame.draw.line(self.screen, (255,0,0), (mx-6, my+6), (mx+6, my-6), 3)
            else:
                pygame.draw.line(self.screen, (100,255,255), a, b, 2)

        # Draw nodes
        # Root with pulse
        pulse = 0.5 + 0.5 * math.sin(self.pulse_timer * 3.0)
        glow_size = int(node_r * (1.2 + 0.3 * pulse))
        glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255,255,255, 80), (glow_size, glow_size), glow_size)
        self.screen.blit(glow_surf, (root[0]-glow_size, root[1]-glow_size))
        pygame.draw.circle(self.screen, (255,255,200), root, node_r)
        pygame.draw.circle(self.screen, (0,0,0), root, node_r, 2)

        for p in l1:
            pygame.draw.circle(self.screen, (220,220,230), p, node_r-1)
            pygame.draw.circle(self.screen, (0,0,0), p, node_r-1, 2)
        for p in l2:
            pygame.draw.circle(self.screen, (200,200,210), p, node_r-2)
            pygame.draw.circle(self.screen, (0,0,0), p, node_r-2, 2)

        # Legend (placed below tree, above footer)
        leg_y = l2_y + 20
        self.screen.blit(self.font.render("🌿 Visited", True, (100,255,255)), (x0+10, leg_y))
        self.screen.blit(self.font.render("❌ Pruned", True, (255,80,80)), (x0+100, leg_y))

        # Footer with stats (at bottom)
        foot_y = y0 + h - 18
        self.screen.blit(self.font.render(f"Nodes: {nodes} | Prunes: {prunes}", True, MUTED), (x0+10, foot_y))

    # -------------------------
    # DRAW: Menu and Play
    # -------------------------
    def draw_menu_home(self):
        w, h = self.screen.get_size()
        draw_crafting_background(self.screen, (0, 0, w, h), (70, 60, 40), (60, 50, 30), cell_size=48)

        mx, my = pygame.mouse.get_pos()
        self.tab_rects = draw_top_tabs(self.screen, self.font_b, w, self.menu_tab, mx, my)

        title = self.font_big.render(GAME_TITLE, True, TXT)
        title_shadow = self.font_big.render(GAME_TITLE, True, (50, 40, 30))
        self.screen.blit(title_shadow, (24, 76))
        self.screen.blit(title, (22, 74))

        subtitle = self.font.render("Choose mode, best-of, difficulty, then START.", True, MUTED)
        self.screen.blit(subtitle, (22, 112))

        # --- Dynamic panel sizing (rules note removed) ---
        pw = 900
        # Sections height
        mode_height = 26 + 86
        human_side_height = 26 + 86 if self.mode == "HUMAN_VS_AI" else 0
        bestof_height = 26 + 86
        diff_height = 26 + 104
        buttons_height = 86 + 86  # start and quit rows
        total_content = mode_height + human_side_height + bestof_height + diff_height + buttons_height
        panel_padding = 40
        ph = total_content + panel_padding

        max_ph = h - 200
        if ph > max_ph:
            ph = max_ph

        px = (w - pw) // 2
        py = (h - ph) // 2 + 20
        draw_panel(self.screen, (px, py, pw, ph))

        x = px + 34
        y = py + 30

        # --- Mode ---
        self.screen.blit(self.font_b.render("Mode", True, TXT), (x, y));
        y += 26
        btn_w = 260
        spacing = 15
        self.btn_ava = (x, y, btn_w, 52)
        self.btn_hva = (x + btn_w + spacing, y, btn_w, 52)
        self.btn_hvh = (x + 2 * (btn_w + spacing), y, btn_w, 52)
        y += 86

        draw_button(self.screen, self.font_b, self.btn_ava, "Agent vs Agent",
                    hovered=hit(self.btn_ava, mx, my), active=(self.mode == "AGENT_VS_AGENT"), accent=True)
        draw_button(self.screen, self.font_b, self.btn_hva, "Human vs AI",
                    hovered=hit(self.btn_hva, mx, my), active=(self.mode == "HUMAN_VS_AI"), accent=True)
        draw_button(self.screen, self.font_b, self.btn_hvh, "Human vs Human",
                    hovered=hit(self.btn_hvh, mx, my), active=(self.mode == "HUMAN_VS_HUMAN"), accent=True)

        # --- Human side (conditional) ---
        if self.mode == "HUMAN_VS_AI":
            self.screen.blit(self.font_b.render("Human side (only Human vs AI)", True, TXT), (x, y));
            y += 26
            self.btn_hred = (x, y, 380, 52)
            self.btn_hblue = (x + 430, y, 380, 52)
            y += 86

            red_active = (self.human_side == RED)
            blue_active = (self.human_side == BLUE)
            draw_button(self.screen, self.font_b, self.btn_hred, "Human = RED",
                        hovered=hit(self.btn_hred, mx, my), active=red_active)
            draw_button(self.screen, self.font_b, self.btn_hblue, "Human = BLUE",
                        hovered=hit(self.btn_hblue, mx, my), active=blue_active)

        # --- Best of ---
        self.screen.blit(self.font_b.render("Best of", True, TXT), (x, y));
        y += 26
        self.btn_best1 = (x, y, 160, 52)
        self.btn_best3 = (x + 200, y, 160, 52)
        self.btn_best5 = (x + 400, y, 160, 52)
        y += 86

        draw_button(self.screen, self.font_b, self.btn_best1, "1 Game",
                    hovered=hit(self.btn_best1, mx, my), active=(self.best_of == 1))
        draw_button(self.screen, self.font_b, self.btn_best3, "3 Games",
                    hovered=hit(self.btn_best3, mx, my), active=(self.best_of == 3))
        draw_button(self.screen, self.font_b, self.btn_best5, "5 Games",
                    hovered=hit(self.btn_best5, mx, my), active=(self.best_of == 5))

        # --- Difficulty ---
        self.screen.blit(self.font_b.render("Difficulty (Hazard strength)", True, TXT), (x, y));
        y += 26
        self.btn_low = (x, y, 260, 52)
        self.btn_med = (x + 295, y, 260, 52)
        self.btn_hard = (x + 590, y, 260, 52)
        y += 104

        draw_button(self.screen, self.font_b, self.btn_low, "LOW",
                    hovered=hit(self.btn_low, mx, my), active=(self.diff == "LOW"))
        draw_button(self.screen, self.font_b, self.btn_med, "MEDIUM",
                    hovered=hit(self.btn_med, mx, my), active=(self.diff == "MEDIUM"))
        draw_button(self.screen, self.font_b, self.btn_hard, "HARD",
                    hovered=hit(self.btn_hard, mx, my), active=(self.diff == "HARD"))

        # --- Start and Quit ---
        self.btn_play = (x, y, 810, 62);
        y += 86
        self.btn_quit = (x, y, 810, 62);
        y += 86

        draw_button(self.screen, self.font_big, self.btn_play, "START GAME",
                    hovered=hit(self.btn_play, mx, my), accent=True)
        draw_button(self.screen, self.font_big, self.btn_quit, "QUIT",
                    hovered=hit(self.btn_quit, mx, my))
    def draw_menu_settings(self):
        w, h = self.screen.get_size()
        draw_crafting_background(self.screen, (0, 0, w, h), (70, 60, 40), (60, 50, 30), cell_size=48)
        mx, my = pygame.mouse.get_pos()
        self.tab_rects = draw_top_tabs(self.screen, self.font_b, w, self.menu_tab, mx, my)

        title = self.font_big.render("SETTINGS", True, TXT)
        title_shadow = self.font_big.render("SETTINGS", True, (50, 40, 30))
        self.screen.blit(title_shadow, (24, 76))
        self.screen.blit(title, (22, 74))
        self.screen.blit(self.font.render("Tune AI, sound, and transitions.", True, MUTED), (22, 112))

        pw, ph = 900, 460
        px, py = (w // 2 - pw // 2, 190)
        draw_panel(self.screen, (px, py, pw, ph))

        x = px + 40
        y = py + 40

        draw_slider_row(self.screen, self.font_b, "AI Search Depth", f"{self.ai_depth}", x, y, pw - 80)
        self.btn_depth_minus = (x + 620, y - 8, 90, 36)
        self.btn_depth_plus = (x + 720, y - 8, 90, 36)
        draw_button(self.screen, self.font_b, self.btn_depth_minus, "-", hovered=hit(self.btn_depth_minus, mx, my))
        draw_button(self.screen, self.font_b, self.btn_depth_plus, "+", hovered=hit(self.btn_depth_plus, mx, my))
        y += 76

        draw_slider_row(self.screen, self.font_b, "AI Think Time (seconds)", f"{self.ai_time:.1f}", x, y, pw - 80)
        self.btn_time_minus = (x + 620, y - 8, 90, 36)
        self.btn_time_plus = (x + 720, y - 8, 90, 36)
        draw_button(self.screen, self.font_b, self.btn_time_minus, "-", hovered=hit(self.btn_time_minus, mx, my))
        draw_button(self.screen, self.font_b, self.btn_time_plus, "+", hovered=hit(self.btn_time_plus, mx, my))
        y += 76

        draw_slider_row(self.screen, self.font_b, "Sound Effects", "ON" if self.sfx.enabled else "OFF", x, y, pw - 80)
        self.btn_sound = (x + 620, y - 8, 190, 36)
        draw_button(self.screen, self.font_b, self.btn_sound, "TOGGLE", hovered=hit(self.btn_sound, mx, my), accent=True)
        y += 76

        draw_slider_row(self.screen, self.font_b, "Fade Transitions", "ON" if self.fade.enabled else "OFF", x, y, pw - 80)
        self.btn_fade = (x + 620, y - 8, 190, 36)
        draw_button(self.screen, self.font_b, self.btn_fade, "TOGGLE", hovered=hit(self.btn_fade, mx, my), accent=True)
        y += 90

        info = "Tip: Higher depth/time = stronger AI but slower turns."
        self.screen.blit(self.font.render(info, True, MUTED), (x, y))

    def draw_menu_about(self):
        w, h = self.screen.get_size()
        draw_crafting_background(self.screen, (0, 0, w, h), (70, 60, 40), (60, 50, 30), cell_size=48)
        mx, my = pygame.mouse.get_pos()
        self.tab_rects = draw_top_tabs(self.screen, self.font_b, w, self.menu_tab, mx, my)

        title = self.font_big.render("ABOUT", True, TXT)
        title_shadow = self.font_big.render("ABOUT", True, (50, 40, 30))
        self.screen.blit(title_shadow, (24, 76))
        self.screen.blit(title, (22, 74))

        text = (
            "Diag-Tactics Arena is a spectator-friendly AI project.\n"
            "RED uses Minimax, BLUE uses Alpha-Beta pruning.\n"
            "Hazards relocate each turn to block easy wins.\n"
            "Goal: make a 4-block DIAGONAL line. No capture.\n"
            "\n"
            f"📊 STATISTICS\n"
            f"Total games: {self.stats['total_games']}\n"
            f"Red wins: {self.stats['red_wins']}  ({self.stats['red_wins']/(self.stats['total_games'] or 1)*100:.1f}%)\n"
            f"Blue wins: {self.stats['blue_wins']}  ({self.stats['blue_wins']/(self.stats['total_games'] or 1)*100:.1f}%)\n"
            f"Achievements unlocked: {len(self.achievements)}"
        )
        y = 130
        for line in text.split("\n"):
            self.screen.blit(self.font.render(line, True, MUTED), (22, y))
            y += 22

    def draw_play(self):
        mx, my = pygame.mouse.get_pos()
        w, h, board_w, sidebar_w, tile, gx, gy = self.layout()

        # background
        self.screen.fill(BG)

        # board panel
        draw_panel(self.screen, (gx - 10, gy - 10, tile * N + 20, tile * N + 20), shadow=True)

        # tiles
        for r in range(N):
            for c in range(N):
                rect = (gx + c * tile, gy + r * tile, tile, tile)
                checker = (r + c) % 2
                draw_tile(self.screen, rect, checker)

        # hazards
        for r, c in self.hazards:
            cx = gx + c * tile + tile // 2
            cy = gy + r * tile + tile // 2
            draw_hazard(self.screen, cx, cy, tile)

        # tokens
        for r in range(N):
            for c in range(N):
                p = self.board[r][c]
                if p == EMPTY:
                    continue
                cx = gx + c * tile + tile // 2
                cy = gy + r * tile + tile // 2
                glow = False
                if self.anim and self.anim["type"] == "MOVE":
                    if (r, c) == self.anim["frm"] or (r, c) == self.anim["to"]:
                        glow = True
                draw_token(self.screen, cx, cy, tile, p, glow)

        # selection outlines
        if self.selected:
            sr, sc = self.selected
            rect = (gx + sc * tile, gy + sr * tile, tile, tile)
            draw_hint_outline(self.screen, rect, "select")
        for tr, tc in self.valid_targets:
            rect = (gx + tc * tile, gy + tr * tile, tile, tile)
            draw_hint_outline(self.screen, rect, "good")

        # hint
        if self.hint_drop_col is not None and self.phase == "DROP":
            draw_drop_arrow(self.screen, gx, gy, tile, self.hint_drop_col)
        if self.hint_target_cell:
            hr, hc = self.hint_target_cell
            rect = (gx + hc * tile, gy + hr * tile, tile, tile)
            draw_hint_outline(self.screen, rect, "suggest")

        # win cells
        if self.winner != EMPTY:
            for r, c in self.win_cells:
                rect = (gx + c * tile, gy + r * tile, tile, tile)
                draw_hint_outline(self.screen, rect, "win")

        # top bar
        top_rect = (0, 0, w, TOPBAR_H)
        pygame.draw.rect(self.screen, PANEL, top_rect)
        pygame.draw.line(self.screen, GRIDLINE, (0, TOPBAR_H), (w, TOPBAR_H), 2)

        turn_text = f"Turn: {'RED' if self.turn == RED else 'BLUE'}  Phase: {self.phase}  {'(PAUSED)' if self.paused else ''}"
        self.screen.blit(self.font_b.render(turn_text, True, TXT), (PAD, 12))
        self.screen.blit(self.font.render(f"Speed: {self.speed:.1f}x", True, MUTED), (PAD, 40))

        # top right buttons
        bx = w - 500
        self.btn_pause = (bx, 10, 100, 32)
        self.btn_step = (bx + 110, 10, 100, 32)
        self.btn_restart = (bx + 220, 10, 120, 32)
        self.btn_back = (bx + 350, 10, 120, 32)

        draw_button(self.screen, self.font_b, self.btn_pause, "PAUSE" if not self.paused else "RESUME",
                    hovered=hit(self.btn_pause, mx, my))
        draw_button(self.screen, self.font_b, self.btn_step, "STEP",
                    hovered=hit(self.btn_step, mx, my))
        draw_button(self.screen, self.font_b, self.btn_restart, "RESTART",
                    hovered=hit(self.btn_restart, mx, my))
        draw_button(self.screen, self.font_b, self.btn_back, "MENU",
                    hovered=hit(self.btn_back, mx, my))

        # speed buttons
        self.btn_spd_down = (bx - 160, 10, 36, 32)
        self.btn_spd_up = (bx - 120, 10, 36, 32)
        draw_button(self.screen, self.font_b, self.btn_spd_down, "-", hovered=hit(self.btn_spd_down, mx, my))
        draw_button(self.screen, self.font_b, self.btn_spd_up, "+", hovered=hit(self.btn_spd_up, mx, my))

        # fullscreen & sidebar toggle
        self.btn_full = (bx - 210, 10, 40, 32)
        self.btn_side = (bx - 270, 10, 50, 32)
        draw_button(self.screen, self.font_b, self.btn_full, "F11", hovered=hit(self.btn_full, mx, my))
        draw_button(self.screen, self.font_b, self.btn_side, "SIDE", hovered=hit(self.btn_side, mx, my),
                    active=self.sidebar_on)

        # --- Sidebar with enhanced analytics ---
        if self.sidebar_on:
            sx = board_w
            panel_rect = (sx, TOPBAR_H, sidebar_w, h - TOPBAR_H)
            draw_panel(self.screen, panel_rect)

            pad = PAD
            x = sx + pad
            y = TOPBAR_H + pad

            # AI Legend (adjust text based on mode)
            self.screen.blit(self.font_b.render("⚔️ AI Legend", True, TXT), (x, y)); y += 26
            if self.mode == "HUMAN_VS_HUMAN":
                self.screen.blit(self.font.render("🔴 Human (Red) gets Minimax hints", True, RED_C), (x + 10, y)); y += 20
                self.screen.blit(self.font.render("🔵 Human (Blue) gets Alpha-Beta hints", True, BLUE_C), (x + 10, y)); y += 24
            else:
                self.screen.blit(self.font.render("🔴 Redstone → Minimax", True, RED_C), (x + 10, y)); y += 20
                self.screen.blit(self.font.render("🔵 Lapis    → Alpha-Beta", True, BLUE_C), (x + 10, y)); y += 24

            # Game State (include series score)
            self.screen.blit(self.font_b.render("📦 Game State", True, TXT), (x, y)); y += 26
            turn_str = f"Turn: {'RED' if self.turn == RED else 'BLUE'} | Phase: {self.phase}"
            self.screen.blit(self.font.render(turn_str, True, MUTED), (x + 10, y)); y += 20
            drops_str = f"Drops: R={self.drop_count[RED]}/{self.max_drop}  B={self.drop_count[BLUE]}/{self.max_drop}"
            self.screen.blit(self.font.render(drops_str, True, MUTED), (x + 10, y)); y += 20
            self.screen.blit(self.font.render(f"Lava: {len(self.hazards)} cells", True, MUTED), (x + 10, y)); y += 20
            series_str = f"Series: R={self.series_wins[RED]}  B={self.series_wins[BLUE]}  (Best of {self.best_of})"
            self.screen.blit(self.font.render(series_str, True, ACC), (x + 10, y)); y += 24

            # Hazard Log
            self.screen.blit(self.font_b.render("🌋 Lava Log", True, TXT), (x, y)); y += 26
            for line in wrap_text(self.font, self.last_haz, sidebar_w - pad * 2 - 20):
                self.screen.blit(self.font.render(line, True, MUTED), (x + 10, y)); y += 18
            y += 6

            # Last Move
            self.screen.blit(self.font_b.render("⛏️ Last Move", True, TXT), (x, y)); y += 26
            for line in wrap_text(self.font, self.last_move, sidebar_w - pad * 2 - 20):
                self.screen.blit(self.font.render(line, True, TXT), (x + 10, y)); y += 18
            y += 6

            # Search & Decision (only if AI played last)
            self.screen.blit(self.font_b.render("🧠 Search & Decision", True, TXT), (x, y)); y += 26
            if self.last_ai:
                st = self.last_ai
                self.screen.blit(self.font.render(f"Algo: {st.algo}", True, MUTED), (x + 10, y)); y += 18
                self.screen.blit(self.font.render(f"Depth: {st.depth} | Nodes: {st.nodes:,}", True, MUTED),
                                 (x + 10, y)); y += 18
                self.screen.blit(
                    self.font.render(f"Prunes: {st.prunes:,} | Time: {st.time_spent * 1000:.0f} ms", True, MUTED),
                    (x + 10, y)); y += 18
                self.screen.blit(self.font.render(f"Best score: {st.best_score}", True, MUTED), (x + 10, y)); y += 24

                if st.top:
                    self.screen.blit(self.font_b.render("🏆 Top 3 Picks", True, TXT), (x, y)); y += 24
                    for i, (score, mv) in enumerate(st.top[:3], 1):
                        mv_str = move_to_str(mv)
                        color = GOOD if i == 1 else MUTED
                        line = f"{i}) {mv_str}  (score {score})"
                        for wl in wrap_text(self.font, line, sidebar_w - pad * 2 - 20):
                            self.screen.blit(self.font.render(wl, True, color), (x + 10, y)); y += 18
            else:
                self.screen.blit(self.font.render("—", True, MUTED), (x + 10, y)); y += 18
                y += 10

            # Hint
            self.screen.blit(self.font_b.render("💡 Hint", True, TXT), (x, y)); y += 26
            self.screen.blit(self.font.render(self.hint_text, True, SUGG), (x + 10, y)); y += 20
            for reason in self.hint_reasons:
                self.screen.blit(self.font.render("• " + reason, True, MUTED), (x + 20, y)); y += 18

            # After hint, place the enhanced pruning panel at the bottom
            bottom_panel_h = 220
            y_bottom = h - TOPBAR_H - bottom_panel_h - 10
            self.draw_pruning_panel(x, y_bottom, sidebar_w - pad * 2, bottom_panel_h, self.last_ai)

        # Draw notification if active
        if self.notification:
            text, timer = self.notification
            notif_surf = self.font_b.render(text, True, ACC)
            notif_rect = notif_surf.get_rect(center=(w//2, TOPBAR_H + 40))
            bg_rect = notif_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (30,30,30), bg_rect, border_radius=8)
            pygame.draw.rect(self.screen, ACC, bg_rect, 2, border_radius=8)
            self.screen.blit(notif_surf, notif_rect)

    def draw_win_overlay(self):
        mx, my = pygame.mouse.get_pos()
        w, h = self.screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Determine if series is over
        needed = (self.best_of + 1) // 2
        series_over = (self.series_wins[RED] >= needed or self.series_wins[BLUE] >= needed)
        if series_over:
            msg = f"{'RED' if self.series_winner == RED else 'BLUE'} WINS THE SERIES!"
        else:
            msg = f"{'RED' if self.winner == RED else 'BLUE'} WINS GAME!"

        txt = self.font_big.render(msg, True, WHITE)
        tw, th = txt.get_size()
        px = (w - tw) // 2
        py = h // 2 - 80

        # shadow
        self.screen.blit(txt, (px + 4, py + 4))
        self.screen.blit(txt, (px, py))

        # Series score
        score_txt = self.font_b.render(f"Series: Red {self.series_wins[RED]}  -  {self.series_wins[BLUE]} Blue", True, WHITE)
        score_rect = score_txt.get_rect(center=(w//2, py + 50))
        self.screen.blit(score_txt, score_rect)

        # Buttons
        btn_w, btn_h = 200, 60
        if series_over or self.best_of == 1:
            # Show only Play Again, Menu, Quit
            self.win_play = (w // 2 - btn_w - 20, h // 2 + 20, btn_w, btn_h)
            self.win_menu = (w // 2 + 20, h // 2 + 20, btn_w, btn_h)
            self.win_quit = (w // 2 - btn_w // 2, h // 2 + 100, btn_w, btn_h)

            draw_button(self.screen, self.font_big, self.win_play, "PLAY AGAIN",
                        hovered=hit(self.win_play, mx, my), accent=True)
            draw_button(self.screen, self.font_big, self.win_menu, "MENU",
                        hovered=hit(self.win_menu, mx, my), accent=True)
            draw_button(self.screen, self.font_big, self.win_quit, "QUIT",
                        hovered=hit(self.win_quit, mx, my))
        else:
            # Show Next Game, Menu, Quit
            self.win_next = (w // 2 - btn_w - 20, h // 2 + 20, btn_w, btn_h)
            self.win_menu = (w // 2 + 20, h // 2 + 20, btn_w, btn_h)
            self.win_quit = (w // 2 - btn_w // 2, h // 2 + 100, btn_w, btn_h)

            draw_button(self.screen, self.font_big, self.win_next, "NEXT GAME",
                        hovered=hit(self.win_next, mx, my), accent=True)
            draw_button(self.screen, self.font_big, self.win_menu, "MENU",
                        hovered=hit(self.win_menu, mx, my), accent=True)
            draw_button(self.screen, self.font_big, self.win_quit, "QUIT",
                        hovered=hit(self.win_quit, mx, my))

    def apply_fade_overlay(self, alpha):
        if alpha <= 0:
            return
        w, h = self.screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

    def run(self):
        running = True
        while running:
            raw_dt = self.clock.tick(FPS) / 1000.0
            dt = min(raw_dt, 0.04) * self.speed
            self.pulse_timer += dt
            mx, my = pygame.mouse.get_pos()

            # Update notification timer
            if self.notification:
                text, timer = self.notification
                timer -= raw_dt
                if timer <= 0:
                    self.notification = None
                else:
                    self.notification = (text, timer)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

                elif e.type == pygame.VIDEORESIZE:
                    self.handle_resize(e.w, e.h)

                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.scene == "PLAY":
                            self.request_scene("MENU")
                            self.menu_tab = "HOME"
                        else:
                            running = False
                    elif e.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif e.key == pygame.K_SPACE and self.scene == "PLAY":
                        self.paused = not self.paused
                        self.sfx.click()
                    elif e.key == pygame.K_n and self.scene == "PLAY":
                        self.step_once = True
                        self.paused = True
                        self.sfx.click()
                    elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.speed = max(0.3, self.speed - 0.2)
                        self.sfx.click()
                    elif e.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self.speed = min(3.0, self.speed + 0.2)
                        self.sfx.click()

                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.scene == "MENU":
                        for tab, rect in getattr(self, "tab_rects", {}).items():
                            if hit(rect, mx, my):
                                t = str(tab).strip().upper()
                                if t in ("HOME", "SETTINGS", "ABOUT"):
                                    self.menu_tab = t
                                else:
                                    if "HOME" in t:
                                        self.menu_tab = "HOME"
                                    elif "SET" in t:
                                        self.menu_tab = "SETTINGS"
                                    elif "ABOUT" in t:
                                        self.menu_tab = "ABOUT"
                                self.sfx.click()
                                break

                        if self.menu_tab == "HOME":
                            # Mode buttons
                            if hit(self.btn_ava, mx, my): self.mode = "AGENT_VS_AGENT"; self.sfx.click()
                            if hit(self.btn_hva, mx, my): self.mode = "HUMAN_VS_AI"; self.sfx.click()
                            if hit(self.btn_hvh, mx, my): self.mode = "HUMAN_VS_HUMAN"; self.sfx.click()

                            # Human side (only if mode is HUMAN_VS_AI and buttons exist)
                            if self.mode == "HUMAN_VS_AI" and hasattr(self, 'btn_hred'):
                                if hit(self.btn_hred, mx, my): self.human_side = RED; self.sfx.click()
                                if hit(self.btn_hblue, mx, my): self.human_side = BLUE; self.sfx.click()

                            # Best of
                            if hit(self.btn_best1, mx, my): self.best_of = 1; self.sfx.click()
                            if hit(self.btn_best3, mx, my): self.best_of = 3; self.sfx.click()
                            if hit(self.btn_best5, mx, my): self.best_of = 5; self.sfx.click()

                            # Difficulty
                            if hit(self.btn_low, mx, my): self.diff = "LOW"; self.sfx.click()
                            if hit(self.btn_med, mx, my): self.diff = "MEDIUM"; self.sfx.click()
                            if hit(self.btn_hard, mx, my): self.diff = "HARD"; self.sfx.click()

                            # Start / Quit
                            if hit(self.btn_play, mx, my):
                                self.sfx.click()
                                self.reset_match(keep_series=False)  # new series
                                self.request_scene("PLAY")
                            if hit(self.btn_quit, mx, my):
                                self.sfx.click()
                                running = False

                        elif self.menu_tab == "SETTINGS":
                            if not hasattr(self, "btn_depth_minus"):
                                continue
                            if hit(self.btn_depth_minus, mx, my):
                                self.ai_depth = max(AI_DEPTH_MIN, self.ai_depth - 1)
                                self.sfx.click()
                            if hit(self.btn_depth_plus, mx, my):
                                self.ai_depth = min(AI_DEPTH_MAX, self.ai_depth + 1)
                                self.sfx.click()
                            if hit(self.btn_time_minus, mx, my):
                                self.ai_time = max(AI_TIME_MIN, round(self.ai_time - AI_TIME_STEP, 1))
                                self.sfx.click()
                            if hit(self.btn_time_plus, mx, my):
                                self.ai_time = min(AI_TIME_MAX, round(self.ai_time + AI_TIME_STEP, 1))
                                self.sfx.click()
                            if hit(self.btn_sound, mx, my):
                                self.sfx.enabled = not self.sfx.enabled
                                self.sfx.click()
                            if hit(self.btn_fade, mx, my):
                                self.fade.enabled = not self.fade.enabled
                                self.sfx.click()

                    elif self.scene == "WIN":
                        # Determine which buttons exist
                        if hasattr(self, 'win_next'):
                            if hit(self.win_next, mx, my):
                                self.sfx.click()
                                self.reset_match(keep_series=True)
                                self.request_scene("PLAY")
                                continue
                        if hasattr(self, 'win_play'):
                            if hit(self.win_play, mx, my):
                                self.sfx.click()
                                self.reset_match(keep_series=False)
                                self.request_scene("PLAY")
                                continue
                        if hit(self.win_menu, mx, my):
                            self.sfx.click()
                            self.request_scene("MENU")
                            self.menu_tab = "HOME"
                            continue
                        if hit(self.win_quit, mx, my):
                            self.sfx.click()
                            running = False
                            continue

                    elif self.scene == "PLAY":
                        w, h, board_w, sidebar_w, tile, gx, gy = self.layout()

                        if hit(self.btn_pause, mx, my):
                            self.paused = not self.paused; self.sfx.click()
                        elif hit(self.btn_step, mx, my):
                            self.step_once = True; self.paused = True; self.sfx.click()
                        elif hit(self.btn_restart, mx, my):
                            self.sfx.click(); self.reset_match(keep_series=True)  # restart same series? better to reset game only
                            # For simplicity, reset game only (keep series)
                            self.reset_match(keep_series=True)
                        elif hit(self.btn_back, mx, my):
                            self.sfx.click(); self.request_scene("MENU"); self.menu_tab = "HOME"
                        elif hit(self.btn_full, mx, my):
                            self.sfx.click(); self.toggle_fullscreen()
                        elif hit(self.btn_side, mx, my):
                            self.sfx.click(); self.sidebar_on = not self.sidebar_on
                        elif hit(self.btn_spd_down, mx, my):
                            self.speed = max(0.3, self.speed - 0.2); self.sfx.click()
                        elif hit(self.btn_spd_up, mx, my):
                            self.speed = min(3.0, self.speed + 0.2); self.sfx.click()
                        else:
                            if self.is_human_turn() and (not self.paused) and (self.anim is None) and (not self.anim_q):
                                cell = self.cell_from_mouse(mx, my, tile, gx, gy)
                                if cell:
                                    r, c = cell
                                    if self.phase == "DROP":
                                        if self.drop_count[self.turn] < self.max_drop:
                                            self.do_drop(c, self.turn)
                                    else:
                                        if self.selected is None:
                                            if self.board[r][c] == self.turn:
                                                self.selected = (r, c)
                                                self.compute_valid_targets(self.selected)
                                                self.sfx.click()
                                        else:
                                            if (r, c) in self.valid_targets:
                                                mv = ("M", self.selected, (r, c))
                                                self.selected = None
                                                self.valid_targets.clear()
                                                self.do_move(mv, self.turn, None)
                                            else:
                                                if self.board[r][c] == self.turn:
                                                    self.selected = (r, c)
                                                    self.compute_valid_targets(self.selected)
                                                    self.sfx.click()
                                                else:
                                                    self.selected = None
                                                    self.valid_targets.clear()

            # updates
            if self.scene == "SPLASH":
                if (time.perf_counter() - self.splash_start) >= SPLASH_SECONDS and not self.splash_done:
                    self.splash_done = True
                    self.request_scene("MENU")
                    self.menu_tab = "HOME"

            elif self.scene == "PLAY":
                if self.anim is None and self.anim_q:
                    self.anim = self.anim_q.pop(0)
                if self.anim:
                    self.anim["t"] += dt
                    if self.anim["t"] >= self.anim["dur"]:
                        self.anim = None

                self.update_human_hint(dt)

                can_step = (not self.paused) or self.step_once
                if can_step and (self.anim is None) and (not self.anim_q) and self.winner == EMPTY:
                    if not self.is_human_turn():
                        self.ai_timer -= dt
                        if self.ai_timer <= 0:
                            self.ai_take_turn()
                            self.ai_timer = self.ai_interval / max(0.35, self.speed)
                            self.step_once = False
                    else:
                        if self.step_once:
                            self.step_once = False

            # draw
            self.screen.fill(BG)

            if self.scene == "SPLASH":
                self.draw_splash()
            elif self.scene == "MENU":
                if self.menu_tab == "HOME":
                    self.draw_menu_home()
                elif self.menu_tab == "SETTINGS":
                    self.draw_menu_settings()
                else:
                    self.draw_menu_about()
            elif self.scene == "PLAY":
                self.draw_play()
            elif self.scene == "WIN":
                self.draw_play()
                self.draw_win_overlay()

            if self.fade.active:
                a, done = self.fade.alpha(raw_dt)
                self.apply_fade_overlay(a)
                if done:
                    if self.fade.phase == "OUT":
                        self.scene = self.fade.next_scene
                        self.fade.phase = "IN"
                        self.fade.t = 0.0
                    else:
                        self.fade.active = False

            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    App().run()