#!/usr/bin/env python3
"""Write assets/terminal.svg from public GitHub language and contribution counts."""

from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "terminal.svg"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { totalContributions }
      totalCommitContributions
    }
    repositories(
      first: 40
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
    ) {
      nodes {
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Markup and packaging noise. The card keeps the languages you actually ship.
SKIP = {"CSS", "HTML", "Shell", "Dockerfile", "Procfile", "Makefile", "SCSS"}
RENAME = {"PLpgSQL": "SQL"}


def fetch(user: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-terminal",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.load(res)
    if payload.get("errors"):
        raise SystemExit(json.dumps(payload["errors"]))
    return payload["data"]["user"]


def languages(user: dict) -> list[tuple[str, int, float]]:
    totals: dict[str, int] = defaultdict(int)
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in SKIP:
                continue
            totals[RENAME.get(name, name)] += edge["size"]
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    total = sum(size for _, size in ranked) or 1
    top = ranked[:5]
    return [(name, size, size / total) for name, size in top]


def render(login: str, commits: int, contributions: int, langs: list[tuple[str, int, float]]) -> str:
    width = 680
    header_h = 36
    row_h = 26
    rows = 6 + len(langs)
    height = header_h + 20 + row_h * rows + 16
    font = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Terminal stats for {escape(login)}">',
        f'<rect width="{width}" height="{height}" fill="#0D1117"/>',
        f'<rect width="{width}" height="{header_h}" fill="#161B22"/>',
        '<circle cx="20" cy="18" r="5.5" fill="#FF5F57"/>',
        '<circle cx="38" cy="18" r="5.5" fill="#FEBC2E"/>',
        '<circle cx="56" cy="18" r="5.5" fill="#28C840"/>',
        f'<text x="74" y="23" fill="#8B949E" font-family="{font}" font-size="13">naveen@london — teletype</text>',
    ]
    y = header_h + 32

    def text(x: int, content: str, fill: str) -> None:
        parts.append(
            f'<text x="{x}" y="{y}" fill="{fill}" font-family="{font}" font-size="15">{escape(content)}</text>'
        )

    text(20, "$ whoami", "#3DDC97")
    y += row_h
    text(36, login, "#C9D1D9")
    y += row_h
    text(36, "Graduate Success Analyst · London", "#8B949E")
    y += row_h
    text(20, "$ commits --past-year", "#3DDC97")
    y += row_h
    text(36, f"{commits} commits   ·   {contributions} contributions", "#C9D1D9")
    y += row_h
    text(20, "$ languages", "#3DDC97")
    y += row_h

    max_size = max((size for _, size, _ in langs), default=1)
    bar_x = 168
    bar_w = 280
    for name, size, share in langs:
        text(36, name, "#C9D1D9")
        bar_y = y - 12
        parts.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="12" fill="#21262D"/>')
        fill_w = max(8, round(bar_w * (size / max_size))) if size else 0
        parts.append(f'<rect x="{bar_x}" y="{bar_y}" width="{fill_w}" height="12" fill="#3DDC97"/>')
        parts.append(
            f'<text x="{bar_x + bar_w + 14}" y="{y}" fill="#8B949E" font-family="{font}" font-size="15">{round(share * 100)}%</text>'
        )
        y += row_h

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    login = os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "9chirla"
    token = os.environ["GITHUB_TOKEN"]
    data = fetch(login, token)
    collection = data["contributionsCollection"]
    svg = render(
        login,
        collection["totalCommitContributions"],
        collection["contributionCalendar"]["totalContributions"],
        languages(data),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
