#!/usr/bin/env python3
"""
sloth_digest: a morning summary of your group chats, written by a local open-weight model.

Feed it WhatsApp-style exported chats (.txt). It remembers what it has already
summarized, so each run covers only NEW messages. Everything runs on localhost
through Ollama; no chat text ever leaves your machine. Standard library only.
"""
import argparse, json, os, re, sys, urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

STATE_NAME = ".sloth_digest_state.json"
TS = r"\[?(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]?\s*[-\u2013]?\s*"
MSG = re.compile("^" + TS + r"([^:]+?):\s(.*)$")
SYS = re.compile("^" + TS)  # timestamped line with no sender = system notice
MEDIA = ("<media omitted>", "image omitted", "video omitted", "sticker omitted", "audio omitted")


def ollama_url():
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def parse_chat(path: Path):
    """Return a list of (sender, text). Handles multi-line messages; skips system notices."""
    msgs = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.replace("\u200e", "").strip("\ufeff")
        m = MSG.match(line)
        if m:
            msgs.append([m.group(3).strip(), m.group(4).strip()])
        elif SYS.match(line):
            continue
        elif msgs and line.strip():
            msgs[-1][1] += " " + line.strip()
    return [tuple(m) for m in msgs]


def is_media(text):
    return text.lower().strip() in MEDIA


def chunk(lines, budget=5000):
    cur, size, out = [], 0, []
    for ln in lines:
        if size + len(ln) > budget and cur:
            out.append("\n".join(cur)); cur, size = [], 0
        cur.append(ln); size += len(ln) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def ask(model, prompt):
    body = json.dumps({"model": model, "stream": False, "format": "json",
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(ollama_url() + "/api/chat", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def summarize(model, lines, me):
    """Map-reduce: summarize each chunk, then merge. Returns a dict."""
    parts = chunk(lines)
    if len(parts) == 1:
        source = parts[0]
    else:
        points = []
        for p in parts:
            r = ask(model, f"Chat messages:\n{p}\n\nList the key points as short strings. "
                           'Reply as JSON: {"points": ["..."]}')
            points += [str(x) for x in r.get("points", [])]
        source = "\n".join("- " + p for p in points)
    who = f' Flag anything asked of, or about, "{me}".' if me else ""
    r = ask(model, f"Group chat content:\n{source}\n\nWrite a TL;DR of at most 2 short sentences, "
                   f"then list concrete plans (with dates/places) and action items.{who} "
                   'Reply as JSON: {"tldr": "...", "plans": ["..."], "action_items": ["..."]}')
    return {"tldr": str(r.get("tldr", "")), "plans": [str(x) for x in r.get("plans", [])],
            "action_items": [str(x) for x in r.get("action_items", [])]}


def stats_only(new):
    top = Counter(s for s, _ in new).most_common(3)
    media = sum(1 for _, t in new if is_media(t))
    return {"tldr": f"{len(new)} new messages (AI summary unavailable). "
                    "Most active: " + ", ".join(f"{n} ({c})" for n, c in top) + f". {media} media items.",
            "plans": [], "action_items": []}


def process(path, model, me, state, use_ai=True):
    msgs = parse_chat(path)
    start = state.get(path.name, 0)
    if start > len(msgs):   # a fresh export replaced the old file
        start = 0
    new = msgs[start:]
    if not new:
        return None, len(msgs)
    lines = [f"{s}: {t[:300]}" for s, t in new if not is_media(t)]
    result = None
    if use_ai and lines:
        try:
            result = summarize(model, lines, me)
        except Exception as e:
            print(f"! model unavailable for {path.name} ({e}); using stats only", file=sys.stderr)
    section = result or stats_only(new)
    section.update(name=path.stem, count=len(new))
    return section, len(msgs)


def render(sections, day):
    out = [f"# 🦥 Morning digest, {day}", ""]
    if not sections:
        return "\n".join(out + ["Nothing new. Enjoy the quiet."]) + "\n"
    for s in sections:
        out += [f"## {s['name']} ({s['count']} new messages)", f"**TL;DR:** {s['tldr']}", ""]
        if s["plans"]:
            out += ["**Plans**"] + [f"- {p}" for p in s["plans"]] + [""]
        if s["action_items"]:
            out += ["**Needs you**"] + [f"- [ ] {a}" for a in s["action_items"]] + [""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="a chat .txt file or a folder of them")
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--me", default="", help="your name in the chats, to flag things for you")
    ap.add_argument("--out", type=Path, default=Path("digests"))
    ap.add_argument("--peek", action="store_true", help="show digest without marking messages as read")
    ap.add_argument("--no-ai", action="store_true", help="stats only, no model")
    a = ap.parse_args()

    src = a.source.expanduser().resolve()
    files = [src] if src.is_file() else sorted(src.glob("*.txt"))
    state_file = (src.parent if src.is_file() else src) / STATE_NAME
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    sections = []
    for f in files:
        sec, total = process(f, a.model, a.me, state, use_ai=not a.no_ai)
        if sec:
            sections.append(sec)
            if not a.peek:
                state[f.name] = total
    md = render(sections, date.today().isoformat())
    print(md)
    if sections and not a.peek:
        a.out.mkdir(exist_ok=True)
        (a.out / f"digest-{date.today().isoformat()}.md").write_text(md)
        state_file.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
