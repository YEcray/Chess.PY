#!/usr/bin/env python3
"""
Chess Game — you play White, the bot plays Black.
Run: python chess.py
"""

import copy, json, random, threading, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# ─── Chess Engine ──────────────────────────────────────────────────────────────

UNICODE = {
    ("K","W"):"♔",("Q","W"):"♕",("R","W"):"♖",
    ("B","W"):"♗",("N","W"):"♘",("P","W"):"♙",
    ("K","B"):"♚",("Q","B"):"♛",("R","B"):"♜",
    ("B","B"):"♝",("N","B"):"♞",("P","B"):"♟",
}

# Piece-square tables (from Black's perspective; White uses flipped rows)
PST = {
    "P": [
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        [50, 50, 50, 50, 50, 50, 50, 50],
        [10, 10, 20, 30, 30, 20, 10, 10],
        [ 5,  5, 10, 25, 25, 10,  5,  5],
        [ 0,  0,  0, 20, 20,  0,  0,  0],
        [ 5, -5,-10,  0,  0,-10, -5,  5],
        [ 5, 10, 10,-20,-20, 10, 10,  5],
        [ 0,  0,  0,  0,  0,  0,  0,  0],
    ],
    "N": [
        [-50,-40,-30,-30,-30,-30,-40,-50],
        [-40,-20,  0,  0,  0,  0,-20,-40],
        [-30,  0, 10, 15, 15, 10,  0,-30],
        [-30,  5, 15, 20, 20, 15,  5,-30],
        [-30,  0, 15, 20, 20, 15,  0,-30],
        [-30,  5, 10, 15, 15, 10,  5,-30],
        [-40,-20,  0,  5,  5,  0,-20,-40],
        [-50,-40,-30,-30,-30,-30,-40,-50],
    ],
    "B": [
        [-20,-10,-10,-10,-10,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5, 10, 10,  5,  0,-10],
        [-10,  5,  5, 10, 10,  5,  5,-10],
        [-10,  0, 10, 10, 10, 10,  0,-10],
        [-10, 10, 10, 10, 10, 10, 10,-10],
        [-10,  5,  0,  0,  0,  0,  5,-10],
        [-20,-10,-10,-10,-10,-10,-10,-20],
    ],
    "R": [
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        [ 5, 10, 10, 10, 10, 10, 10,  5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [-5,  0,  0,  0,  0,  0,  0, -5],
        [ 0,  0,  0,  5,  5,  0,  0,  0],
    ],
    "Q": [
        [-20,-10,-10, -5, -5,-10,-10,-20],
        [-10,  0,  0,  0,  0,  0,  0,-10],
        [-10,  0,  5,  5,  5,  5,  0,-10],
        [ -5,  0,  5,  5,  5,  5,  0, -5],
        [  0,  0,  5,  5,  5,  5,  0, -5],
        [-10,  5,  5,  5,  5,  5,  0,-10],
        [-10,  0,  5,  0,  0,  0,  0,-10],
        [-20,-10,-10, -5, -5,-10,-10,-20],
    ],
    "K": [
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-30,-40,-40,-50,-50,-40,-40,-30],
        [-20,-30,-30,-40,-40,-30,-30,-20],
        [-10,-20,-20,-20,-20,-20,-20,-10],
        [ 20, 20,  0,  0,  0,  0, 20, 20],
        [ 20, 30, 10,  0,  0, 10, 30, 20],
    ],
}

PIECE_VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

class Piece:
    def __init__(self, kind, color):
        self.kind = kind; self.color = color; self.moved = False
    def to_dict(self):
        return {"kind": self.kind, "color": self.color, "symbol": UNICODE[(self.kind, self.color)]}

def make_board():
    b = [[None]*8 for _ in range(8)]
    order = ["R","N","B","Q","K","B","N","R"]
    for row, color in ((0,"B"),(7,"W")):
        for col, kind in enumerate(order):
            b[row][col] = Piece(kind, color)
        pr = 1 if color == "B" else 6
        for col in range(8):
            b[pr][col] = Piece("P", color)
    return b

def in_bounds(r,c): return 0<=r<8 and 0<=c<8

