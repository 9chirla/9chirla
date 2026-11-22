#!/usr/bin/env python3
"""Play README chess from an issue title. Rewrites the block between the markers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import chess

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STATE = ROOT / "assets" / "chess.json"
BEGIN = "<!-- chess:start -->"
END = "<!-- chess:end -->"

PIECES = str.maketrans(
    {
        "P": "♙",
        "N": "♘",
        "B": "♗",
        "R": "♖",
        "Q": "♕",
        "K": "♔",
        "p": "♟",
        "n": "♞",
        "b": "♝",
        "r": "♜",
        "q": "♛",
        "k": "♚",
    }
)


def starting_state() -> dict:
    return {"fen": chess.STARTING_FEN, "last_player": ""}


def load_state() -> dict:
    if not STATE.exists():
        return starting_state()
    return json.loads(STATE.read_text())


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def issue_link(repo: str, title: str) -> str:
    body = quote("Submit this issue. Leave the title exactly as it is.")
    return f"https://github.com/{repo}/issues/new?title={quote(title)}&body={body}"


def board_art(board: chess.Board) -> str:
    lines = []
    for rank in range(8, 0, -1):
        cells = []
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank - 1))
            cells.append(piece.symbol().translate(PIECES) if piece else "·")
        lines.append(f"{rank}  " + " ".join(cells))
    lines.append("   a b c d e f g h")
    return "\n".join(lines)


def move_table(board: chess.Board, repo: str) -> str:
    groups: dict[str, list[str]] = {}
    for move in board.legal_moves:
        src = chess.square_name(move.from_square).upper()
        dst = chess.square_name(move.to_square).upper()
        groups.setdefault(src, []).append(dst)
    rows = ["| From | To |", "| --- | --- |"]
    for src in sorted(groups):
        links = []
        for dst in sorted(set(groups[src])):
            title = f"Chess: Move {src} to {dst}"
            links.append(f"[{dst}]({issue_link(repo, title)})")
        rows.append(f"| {src} | {' · '.join(links)} |")
    return "\n".join(rows)


def render_block(state: dict, repo: str) -> str:
    board = chess.Board(state["fen"])
    if board.is_checkmate():
        status = "Checkmate."
    elif board.is_stalemate():
        status = "Stalemate."
    elif board.is_game_over():
        status = "Game over."
    else:
        side = "White" if board.turn == chess.WHITE else "Black"
        status = f"{side} to move."

    parts = [
        f"**{status}**",
        "",
        "<pre>",
        board_art(board),
        "</pre>",
        "",
    ]
    if not board.is_game_over():
        parts.extend(
            [
                "Click a destination. GitHub opens an issue. The workflow plays the move and closes it.",
                "",
                move_table(board, repo),
                "",
            ]
        )
    new_game = issue_link(repo, "Chess: Start new game")
    parts.append(f"[Start a new game]({new_game})")
    parts.append("")
    return "\n".join(parts)


def write_readme(block: str) -> None:
    text = README.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit("README is missing chess markers")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    replacement = f"{BEGIN}\n{block}{END}"
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit("Could not replace the chess block")
    README.write_text(updated)


def resolve_move(board: chess.Board, uci: str) -> chess.Move | None:
    for suffix in ("", "q"):
        try:
            move = chess.Move.from_uci(uci + suffix)
        except ValueError:
            continue
        if move in board.legal_moves:
            return move
    return None


def play(title: str, author: str, owner: str, repo: str) -> tuple[bool, str]:
    state = load_state()
    board = chess.Board(state["fen"])
    new_game = re.fullmatch(r"Chess:\s*Start new game", title.strip(), re.I)
    move_match = re.fullmatch(
        r"Chess:\s*Move\s+([A-H][1-8])\s+to\s+([A-H][1-8])",
        title.strip(),
        re.I,
    )

    if new_game:
        if not board.is_game_over() and author != owner and state.get("last_player"):
            block = render_block(state, repo)
            write_readme(block)
            return False, "A game is in progress. Only the owner can start a new one."
        state = starting_state()
        save_state(state)
        write_readme(render_block(state, repo))
        return True, "New game. White to move."

    if not move_match:
        return False, "Use a title like `Chess: Move E2 to E4`."

    if board.is_game_over():
        return False, "This game is over. Start a new one."

    if state.get("last_player") and state["last_player"] == author:
        return False, "The same player cannot take two turns in a row."

    uci = (move_match.group(1) + move_match.group(2)).lower()
    move = resolve_move(board, uci)
    if move is None:
        return False, f"{move_match.group(1).upper()} to {move_match.group(2).upper()} is not legal here."

    board.push(move)
    state["fen"] = board.fen()
    state["last_player"] = author
    save_state(state)
    write_readme(render_block(state, repo))
    played = move.uci().upper()
    return True, f"Played {played[:2]} to {played[2:4]}."


def main() -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "9chirla/9chirla")
    title = os.environ.get("ISSUE_TITLE", "")
    author = os.environ.get("ISSUE_AUTHOR", "")
    owner = os.environ.get("REPO_OWNER", "9chirla")

    if os.environ.get("CHESS_RENDER_ONLY") == "1":
        state = load_state()
        save_state(state)
        write_readme(render_block(state, repo))
        result = {"changed": True, "reply": "Rendered the current board."}
    else:
        changed, reply = play(title, author, owner, repo)
        result = {"changed": changed, "reply": reply}

    Path("/tmp/chess-result.json").write_text(json.dumps(result) + "\n")
    print(result["reply"])


if __name__ == "__main__":
    main()
