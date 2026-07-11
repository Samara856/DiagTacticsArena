# ai.py
import time
from dataclasses import dataclass
from settings import N, EMPTY, RED, BLUE
from game_logic import winner_diagonal, other, legal_moves_movephase, apply_move, DIAG_SEGS

@dataclass
class AIStats:
    algo: str = ""
    nodes: int = 0
    prunes: int = 0
    depth: int = 0
    best_score: int = 0
    time_spent: float = 0.0
    top: list = None  # [(score, move),...]

def eval_components(board, player, hazards):
    """Return components so we can explain 'why' a move was suggested."""
    w, _ = winner_diagonal(board)
    if w == player:
        return {"win": 1, "diag": 1e9, "mob": 0, "haz": 0, "total": 100000}
    if w == other(player):
        return {"win": -1, "diag": -1e9, "mob": 0, "haz": 0, "total": -100000}

    # diagonal progress (symmetric)
    diag = 0
    for seg in DIAG_SEGS:
        vals = [board[r][c] for r, c in seg]
        mc = vals.count(player)
        oc = vals.count(other(player))
        ec = vals.count(EMPTY)
        if oc == 0:
            diag += (mc * mc) * 75 + ec * 2
        if mc == 0:
            diag -= (oc * oc) * 75 + ec * 2   # symmetric penalty

    # mobility
    mob = len(legal_moves_movephase(board, player, hazards)) - len(legal_moves_movephase(board, other(player), hazards))
    mob *= 4

    # hazard safety: penalize being adjacent to hazards
    haz_pen = 0
    for r in range(N):
        for c in range(N):
            if board[r][c] != player:
                continue
            adj = 0
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                if (r+dr, c+dc) in hazards:
                    adj += 1
            haz_pen -= adj * 10

    total = int(diag + mob + haz_pen)
    return {"win": 0, "diag": int(diag), "mob": int(mob), "haz": int(haz_pen), "total": total}

def eval_board(board, player, hazards):
    return eval_components(board, player, hazards)["total"]

# -------------------------
# DROP chooser (fast heuristic)
# -------------------------
def ai_choose_drop(board, player, hazards):
    best_col = None
    top = []
    for col in range(N):
        nb, land = _drop_in_column(board, col, player, hazards)
        if nb is None:
            continue
        sc = eval_board(nb, player, hazards)
        top.append((sc, col, land))
    top.sort(reverse=True, key=lambda x: x[0])
    if top:
        best_col = top[0][1]
    return best_col, top[:3]

def _drop_in_column(board, col, player, hazards):
    if col < 0 or col >= N:
        return None, None
    for r in range(N - 1, -1, -1):
        if (r, col) in hazards:
            continue
        if board[r][col] == EMPTY:
            nb = [row[:] for row in board]
            nb[r][col] = player
            return nb, (r, col)
    return None, None

# -------------------------
# Minimax (RED)
# -------------------------
def minimax_move(board, player, hazards, depth, time_limit):
    st = AIStats(algo="Minimax", nodes=0, prunes=0, depth=0, best_score=0, time_spent=0.0, top=[])
    start = time.perf_counter()

    def time_up():
        return (time.perf_counter() - start) >= time_limit

    def terminal(b, d):
        w, _ = winner_diagonal(b)
        if w != EMPTY or d == 0:
            return True, eval_board(b, player, hazards)
        if not legal_moves_movephase(b, player, hazards):
            return True, -80000
        if not legal_moves_movephase(b, other(player), hazards):
            return True, 80000
        return False, 0

    def maxv(b, d):
        if time_up(): raise TimeoutError
        st.nodes += 1
        done, val = terminal(b, d)
        if done: return val
        v = -10**9
        for mv in legal_moves_movephase(b, player, hazards):
            v = max(v, minv(apply_move(b, mv), d - 1))
        return v

    def minv(b, d):
        if time_up(): raise TimeoutError
        st.nodes += 1
        done, val = terminal(b, d)
        if done: return val
        v = 10**9
        for mv in legal_moves_movephase(b, other(player), hazards):
            v = min(v, maxv(apply_move(b, mv), d - 1))
        return v

    best_mv = None
    best_sc = -10**9
    best_top = []

    try:
        for d in range(1, depth + 1):
            if time_up(): break
            st.depth = d
            scored = []
            for mv in legal_moves_movephase(board, player, hazards):
                sc = minv(apply_move(board, mv), d - 1)
                scored.append((sc, mv))
            scored.sort(reverse=True, key=lambda x: x[0])
            if scored:
                best_sc, best_mv = scored[0]
                best_top = scored[:3]
    except TimeoutError:
        pass

    st.best_score = best_sc
    st.top = best_top
    st.time_spent = time.perf_counter() - start
    return best_mv, st