def raw_moves(board, r, c, ep=None):
    p = board[r][c]
    if not p: return []
    moves, color, opp = [], p.color, "B" if p.color=="W" else "W"

    def slide(dirs):
        for dr,dc in dirs:
            nr,nc = r+dr, c+dc
            while in_bounds(nr,nc):
                t = board[nr][nc]
                if t is None: moves.append((nr,nc))
                elif t.color==opp: moves.append((nr,nc)); break
                else: break
                nr+=dr; nc+=dc

    def jump(offs):
        for dr,dc in offs:
            nr,nc = r+dr, c+dc
            if in_bounds(nr,nc):
                t = board[nr][nc]
                if t is None or t.color==opp: moves.append((nr,nc))

    if p.kind=="R": slide([(1,0),(-1,0),(0,1),(0,-1)])
    elif p.kind=="B": slide([(1,1),(1,-1),(-1,1),(-1,-1)])
    elif p.kind=="Q": slide([(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)])
    elif p.kind=="N": jump([(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)])
    elif p.kind=="K":
        jump([(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)])
        if not p.moved:
            for dc, path, rook_col in ((2,[5,6],7), (-2,[2,3],0)):
                rook = board[r][rook_col]
                if rook and rook.kind=="R" and not rook.moved:
                    if all(board[r][cc] is None for cc in path):
                        moves.append((r, c+dc))
    elif p.kind=="P":
        fwd = -1 if color=="W" else 1
        if in_bounds(r+fwd,c) and board[r+fwd][c] is None:
            moves.append((r+fwd,c))
            sr = 6 if color=="W" else 1
            if r==sr and board[r+2*fwd][c] is None:
                moves.append((r+2*fwd,c))
        for dc in (-1,1):
            nr,nc = r+fwd, c+dc
            if in_bounds(nr,nc):
                t = board[nr][nc]
                if t and t.color==opp: moves.append((nr,nc))
                if ep and (nr,nc)==ep: moves.append((nr,nc))
    return moves

def find_king(board, color):
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p and p.kind=="K" and p.color==color: return r,c

def is_attacked(board, r, c, by):
    for rr in range(8):
        for cc in range(8):
            p = board[rr][cc]
            if p and p.color==by and (r,c) in raw_moves(board,rr,cc): return True
    return False

def in_check(board, color):
    pos = find_king(board, color)
    if not pos: return False
    return is_attacked(board, pos[0], pos[1], "B" if color=="W" else "W")

