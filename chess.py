#!/usr/bin/env python3
"""
Chess Game - Terminal-based two-player chess
Run: python chess.py
"""

import os
import sys
import copy

# ─── ANSI Colors ───────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
BG_DARK  = "\033[48;5;94m"   # dark brown square
BG_LIGHT = "\033[48;5;223m"  # light cream square
BG_SEL   = "\033[48;5;226m"  # yellow – selected piece
BG_MOVE  = "\033[48;5;154m"  # green  – valid move
BG_CHECK = "\033[48;5;196m"  # red    – king in check
FG_WHITE = "\033[97m"
FG_BLACK = "\033[30m"
FG_LABEL = "\033[38;5;240m"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

# ─── Piece definitions ─────────────────────────────────────────────────────────
UNICODE = {
    ("K","W"):"♔", ("Q","W"):"♕", ("R","W"):"♖",
    ("B","W"):"♗", ("N","W"):"♘", ("P","W"):"♙",
    ("K","B"):"♚", ("Q","B"):"♛", ("R","B"):"♜",
    ("B","B"):"♝", ("N","B"):"♞", ("P","B"):"♟",
}

class Piece:
    def __init__(self, kind, color):
        self.kind  = kind   # K Q R B N P
        self.color = color  # W B
        self.moved = False

    def __repr__(self):
        return UNICODE[(self.kind, self.color)]

# ─── Board ─────────────────────────────────────────────────────────────────────
def make_board():
    b = [[None]*8 for _ in range(8)]
    order = ["R","N","B","Q","K","B","N","R"]
    for c, color in ((0,"B"), (7,"W")):
        for col, kind in enumerate(order):
            b[c][col] = Piece(kind, color)
        pawn_row = 1 if color == "B" else 6
        for col in range(8):
            b[pawn_row][col] = Piece("P", color)
    return b

# ─── Move generation ───────────────────────────────────────────────────────────
def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8

def raw_moves(board, r, c, en_passant=None):
    """Return list of (to_r, to_c) WITHOUT checking self-check."""
    p = board[r][c]
    if p is None:
        return []
    moves = []
    color = p.color
    opp   = "B" if color == "W" else "W"

    def slide(dirs):
        for dr, dc in dirs:
            nr, nc = r+dr, c+dc
            while in_bounds(nr, nc):
                target = board[nr][nc]
                if target is None:
                    moves.append((nr, nc))
                elif target.color == opp:
                    moves.append((nr, nc))
                    break
                else:
                    break
                nr += dr; nc += dc

    def jump(offsets):
        for dr, dc in offsets:
            nr, nc = r+dr, c+dc
            if in_bounds(nr, nc):
                target = board[nr][nc]
                if target is None or target.color == opp:
                    moves.append((nr, nc))

    if p.kind == "R":
        slide([(1,0),(-1,0),(0,1),(0,-1)])
    elif p.kind == "B":
        slide([(1,1),(1,-1),(-1,1),(-1,-1)])
    elif p.kind == "Q":
        slide([(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)])
    elif p.kind == "N":
        jump([(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)])
    elif p.kind == "K":
        jump([(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)])
        # Castling
        if not p.moved:
            for dc, cols in ((2, [5,6,7]), (-2, [1,2,3,4])):
                rook_col = 7 if dc == 2 else 0
                rook = board[r][rook_col]
                if rook and rook.kind == "R" and not rook.moved:
                    path = cols[:-1] if dc == 2 else cols[1:]
                    if all(board[r][cc] is None for cc in path):
                        moves.append((r, c+dc))
    elif p.kind == "P":
        fwd = -1 if color == "W" else 1
        # Forward
        if in_bounds(r+fwd, c) and board[r+fwd][c] is None:
            moves.append((r+fwd, c))
            start_row = 6 if color == "W" else 1
            if r == start_row and board[r+2*fwd][c] is None:
                moves.append((r+2*fwd, c))
        # Captures
        for dc in (-1, 1):
            nr, nc = r+fwd, c+dc
            if in_bounds(nr, nc):
                target = board[nr][nc]
                if target and target.color == opp:
                    moves.append((nr, nc))
                # En passant
                if en_passant and (nr, nc) == en_passant:
                    moves.append((nr, nc))
    return moves

def find_king(board, color):
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p and p.kind == "K" and p.color == color:
                return r, c
    return None

def is_attacked(board, r, c, by_color):
    """Is square (r,c) attacked by any piece of by_color?"""
    for rr in range(8):
        for cc in range(8):
            p = board[rr][cc]
            if p and p.color == by_color:
                if (r, c) in raw_moves(board, rr, cc):
                    return True
    return False

def in_check(board, color):
    kr, kc = find_king(board, color)
    opp = "B" if color == "W" else "W"
    return is_attacked(board, kr, kc, opp)

