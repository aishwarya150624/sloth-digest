# 🦥 Sloth Digest

Wake up to a 2-line summary of your group chats, written by an AI that never leaves your laptop.

Export a chat (WhatsApp: *Chat → More → Export chat → Without media*), drop the `.txt` in a folder, and run one command. Sloth Digest reads only the **new** messages since last time and writes a digest:

```
## family_group (13 new messages)
TL;DR: <two short sentences>
Plans
- <dates, places>
Needs you
- [ ] <things asked of you>
```

## Why open-source AI?
- **Private:** your family chats never touch a cloud API. Summarizing them with a hosted model means handing a stranger your conversations.
- **Free forever:** a nightly run over many chats would add up on a paid API. Locally it costs electricity.
- **Offline:** works without internet.
- **Swappable:** `--model qwen2.5:7b` for sharper summaries, or a small model for an old laptop.

## Built for laziness
- **Incremental:** remembers what it has already summarized (`.sloth_digest_state.json`), so you never re-read old news.
- **Long chats OK:** big backlogs are summarized in chunks, then merged (map-reduce).
- **Flags what's yours:** `--me Asha` surfaces things asked of, or about, you.
- **Never blocks:** if the model is down, you still get a stats digest (message counts, top talkers).
- **Handles real exports:** multi-line messages, system notices, "media omitted", and both common timestamp formats.
- **Zero dependencies:** Python 3.8+ standard library only.

## Quick start
```bash
ollama pull llama3.2:3b
python sloth_digest.py demo --me Asha        # try the included sample chat
python sloth_digest.py ~/chats --me Asha     # your own folder of exports
```
Digests are saved to `digests/digest-YYYY-MM-DD.md`.

## Fully lazy mode (every morning at 6)
```cron
0 6 * * * /usr/bin/python3 /path/to/sloth_digest.py ~/chats --me YourName
```

## Options
| Flag | Meaning |
|------|---------|
| `--me NAME` | Your name in the chats |
| `--model NAME` | Ollama model (default `llama3.2:3b`) |
| `--peek` | Show the digest without marking messages as read |
| `--no-ai` | Stats only, no model |
| `--out DIR` | Where to save digests (default `digests/`) |

Set `OLLAMA_HOST` to use a different Ollama server.

## Tests
```bash
python -m unittest discover -s tests -v
```
Tests use a fake Ollama server, so no model download is needed.

## Limits
Summaries come from a small model and can miss nuance or misread sarcasm. Treat it as a skim aid, not a record. Only text exports are supported for now.

## License
MIT