def apply_move(board, fr, fc, tr, tc, ep=None):
    b = copy.deepcopy(board)
    p = b[fr][fc]
    new_ep = None
    if p.kind=="P" and ep and (tr,tc)==ep:
        b[fr][tc] = None
    if p.kind=="P" and abs(tr-fr)==2:
        new_ep = ((fr+tr)//2, tc)
    if p.kind=="K" and abs(tc-fc)==2:
        if tc>fc:
            b[fr][5]=b[fr][7]; b[fr][7]=None
            if b[fr][5]: b[fr][5].moved=True
        else:
            b[fr][3]=b[fr][0]; b[fr][0]=None
            if b[fr][3]: b[fr][3].moved=True
    b[tr][tc] = p; b[fr][fc] = None; p.moved = True
    if p.kind=="P" and (tr==0 or tr==7):
        b[tr][tc] = Piece("Q", p.color)
    return b, new_ep

def legal_moves(board, r, c, ep=None):
    p = board[r][c]
    if not p: return []
    result = []
    for tr,tc in raw_moves(board,r,c,ep):
        nb,_ = apply_move(board,r,c,tr,tc,ep)
        if not in_check(nb, p.color): result.append((tr,tc))
    return result

def all_legal_moves(board, color, ep=None):
    moves = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p and p.color==color:
                for tr,tc in legal_moves(board,r,c,ep):
                    moves.append((r,c,tr,tc))
    return moves

# ─── Evaluation ────────────────────────────────────────────────────────────────

def pst_score(piece, r, c):
    """Piece-square table bonus. PST rows are from Black's POV (row 0 = Black's back rank)."""
    table = PST.get(piece.kind)
    if not table: return 0
    if piece.color == "B":
        return table[r][c]
    else:
        return table[7-r][c]

def evaluate(board):
    """Positive = good for Black (the bot)."""
    score = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p:
                val = PIECE_VALUE[p.kind] + pst_score(p, r, c)
                score += val if p.color == "B" else -val
    return score

def order_moves(board, moves, ep):
    """Sort moves: captures first (MVV-LVA), then by PST improvement."""
    def priority(mv):
        fr,fc,tr,tc = mv
        target = board[tr][tc]
        if target:
            return -(PIECE_VALUE[target.kind] - PIECE_VALUE[board[fr][fc].kind] // 10)
        return 0
    return sorted(moves, key=priority)

def minimax(board, depth, alpha, beta, maximizing, ep):
    color = "B" if maximizing else "W"
    moves = all_legal_moves(board, color, ep)

    if not moves:
        if in_check(board, color):
            return (10000 if not maximizing else -10000), None
        return 0, None

    if depth == 0:
        return evaluate(board), None

    moves = order_moves(board, moves, ep)
    best_move = None

    if maximizing:
        best = -999999
        for fr,fc,tr,tc in moves:
            nb, nep = apply_move(board, fr, fc, tr, tc, ep)
            score, _ = minimax(nb, depth-1, alpha, beta, False, nep)
            if score > best:
                best = score; best_move = (fr,fc,tr,tc)
            alpha = max(alpha, score)
            if beta <= alpha: break
        return best, best_move
    else:
        best = 999999
        for fr,fc,tr,tc in moves:
            nb, nep = apply_move(board, fr, fc, tr, tc, ep)
            score, _ = minimax(nb, depth-1, alpha, beta, True, nep)
            if score < best:
                best = score; best_move = (fr,fc,tr,tc)
            beta = min(beta, score)
            if beta <= alpha: break
        return best, best_move

def bot_move(board, ep, difficulty):
    """Return (fr,fc,tr,tc) for Black's best move."""
    moves = all_legal_moves(board, "B", ep)
    if not moves: return None

    if difficulty == "easy":
        # Random move with slight preference for captures
        captures = [(fr,fc,tr,tc) for fr,fc,tr,tc in moves if board[tr][tc]]
        pool = captures if captures and random.random() < 0.6 else moves
        return random.choice(pool)
    elif difficulty == "medium":
        depth = 2
    else:  # hard
        depth = 3

    _, move = minimax(board, depth, -999999, 999999, True, ep)
    return move

# ─── Game State ────────────────────────────────────────────────────────────────

class GameState:
    def __init__(self):
        self.difficulty = "medium"
        self.reset()

    def reset(self):
        self.board = make_board()
        self.turn = "W"
        self.ep = None
        self.last_move = None
        self.status = "playing"
        self.winner = None
        self.captured_w = []
        self.captured_b = []
        self.move_history = []
        self.promotion_pending = None
        self.bot_thinking = False

    def board_dict(self):
        return [[self.board[r][c].to_dict() if self.board[r][c] else None for c in range(8)] for r in range(8)]

    def get_moves(self, r, c):
        return legal_moves(self.board, r, c, self.ep)

    def _apply(self, fr, fc, tr, tc):
        """Internal: apply move, track captures and history."""
        p = self.board[fr][fc]
        cap = self.board[tr][tc]
        if cap:
            (self.captured_w if cap.color=="W" else self.captured_b).append(cap.to_dict())
        if p.kind=="P" and self.ep and (tr,tc)==self.ep:
            epc = self.board[fr][tc]
            if epc:
                (self.captured_w if epc.color=="W" else self.captured_b).append(epc.to_dict())
        cols = "abcdefgh"
        self.move_history.append(f"{'●' if self.turn=='B' else '○'} {cols[fc]}{8-fr}→{cols[tc]}{8-tr}")
        self.board, self.ep = apply_move(self.board, fr, fc, tr, tc, self.ep)
        self.last_move = (fr, fc, tr, tc)

    def move(self, fr, fc, tr, tc):
        p = self.board[fr][fc]
        if not p or p.color != self.turn: return False
        if (tr, tc) not in self.get_moves(fr, fc): return False
        self._apply(fr, fc, tr, tc)
        # Pawn promotion for human
        if self.board[tr][tc] and self.board[tr][tc].kind == "P" and (tr == 0 or tr == 7):
            self.promotion_pending = (tr, tc)
            return True
        self.turn = "B" if self.turn == "W" else "W"
        self._update_status()
        return True

    def promote(self, kind):
        if not self.promotion_pending: return
        tr, tc = self.promotion_pending
        color = self.board[tr][tc].color
        self.board[tr][tc] = Piece(kind, color)
        self.promotion_pending = None
        self.turn = "B" if self.turn == "W" else "W"
        self._update_status()

    def do_bot_move(self):
        """Run bot move synchronously (called from background thread)."""
        if self.turn != "B" or self.status not in ("playing","check"): return
        self.bot_thinking = True
        mv = bot_move(self.board, self.ep, self.difficulty)
        self.bot_thinking = False
        if mv:
            fr,fc,tr,tc = mv
            self._apply(fr, fc, tr, tc)
            # Bot promotes to queen automatically
            if self.board[tr][tc] and self.board[tr][tc].kind=="P" and (tr==0 or tr==7):
                self.board[tr][tc] = Piece("Q", "B")
            self.turn = "W"
            self._update_status()

    def _update_status(self):
        opp = self.turn
        moves = all_legal_moves(self.board, opp, self.ep)
        if not moves:
            if in_check(self.board, opp):
                self.status = "checkmate"; self.winner = "W" if opp=="B" else "B"
            else:
                self.status = "stalemate"
        elif in_check(self.board, opp):
            self.status = "check"
        else:
            self.status = "playing"

    def to_json(self):
        return json.dumps({
            "board": self.board_dict(),
            "turn": self.turn,
            "status": self.status,
            "winner": self.winner,
            "last_move": self.last_move,
            "captured_w": self.captured_w,
            "captured_b": self.captured_b,
            "move_history": self.move_history[-20:],
            "promotion_pending": self.promotion_pending,
            "bot_thinking": self.bot_thinking,
            "difficulty": self.difficulty,
        })

GAME = GameState()

# ─── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chess vs Bot</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
  :root {
    --sq-light: #f0d9b5;
    --sq-dark:  #b58863;
    --sq-sel:   #f6f669;
    --sq-move:  #cdd16e;
    --sq-last:  #caa952;
    --sq-check: #e74c3c;
    --bg:       #1a1a18;
    --panel:    #242420;
    --border:   #3a3a32;
    --gold:     #c9a84c;
    --text:     #e8e0cc;
    --muted:    #7a7060;
    --wp:       #fffff0;
    --bp:       #1a1008;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Crimson Text', Georgia, serif;
    min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; padding: 20px;
  }
  h1 { font-family:'Playfair Display',serif; font-size:2rem; letter-spacing:.15em; color:var(--gold); margin-bottom:2px; text-align:center; }
  .subtitle { color:var(--muted); font-size:.85rem; letter-spacing:.1em; margin-bottom:18px; text-align:center; }

  .game-wrap { display:flex; gap:24px; align-items:flex-start; flex-wrap:wrap; justify-content:center; }
  .board-section { display:flex; flex-direction:column; align-items:center; }

  .turn-indicator {
    font-family:'Playfair Display',serif; font-size:1.05rem;
    padding:8px 20px; margin-bottom:10px;
    border:1px solid var(--border); border-radius:2px;
    background:var(--panel); min-width:240px; text-align:center; transition:all .3s;
  }
  .turn-indicator.white { border-color:#aaa; color:#eee; }
  .turn-indicator.black { border-color:#555; color:#aaa; }
  .turn-indicator.check { border-color:#e74c3c; color:#e74c3c; animation:pulse .8s infinite alternate; }
  .turn-indicator.end   { border-color:var(--gold); color:var(--gold); }
  .turn-indicator.thinking { border-color:#5b8dd9; color:#5b8dd9; animation:pulse2 1s infinite alternate; }
  @keyframes pulse  { from{box-shadow:0 0 0 rgba(231,76,60,0)} to{box-shadow:0 0 12px rgba(231,76,60,.5)} }
  @keyframes pulse2 { from{box-shadow:0 0 0 rgba(91,141,217,0)} to{box-shadow:0 0 12px rgba(91,141,217,.4)} }

  .coords { display:flex; }
  .coord-row { display:flex; flex-direction:column; justify-content:space-around; height:480px; padding:4px 0; margin-right:6px; }
  .coord-col { display:flex; justify-content:space-around; width:480px; padding:0 4px; margin-top:6px; }
  .coord { font-size:.75rem; color:var(--muted); width:12px; text-align:center; }

  #board {
    display:grid; grid-template-columns:repeat(8,60px); grid-template-rows:repeat(8,60px);
    border:3px solid var(--gold); box-shadow:0 8px 40px rgba(0,0,0,.6),0 0 0 1px #000;
  }
  .sq {
    width:60px; height:60px; display:flex; align-items:center; justify-content:center;
    font-size:42px; cursor:pointer; position:relative; transition:filter .1s; user-select:none;
  }
  .sq.light { background:var(--sq-light); }
  .sq.dark  { background:var(--sq-dark);  }
  .sq.selected  { background:var(--sq-sel)  !important; }
  .sq.move-hint { background:var(--sq-move) !important; }
  .sq.move-hint::after {
    content:''; position:absolute; width:22px; height:22px;
    border-radius:50%; background:rgba(0,0,0,.18); pointer-events:none;
  }
  .sq.move-hint.has-piece::after {
    width:56px; height:56px; border-radius:2px;
    background:none; border:4px solid rgba(0,0,0,.25);
  }
  .sq.last-move { background:var(--sq-last) !important; }
  .sq.in-check  { background:var(--sq-check) !important; }
  .sq.bot-sq    { background:#4a6fa5 !important; }
  .sq:hover:not(.bot-sq) { filter:brightness(1.1); }
  .piece { line-height:1; transition:transform .15s; pointer-events:none; }
  .piece.white { color:var(--wp); text-shadow:0 1px 3px rgba(0,0,0,.7),0 0 1px #000; }
  .piece.black { color:var(--bp); text-shadow:0 1px 2px rgba(255,255,200,.3); }

  /* Panels */
  .panel { width:200px; display:flex; flex-direction:column; gap:14px; }
  .panel-box { background:var(--panel); border:1px solid var(--border); border-radius:2px; padding:14px; }
  .panel-title { font-family:'Playfair Display',serif; font-size:.8rem; letter-spacing:.12em; color:var(--gold); text-transform:uppercase; margin-bottom:10px; border-bottom:1px solid var(--border); padding-bottom:6px; }
  .captured-row { font-size:22px; line-height:1.4; min-height:28px; word-break:break-all; }
  .captured-row.wc { color:var(--wp); text-shadow:0 1px 2px rgba(0,0,0,.8); }
  .captured-row.bc { color:var(--bp); background:rgba(255,255,255,.05); border-radius:2px; padding:2px 4px; }
  #history { max-height:170px; overflow-y:auto; display:flex; flex-direction:column; gap:3px; }
  #history::-webkit-scrollbar { width:4px; }
  #history::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }
  .history-entry { font-size:.82rem; color:var(--muted); padding:2px 4px; border-radius:2px; }
  .history-entry:last-child { color:var(--text); background:rgba(255,255,255,.04); }

  /* Difficulty selector */
  .diff-row { display:flex; gap:6px; margin-bottom:2px; }
  .diff-btn {
    flex:1; font-family:'Playfair Display',serif; font-size:.7rem; letter-spacing:.06em;
    background:transparent; border:1px solid var(--border); color:var(--muted);
    padding:6px 4px; cursor:pointer; transition:all .2s; text-transform:uppercase; border-radius:1px;
  }
  .diff-btn:hover { border-color:var(--gold); color:var(--text); }
  .diff-btn.active { border-color:var(--gold); color:var(--gold); background:rgba(201,168,76,.08); }

  .btn {
    font-family:'Playfair Display',serif; font-size:.8rem; letter-spacing:.1em;
    background:transparent; border:1px solid var(--gold); color:var(--gold);
    padding:8px 16px; cursor:pointer; transition:all .2s; width:100%; text-transform:uppercase;
  }
  .btn:hover { background:var(--gold); color:var(--bg); }

  /* Thinking dots */
  .dots::after { content:''; animation:dots 1.2s steps(4,end) infinite; }
  @keyframes dots {
    0%  { content:''; }
    25% { content:'.'; }
    50% { content:'..'; }
    75% { content:'...'; }
  }

  /* Promo modal */
  #promo-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.75); z-index:100; align-items:center; justify-content:center; }
  #promo-modal.show { display:flex; }
  .promo-box { background:var(--panel); border:2px solid var(--gold); padding:28px 32px; text-align:center; }
  .promo-title { font-family:'Playfair Display',serif; color:var(--gold); margin-bottom:20px; font-size:1.2rem; letter-spacing:.1em; }
  .promo-pieces { display:flex; gap:16px; justify-content:center; }
  .promo-piece { font-size:52px; cursor:pointer; padding:8px 12px; border:1px solid transparent; border-radius:2px; transition:all .15s; }
  .promo-piece:hover { border-color:var(--gold); background:rgba(201,168,76,.1); }
  .promo-piece.white { color:var(--wp); text-shadow:0 1px 3px rgba(0,0,0,.8); }
  .promo-piece.black { color:var(--bp); }

  /* Result overlay */
  #result-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.8); z-index:200; align-items:center; justify-content:center; }
  #result-overlay.show { display:flex; }
  .result-box { background:var(--panel); border:2px solid var(--gold); padding:40px 56px; text-align:center; animation:fadeIn .4s ease; }
  @keyframes fadeIn { from{opacity:0;transform:scale(.95)} to{opacity:1;transform:scale(1)} }
  .result-icon { font-size:4rem; margin-bottom:8px; }
  .result-title { font-family:'Playfair Display',serif; font-size:2rem; color:var(--gold); margin-bottom:8px; }
  .result-sub { color:var(--muted); margin-bottom:24px; font-size:1.1rem; }
  .result-btn { font-family:'Playfair Display',serif; font-size:.9rem; letter-spacing:.12em; background:var(--gold); border:none; color:var(--bg); padding:12px 32px; cursor:pointer; text-transform:uppercase; transition:opacity .2s; }
  .result-btn:hover { opacity:.85; }
</style>
</head>
<body>
<h1>♟ CHESS</h1>
<p class="subtitle">You play <strong>White</strong> · Bot plays <strong>Black</strong></p>

<div class="game-wrap">
  <!-- Left panel -->
  <div class="panel">
    <div class="panel-box">
      <div class="panel-title">Captured</div>
      <div style="margin-bottom:6px;font-size:.72rem;color:var(--muted)">Bot took (your pieces):</div>
      <div class="captured-row wc" id="cap-white"></div>
      <div style="margin-top:10px;margin-bottom:6px;font-size:.72rem;color:var(--muted)">You took (bot pieces):</div>
      <div class="captured-row bc" id="cap-black"></div>
    </div>
    <div class="panel-box">
      <div class="panel-title">History</div>
      <div id="history"></div>
    </div>
  </div>

  <!-- Board -->
  <div class="board-section">
    <div class="turn-indicator white" id="turn-indicator">Your Turn (White)</div>
    <div class="coords">
      <div class="coord-row" id="rank-labels"></div>
      <div>
        <div id="board"></div>
        <div class="coord-col" id="file-labels"></div>
      </div>
    </div>
  </div>

  <!-- Right panel -->
  <div class="panel">
    <div class="panel-box">
      <div class="panel-title">Difficulty</div>
      <div class="diff-row">
        <button class="diff-btn" id="diff-easy"   onclick="setDiff('easy')">Easy</button>
        <button class="diff-btn active" id="diff-medium" onclick="setDiff('medium')">Med</button>
        <button class="diff-btn" id="diff-hard"   onclick="setDiff('hard')">Hard</button>
      </div>
    </div>
    <div class="panel-box">
      <button class="btn" onclick="newGame()">New Game</button>
    </div>
    <div class="panel-box">
      <div class="panel-title">How to Play</div>
      <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
        You are <strong style="color:var(--text)">White</strong>. Click a piece then click a highlighted square to move.<br><br>
        The bot thinks automatically after your move.<br><br>
        Castling, en passant &amp; promotion all work.
      </div>
    </div>
  </div>
</div>

<!-- Promotion Modal -->
<div id="promo-modal">
  <div class="promo-box">
    <div class="promo-title">Promote Your Pawn</div>
    <div class="promo-pieces" id="promo-pieces"></div>
  </div>
</div>

<!-- Result Overlay -->
<div id="result-overlay">
  <div class="result-box">
    <div class="result-icon" id="result-icon">♛</div>
    <div class="result-title" id="result-title">Checkmate!</div>
    <div class="result-sub"   id="result-sub">White wins</div>
    <button class="result-btn" onclick="newGame()">Play Again</button>
  </div>
</div>

<script>
let state = null, selected = null, legalMoves = [], polling = null;
const FILES='abcdefgh', RANKS='87654321';

document.getElementById('rank-labels').innerHTML = RANKS.split('').map(r=>`<div class="coord">${r}</div>`).join('');
document.getElementById('file-labels').innerHTML = FILES.split('').map(f=>`<div class="coord">${f}</div>`).join('');

async function fetchState() {
  const r = await fetch('/state');
  state = await r.json();
  render();
}
async function getMoves(r,c) {
  const res = await fetch(`/moves?r=${r}&c=${c}`);
  return (await res.json()).moves;
}
async function doMove(fr,fc,tr,tc) {
  await fetch('/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fr,fc,tr,tc})});
  await fetchState();
  // If it's now bot's turn, start polling for bot completion
  if (state && state.turn === 'B' && (state.status==='playing'||state.status==='check')) {
    startBotPoll();
  }
}
async function doPromote(kind) {
  await fetch('/promote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind})});
  document.getElementById('promo-modal').classList.remove('show');
  await fetchState();
  if (state && state.turn==='B' && (state.status==='playing'||state.status==='check')) startBotPoll();
}
async function newGame() {
  selected=null; legalMoves=[]; stopPoll();
  document.getElementById('result-overlay').classList.remove('show');
  await fetch('/reset',{method:'POST'});
  await fetchState();
}
async function setDiff(d) {
  await fetch('/difficulty',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({difficulty:d})});
  ['easy','medium','hard'].forEach(x=>document.getElementById(`diff-${x}`).classList.remove('active'));
  document.getElementById(`diff-${d}`).classList.add('active');
}

function startBotPoll() {
  stopPoll();
  // Trigger bot move server-side
  fetch('/bot_move', {method:'POST'});
  // Poll until bot is done
  polling = setInterval(async () => {
    await fetchState();
    if (!state.bot_thinking) stopPoll();
  }, 300);
}
function stopPoll() {
  if (polling) { clearInterval(polling); polling=null; }
}

async function onSquareClick(r,c) {
  if (!state) return;
  if (state.status==='checkmate'||state.status==='stalemate') return;
  if (state.promotion_pending) return;
  if (state.turn !== 'W') return; // bot's turn, don't allow clicks
  const piece = state.board[r][c];
  if (selected && legalMoves.some(m=>m[0]===r&&m[1]===c)) {
    await doMove(selected[0],selected[1],r,c);
    selected=null; legalMoves=[]; return;
  }
  if (piece && piece.color===state.turn) {
    selected=[r,c]; legalMoves=await getMoves(r,c); render(); return;
  }
  selected=null; legalMoves=[]; render();
}

function render() {
  if (!state) return;
  const pieces=state.board;
  const lastMove=state.last_move;
  const lastSet=lastMove?new Set([`${lastMove[0]},${lastMove[1]}`,`${lastMove[2]},${lastMove[3]}`]):new Set();
  let checkKing=null;
  if (state.status==='check'||state.status==='checkmate') {
    for (let r=0;r<8;r++) for (let c=0;c<8;c++) {
      const p=pieces[r][c];
      if (p&&p.kind==='K'&&p.color===state.turn) checkKing=`${r},${c}`;
    }
  }
  const moveSet=new Set(legalMoves.map(m=>`${m[0]},${m[1]}`));
  // Highlight bot's last move distinctly
  const botLastSet = (state.turn==='W' && lastMove) ? lastSet : new Set();

  let html='';
  for (let r=0;r<8;r++) for (let c=0;c<8;c++) {
    const p=pieces[r][c], key=`${r},${c}`;
    const isLight=(r+c)%2===0;
    const isSel=selected&&selected[0]===r&&selected[1]===c;
    const isMoveHint=moveSet.has(key);
    const isLast=lastSet.has(key);
    const isCheck=checkKing===key;
    let cls=`sq ${isLight?'light':'dark'}`;
    if (isSel) cls+=' selected';
    else if (isCheck) cls+=' in-check';
    else if (isLast) cls+=' last-move';
    if (isMoveHint) cls+=' move-hint';
    if (isMoveHint&&p) cls+=' has-piece';
    const disabled = state.turn!=='W' ? ' style="cursor:default"' : '';
    const pHtml=p?`<span class="piece ${p.color==='W'?'white':'black'}">${p.symbol}</span>`:'';
    html+=`<div class="${cls}"${disabled} onclick="onSquareClick(${r},${c})">${pHtml}</div>`;
  }
  document.getElementById('board').innerHTML=html;

  // Turn indicator
  const ti=document.getElementById('turn-indicator');
  if (state.status==='checkmate') {
    const w=state.winner==='W'?'You win':'Bot wins';
    ti.textContent=`${w} — Checkmate!`; ti.className='turn-indicator end';
  } else if (state.status==='stalemate') {
    ti.textContent='Stalemate — Draw'; ti.className='turn-indicator end';
  } else if (state.bot_thinking) {
    ti.innerHTML='Bot is thinking<span class="dots"></span>'; ti.className='turn-indicator thinking';
  } else if (state.status==='check' && state.turn==='W') {
    ti.textContent='Your Turn — CHECK!'; ti.className='turn-indicator check';
  } else if (state.status==='check' && state.turn==='B') {
    ti.textContent="Bot's Turn — CHECK!"; ti.className='turn-indicator check';
  } else {
    ti.textContent=state.turn==='W'?'Your Turn (White)':"Bot Thinking...";
    ti.className=state.turn==='W'?'turn-indicator white':'turn-indicator black';
  }

  document.getElementById('cap-white').textContent=state.captured_w.map(p=>p.symbol).join('');
  document.getElementById('cap-black').textContent=state.captured_b.map(p=>p.symbol).join('');

  const hist=document.getElementById('history');
  hist.innerHTML=state.move_history.map(m=>`<div class="history-entry">${m}</div>`).join('');
  hist.scrollTop=hist.scrollHeight;

  // Difficulty buttons
  ['easy','medium','hard'].forEach(d=>{
    const el=document.getElementById(`diff-${d}`);
    if(el) el.classList.toggle('active', d===state.difficulty);
  });

  // Promotion modal (human only)
  if (state.promotion_pending) {
    const [tr,tc]=state.promotion_pending;
    const prom=state.board[tr][tc];
    const color=prom?prom.color:'W';
    const syms={Q:color==='W'?'♕':'♛',R:color==='W'?'♖':'♜',B:color==='W'?'♗':'♝',N:color==='W'?'♘':'♞'};
    document.getElementById('promo-pieces').innerHTML=
      Object.entries(syms).map(([k,s])=>`<div class="promo-piece ${color==='W'?'white':'black'}" onclick="doPromote('${k}')">${s}</div>`).join('');
    document.getElementById('promo-modal').classList.add('show');
  }

  // Result overlay
  if (state.status==='checkmate'||state.status==='stalemate') {
    setTimeout(()=>{
      if (state.status==='checkmate') {
        const human = state.winner==='W';
        document.getElementById('result-icon').textContent=human?'🏆':'🤖';
        document.getElementById('result-title').textContent=human?'You Win!':'Bot Wins!';
        document.getElementById('result-sub').textContent=human?'Excellent play — Checkmate!':'The bot wins by Checkmate';
      } else {
        document.getElementById('result-icon').textContent='🤝';
        document.getElementById('result-title').textContent='Stalemate';
        document.getElementById('result-sub').textContent='The game is a draw';
      }
      document.getElementById('result-overlay').classList.add('show');
    },600);
  }
}
fetchState();
</script>
</body>
</html>"""

# ─── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, data, code=200):
        body = data.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_html(HTML)
        elif self.path == "/state":
            self.send_json(GAME.to_json())
        elif self.path.startswith("/moves"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            r, c = int(qs["r"][0]), int(qs["c"][0])
            moves = GAME.get_moves(r, c)
            self.send_json(json.dumps({"moves": moves}))
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/move":
            GAME.move(body["fr"], body["fc"], body["tr"], body["tc"])
            self.send_json(GAME.to_json())
        elif self.path == "/promote":
            GAME.promote(body["kind"])
            self.send_json(GAME.to_json())
        elif self.path == "/reset":
            GAME.reset()
            self.send_json(GAME.to_json())
        elif self.path == "/difficulty":
            GAME.difficulty = body.get("difficulty", "medium")
            self.send_json(GAME.to_json())
        elif self.path == "/bot_move":
            # Run bot in background thread so HTTP response is immediate
            threading.Thread(target=GAME.do_bot_move, daemon=True).start()
            self.send_json(GAME.to_json())
        else:
            self.send_response(404); self.end_headers()

# ─── Launch ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PORT = 5173
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"\n  ♟  Chess vs Bot — {url}")
    print(f"  You play White. Bot plays Black.")
    print(f"  Opening browser… (Ctrl+C to quit)\n")
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Goodbye!")