# ui.py
import pygame
from settings import *

def hit(rect, mx, my):
    x, y, w, h = rect
    return x <= mx <= x + w and y <= my <= y + h


def draw_button(surf, font, rect, text, hovered=False, active=False, accent=False):
    x, y, w, h = rect
    # Base colors like stone/cobblestone
    base = (96, 96, 96)  # stone
    hov = (120, 120, 120)  # lighter stone
    act = (70, 70, 70)  # dark stone
    if accent:
        base = (200, 170, 100)  # gold block
        hov = (220, 190, 120)
        act = (160, 130, 70)

    col = act if active else (hov if hovered else base)

    # Shadow (offset)
    shadow_rect = (x + 3, y + 3, w, h)
    pygame.draw.rect(surf, (30, 30, 30), shadow_rect, border_radius=6)

    # Main button
    pygame.draw.rect(surf, col, rect, border_radius=6)

    # Border
    border_color = (20, 20, 20)
    pygame.draw.rect(surf, border_color, rect, 2, border_radius=6)

    # If active, draw a glowing gold outline
    if active:
        glow_color = ACC
        pygame.draw.rect(surf, glow_color, rect, 4, border_radius=6)

    # Text
    label = font.render(text, True, TXT)
    surf.blit(label, (x + (w - label.get_width()) // 2, y + (h - label.get_height()) // 2))

def draw_panel(surface, rect, shadow=True):
    if shadow:
        pygame.draw.rect(surface, (40,30,20), (rect[0]+4, rect[1]+4, rect[2], rect[3]), border_radius=8)
    pygame.draw.rect(surface, PANEL2, rect, border_radius=8)
    pygame.draw.rect(surface, (50,40,30), rect, 2, border_radius=8)

def wrap_lines(font, text, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.size(t)[0] <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def wrap_text(font, text, max_width):
    """Break text into lines that fit within max_width (pixels)."""
    words = text.split(' ')
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def move_to_str(move):
    """Convert a move (DROP column or MOVE tuple) to readable string."""
    if isinstance(move, int):
        return f"DROP col {move+1}"
    elif isinstance(move, tuple) and len(move) == 3 and move[0] == "M":
        return f"MOVE {move[1]}→{move[2]}"
    else:
        return str(move)

def draw_tile(surface, rect, checker):
    # Minecraft grass/dirt pattern: alternate between two earthy tones
    col = GRID_A if checker else GRID_B
    pygame.draw.rect(surface, col, rect, border_radius=0)   # sharp corners (blocky)
    # Add a subtle inner highlight to simulate block face
    inner = (min(col[0]+30,255), min(col[1]+30,255), min(col[2]+30,255))
    pygame.draw.rect(surface, inner, (rect[0]+2, rect[1]+2, rect[2]-4, rect[3]-4), 1, border_radius=0)
    pygame.draw.rect(surface, GRIDLINE, rect, 2, border_radius=0)   # thick border

def draw_token(surface, cx, cy, tile, p, glow=False):
    # Tokens look like ore blocks: redstone / lapis
    col = RED_C if p == 1 else BLUE_C
    sz = max(18, tile - 18)
    x = cx - sz // 2
    y = cy - sz // 2
    # Outer glow if selected
    if glow:
        glow_surf = pygame.Surface((sz+8, sz+8), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (255,255,255,100), (0,0,sz+8,sz+8), border_radius=4)
        surface.blit(glow_surf, (x-4, y-4))
    # Ore block
    pygame.draw.rect(surface, col, (x, y, sz, sz), border_radius=4)
    # Dark border
    pygame.draw.rect(surface, (30,30,30), (x, y, sz, sz), 3, border_radius=4)
    # Highlight corners
    pygame.draw.line(surface, (255,255,255,60), (x+3, y+3), (x+sz-6, y+3), 2)
    pygame.draw.line(surface, (255,255,255,60), (x+3, y+3), (x+3, y+sz-6), 2)

def draw_hazard(surface, cx, cy, tile):
    # Lava hazard
    sz = max(14, tile - 22)
    x = cx - sz // 2
    y = cy - sz // 2
    # Lava core
    pygame.draw.rect(surface, HAZ_C, (x, y, sz, sz), border_radius=4)
    # Inner glow (hotter)
    inner = (255, 200, 0)
    pygame.draw.rect(surface, inner, (x+2, y+2, sz-4, sz-4), border_radius=4)
    # Dark border
    pygame.draw.rect(surface, (50,30,10), (x, y, sz, sz), 3, border_radius=4)

def draw_hint_outline(surface, rect, kind="suggest"):
    # rect is cell's rectangle (x,y,w,h)
    if kind == "suggest":
        color = SUGG
        width = 4
    elif kind == "good":
        color = GOOD
        width = 3
    elif kind == "win":
        color = ACC
        width = 4
    elif kind == "select":
        color = (200,200,200)
        width = 3
    else:
        return
    pygame.draw.rect(surface, color, rect, width, border_radius=0)

def draw_drop_arrow(surface, gx, gy, tile, col):
    # Arrow made of blocks? We'll keep simple polygon but with earthy colors
    x = gx + col * tile + tile // 2
    y = gy - 18
    pts = [(x, y), (x - 10, y + 14), (x + 10, y + 14)]
    pygame.draw.polygon(surface, SUGG, pts)
    pygame.draw.polygon(surface, (100,60,20), pts, 2)

def draw_top_tabs(surface, font_b, w, active_tab, mx, my):
    # Minecraft-style tabs like stone slabs
    pygame.draw.rect(surface, PANEL, (0, 0, w, 54))
    tabs = ["HOME", "SETTINGS", "ABOUT"]
    rects = {}
    x = 18
    for t in tabs:
        r = (x, 10, 140, 34)
        rects[t] = r
        draw_button(surface, font_b, r, t, hovered=hit(r, mx, my), active=(active_tab == t), accent=True)
        x += 150
    return rects

def draw_slider_row(surface, font, label, value_text, x, y, w):
    surface.blit(font.render(label, True, TXT), (x, y))
    surface.blit(font.render(value_text, True, MUTED), (x + w - 140, y))

def draw_crafting_background(surf, rect, color1, color2, cell_size=32):
    """Fill rect with a checkerboard pattern (like a crafting grid)."""
    x0, y0, w, h = rect
    for x in range(x0, x0 + w, cell_size):
        for y in range(y0, y0 + h, cell_size):
            # alternate color based on position
            col = color1 if ((x - x0) // cell_size + (y - y0) // cell_size) % 2 == 0 else color2
            cell_rect = (x, y, min(cell_size, x0 + w - x), min(cell_size, y0 + h - y))
            pygame.draw.rect(surf, col, cell_rect)