"""The review page: one self-contained HTML file with the period's sessions as timelines and its
patterns (008 decision 6). Every text is escaped; nothing is served or sent anywhere.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_path

from mufuse.companion.store import Store
from mufuse.journal.patterns import find, pattern_lines
from mufuse.journal.timeline import timeline

_STYLE = """
:root { --bg:#fff; --ink:#1a1a1a; --dim:#666; --line:#e3e3e3; --accent:#e8590c; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#141414; --ink:#eee; --dim:#999; --line:#2b2b2b; }
}
body { background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,sans-serif;
  max-width:46rem; margin:2rem auto; padding:0 16px; }
h1 { font-size:1.4rem; }
h2 { font-size:1.1rem; margin-top:2rem; border-bottom:1px solid var(--line); }
ol { list-style:none; padding:0; } li { padding:.2rem 0; border-bottom:1px solid var(--line); }
time { color:var(--dim); font-variant-numeric:tabular-nums; margin-right:.6rem; }
.kind { color:var(--accent); font-size:.8rem; text-transform:uppercase; margin-right:.4rem; }
.note { color:var(--dim); }
"""


def default_dir() -> Path:
    return user_data_path("mufuse", appauthor=False) / "review"


def render(store: Store, *, since: float, until: float, title: str) -> str:
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>MuFuse review</title><style>{_STYLE}</style></head><body>",
        f"<h1>{e(title)}</h1>",
        "<p class='note'>Made on this computer from your own check-ins. Numbers are counted in"
        " code; patterns are hypotheses.</p>",
        "<h2>Patterns</h2><ol>",
    ]
    lines = pattern_lines(find(store, since=since, until=until))
    parts.append(f"<p class='note'>{e(lines[0])}</p>")
    parts += [f"<li>{e(line)}</li>" for line in lines[1:]]
    parts.append("</ol>")
    for session, start, _ in store.sessions(since=since):
        if start > until:
            continue
        day = datetime.fromtimestamp(start).strftime("%a %d %b %H:%M")
        parts.append(f"<h2>Session {session} · {e(day)}</h2><ol>")
        for ev in timeline(store, session):
            hm = datetime.fromtimestamp(ev.t).strftime("%H:%M")
            parts.append(
                f"<li><time>{hm}</time><span class='kind'>{e(ev.kind)}</span>{e(ev.text)}</li>"
            )
        parts.append("</ol>")
    parts.append("</body></html>")
    return "\n".join(parts)


def write(store: Store, *, since: float, until: float, out: Path | None = None) -> Path:
    stamp = datetime.fromtimestamp(until).strftime("%Y%m%d")
    path = out or default_dir() / f"review-{stamp}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = datetime.fromtimestamp(since).strftime("%d %b")
    last = datetime.fromtimestamp(until).strftime("%d %b %Y")
    path.write_text(
        render(store, since=since, until=until, title=f"MuFuse review, {first} to {last}"),
        encoding="utf-8",
    )
    return path
