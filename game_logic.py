# game_logic.py
from settings import N, EMPTY, RED, BLUE, DIRS4

def other(p): return BLUE if p == RED else RED
def inb(r, c): return 0 <= r < N and 0 <= c < N

def build_diagonal_segments():
    segs = []
    K = 4
    # "\" diagonals
    for r in range(N - K + 1):
        for c in range(N - K + 1):
            segs.append([(r + i, c + i) for i in range(K)])
    # "/" diagonals
    for r in range(K - 1, N):
        for c in range(N - K + 1):
            segs.append([(r - i, c + i) for i in range(K)])
    return segs

DIAG_SEGS = build_diagonal_segments()

def winner_diagonal(board):
    for seg in DIAG_SEGS:
        vals = [board[r][c] for r, c in seg]
        if vals[0] != EMPTY and all(v == vals[0] for v in vals):
            return vals[0], seg
    return EMPTY, []

# -------------------------
# DROP
# -------------------------
def drop_in_column(board, col, player, hazards):
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
# MOVE (UDLR only) - NO CAPTURE
# -------------------------
def legal_moves_movephase(board, player, hazards):
    moves = []
    for r in range(N):
        for c in range(N):
            if board[r][c] != player:
                continue
            for dr, dc in DIRS4:
                nr, nc = r + dr, c + dc
                if not inb(nr, nc):
                    continue
                if (nr, nc) in hazards:
                    continue
                if board[nr][nc] != EMPTY:
                    continue
                moves.append(("M", (r, c), (nr, nc)))
    return moves

def apply_move(board, mv):
    _, (r, c), (nr, nc) = mv
    nb = [row[:] for row in board]
    nb[nr][nc] = nb[r][c]
    nb[r][c] = EMPTY
    return nb