# -------------------------
# Alpha-Beta (BLUE) with move ordering
# -------------------------
def alphabeta_move(board, player, hazards, depth, time_limit):
    st = AIStats(algo="Alpha-Beta", nodes=0, prunes=0, depth=0, best_score=0, time_spent=0.0, top=[])
    start = time.perf_counter()

    def time_up():
        return (time.perf_counter() - start) >= time_limit

    def terminal(b, d):
        w, _ = winner_diagonal(b)
        if w != EMPTY or d == 0:
            return True, eval_board(b, player, hazards)
        if not legal_moves_movephase(b, player, hazards):
            return True, -80000
        if not legal_moves_movephase(b, other(player), hazards):
            return True, 80000
        return False, 0

    # move ordering: try captures? none. we can use simple heuristic: order by previous depth scores if available
    # For simplicity, we'll not implement complex ordering here.

    def maxv(b, d, a, beta):
        if time_up(): raise TimeoutError
        st.nodes += 1
        done, val = terminal(b, d)
        if done: return val
        v = -10**9
        moves = legal_moves_movephase(b, player, hazards)
        # simple static ordering: try moves that might be better first? we can skip for now
        for mv in moves:
            v = max(v, minv(apply_move(b, mv), d - 1, a, beta))
            a = max(a, v)
            if a >= beta:
                st.prunes += 1
                break
        return v

    def minv(b, d, a, beta):
        if time_up(): raise TimeoutError
        st.nodes += 1
        done, val = terminal(b, d)
        if done: return val
        v = 10**9
        moves = legal_moves_movephase(b, other(player), hazards)
        for mv in moves:
            v = min(v, maxv(apply_move(b, mv), d - 1, a, beta))
            beta = min(beta, v)
            if a >= beta:
                st.prunes += 1
                break
        return v

    best_mv = None
    best_sc = -10**9
    best_top = []

    try:
        for d in range(1, depth + 1):
            if time_up(): break
            st.depth = d
            scored = []
            a, b = -10**9, 10**9
            for mv in legal_moves_movephase(board, player, hazards):
                sc = minv(apply_move(board, mv), d - 1, a, b)
                scored.append((sc, mv))
                a = max(a, sc)
            scored.sort(reverse=True, key=lambda x: x[0])
            if scored:
                best_sc, best_mv = scored[0]
                best_top = scored[:3]
    except TimeoutError:
        pass

    st.best_score = best_sc
    st.top = best_top
    st.time_spent = time.perf_counter() - start
    return best_mv, st

# -------------------------
# Explanation helper
# -------------------------
def explain_action(board, player, hazards, action_type, action_value):
    base = eval_components(board, player, hazards)

    if action_type == "DROP":
        col = action_value
        nb, land = _drop_in_column(board, col, player, hazards)
        if nb is None:
            return ["No legal drop found."]
        after = eval_components(nb, player, hazards)
        delta = {k: after[k] - base[k] for k in ["diag", "mob", "haz", "total"]}
        reasons = _pick_reasons(delta)
        return reasons

    if action_type == "MOVE":
        mv = action_value
        nb = apply_move(board, mv)
        after = eval_components(nb, player, hazards)
        delta = {k: after[k] - base[k] for k in ["diag", "mob", "haz", "total"]}
        reasons = _pick_reasons(delta)
        return reasons

    return ["—"]

def _pick_reasons(delta):
    pairs = [
        ("Diagonal progress improved", delta["diag"]),
        ("Mobility improved", delta["mob"]),
        ("Safer vs hazards", delta["haz"]),
    ]
    pairs.sort(key=lambda x: x[1], reverse=True)
    out = []
    for label, val in pairs:
        if val > 0:
            out.append(f"{label} (+{val})")
    if not out:
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        out = [f"{label} ({val:+})" for label, val in pairs[:3]]
    return out[:3]