def apply_move(board, fr, fc, tr, tc, en_passant=None):
    """Apply move on a deep copy; return new board, new en_passant square."""
    b = copy.deepcopy(board)
    p = b[fr][fc]
    new_ep = None

    # En passant capture
    if p.kind == "P" and en_passant and (tr, tc) == en_passant:
        cap_r = fr  # captured pawn is on same rank as moving pawn
        b[cap_r][tc] = None

    # Two-square pawn advance → set en passant
    if p.kind == "P" and abs(tr - fr) == 2:
        new_ep = ((fr + tr) // 2, tc)

    # Castling rook move
    if p.kind == "K" and abs(tc - fc) == 2:
        if tc > fc:  # kingside
            b[fr][5] = b[fr][7]
            b[fr][7] = None
            if b[fr][5]: b[fr][5].moved = True
        else:        # queenside
            b[fr][3] = b[fr][0]
            b[fr][0] = None
            if b[fr][3]: b[fr][3].moved = True

    b[tr][tc] = p
    b[fr][fc] = None
    p.moved = True

    # Pawn promotion (auto-queen)
    if p.kind == "P" and (tr == 0 or tr == 7):
        b[tr][tc] = Piece("Q", p.color)

    return b, new_ep

def legal_moves(board, r, c, en_passant=None):
    p = board[r][c]
    if p is None:
        return []
    result = []
    for tr, tc in raw_moves(board, r, c, en_passant):
        nb, _ = apply_move(board, r, c, tr, tc, en_passant)
        if not in_check(nb, p.color):
            result.append((tr, tc))
    return result

def all_legal_moves(board, color, en_passant=None):
    moves = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p and p.color == color:
                for mv in legal_moves(board, r, c, en_passant):
                    moves.append((r, c, mv[0], mv[1]))
    return moves

# ─── Rendering ─────────────────────────────────────────────────────────────────
def render(board, selected=None, highlights=None, check_king=None, last_move=None, status=""):
    highlights = highlights or set()
    clear()
    print(f"\n  {BOLD}♟  CHESS{RESET}\n")
    print(f"  {FG_LABEL}  a b c d e f g h{RESET}")
    print(f"  {FG_LABEL}  ─────────────────{RESET}")
    for r in range(8):
        row_label = str(8 - r)
        line = f"  {FG_LABEL}{row_label}│{RESET} "
        for c in range(8):
            p = board[r][c]
            is_light = (r + c) % 2 == 0

            if selected and (r, c) == selected:
                bg = BG_SEL
            elif (r, c) in highlights:
                bg = BG_MOVE
            elif check_king and (r, c) == check_king:
                bg = BG_CHECK
            elif last_move and (r, c) in last_move:
                bg = "\033[48;5;180m"
            else:
                bg = BG_LIGHT if is_light else BG_DARK

            if p:
                fg = FG_WHITE if p.color == "W" else FG_BLACK
                line += f"{bg}{fg}{BOLD} {p} {RESET}"
            else:
                dot = "·" if (r,c) in highlights else " "
                line += f"{bg} {dot} {RESET}"
        line += f" {FG_LABEL}{row_label}{RESET}"
        print(line)
    print(f"  {FG_LABEL}  ─────────────────{RESET}")
    print(f"  {FG_LABEL}  a b c d e f g h{RESET}\n")
    if status:
        print(f"  {status}\n")

# ─── Input parsing ─────────────────────────────────────────────────────────────
def parse_square(s):
    s = s.strip().lower()
    if len(s) == 2 and s[0] in "abcdefgh" and s[1] in "12345678":
        c = ord(s[0]) - ord('a')
        r = 8 - int(s[1])
        return r, c
    return None

def parse_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        sys.exit(0)

# ─── Main game loop ────────────────────────────────────────────────────────────
def game():
    board = make_board()
    turn  = "W"
    en_passant = None
    last_move  = set()
    move_history = []

    while True:
        opp = "B" if turn == "W" else "W"
        king_pos = None
        check_king_sq = None

        if in_check(board, turn):
            king_pos = find_king(board, turn)
            check_king_sq = king_pos

        all_moves = all_legal_moves(board, turn, en_passant)
        if not all_moves:
            if in_check(board, turn):
                status = f"  {BOLD}Checkmate! {'Black' if turn=='W' else 'White'} wins! 🎉{RESET}"
            else:
                status = f"  {BOLD}Stalemate! It's a draw.{RESET}"
            render(board, check_king=check_king_sq, last_move=last_move, status=status)
            parse_input("  Press Enter to exit...")
            break

        color_name = "White" if turn == "W" else "Black"
        check_msg  = f"  {BOLD}\033[91m⚠  {color_name} is in CHECK!{RESET}" if in_check(board, turn) else ""
        status = f"  {BOLD}{color_name}'s turn{RESET}  (type 'quit' or 'draw')" + ("\n" + check_msg if check_msg else "")

        render(board, check_king=check_king_sq, last_move=last_move, status=status)

        # Select piece
        while True:
            raw = parse_input("  Select piece (e.g. e2): ")
            if raw.lower() == "quit":
                print("  Thanks for playing!"); sys.exit(0)
            if raw.lower() == "draw":
                print("  Draw agreed. Thanks for playing!"); sys.exit(0)
            sq = parse_square(raw)
            if sq is None:
                print("  Invalid square. Use format like 'e2'."); continue
            r, c = sq
            p = board[r][c]
            if p is None or p.color != turn:
                print("  No friendly piece there."); continue
            moves = legal_moves(board, r, c, en_passant)
            if not moves:
                print("  That piece has no legal moves."); continue
            break

        highlights = set(moves)
        render(board, selected=(r,c), highlights=highlights, check_king=check_king_sq,
               last_move=last_move, status=status)

        # Select destination
        while True:
            raw = parse_input("  Move to (e.g. e4, or 'back'): ")
            if raw.lower() == "back":
                break
            if raw.lower() == "quit":
                print("  Thanks for playing!"); sys.exit(0)
            dest = parse_square(raw)
            if dest is None:
                print("  Invalid square."); continue
            if dest not in highlights:
                print("  Illegal move."); continue
            tr, tc = dest
            board, en_passant = apply_move(board, r, c, tr, tc, en_passant)
            last_move = {(r,c), (tr,tc)}
            move_history.append(f"{'W' if turn=='W' else 'B'}: {raw}")
            turn = opp
            break

if __name__ == "__main__":
    game()
