# Leighton Virtual Waiter — Perpetual Bistro

A local, offline conversational restaurant agent. The user talks to **Leighton**, a
virtual waiter that browses a menu, takes orders, answers questions about
ingredients and allergens, modifies the order, and confirms it. All menu,
price, stock, and order data lives in a local SQLite database.

The project is built for the AI course lab on Conversational State Machines
and Workflows (Lab Activity 6.1). It runs entirely on a laptop — **no cloud
APIs**.

---

## Project Overview

Leighton is a stateful, multi-turn conversational agent that:

- Maintains session memory across many turns.
- Uses a Finite State Machine (FSM) to enforce conversation flow.
- Calls Python tools that read/write SQLite (menu, stock, cart, totals).
- Refuses to invent menu items, prices, stock, or order contents — the
  database is the single source of truth.
- Ships with two interfaces: a plain CLI (the activity's required
  deliverable) and a Textual-based terminal UI (the activity's Option 2).

The LLM in use is **`qwen2.5:3b`** running through a local Ollama server.

---

## Current Scope

### Implemented and working

- Interactive CLI: `backend/virtual_waiter_prototype.py`
- Textual terminal UI: `backend/tui_app.py`
- Five-state FSM with deterministic pre-parsers for all state-changing
  intents (see "Finite State Machine" below)
- SQLite database with 16 menu items and full argument validation on
  every tool
- Per-turn JSON conversation logging (written by the CLI)
- Native Ollama tool calling for read-only queries (menu lookup,
  ingredient descriptions, allergen scans)
- Polite refusals for off-topic questions and unsupported recipe changes

### Not yet implemented

The following features are **planned but not in the current codebase**:

- Web UI (Flask + HTML/CSS/JS) — the activity's Option 1
- Speech-to-text (STT)
- Text-to-speech (TTS)
- Wake phrase "Hey, Leighton"

They should not be assumed to work. See the "Future Work" section at the
bottom.

---

## Technology Stack and Prerequisites

| Component | Version / Notes |
|-----------|-----------------|
| Python | 3.10 or newer (developed and tested on 3.12) |
| Ollama | Latest stable — running locally |
| LLM model | **`qwen2.5:3b`** — verified to return structured `tool_calls` from Ollama's `/api/chat` endpoint |
| SQLite | Bundled with Python (`sqlite3` module) |
| Python deps | `textual>=0.50`, `requests>=2.31` |
| Terminal | Windows Terminal recommended for the TUI (alt-screen support required) |

No paid APIs. No cloud calls.

---

## Installation and Setup (Windows)

Run these commands in **PowerShell** from the project root
(`Leighton-virtual-waiter`).

### 1. Verify Python

```powershell
python --version
```

Expect Python 3.10+. If `python` points to a non-Windows interpreter (e.g.
MSYS2), use the full path to your Windows Python executable for the next
step.

### 2. Create and activate a virtual environment

```powershell
& "C:\Path\To\Python312\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
```

You must see `(.venv)` at the start of your prompt for every command below.

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then activate again.

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

If `requirements.txt` is missing for any reason, run:

```powershell
pip install textual requests
```

### 4. Verify Ollama

```powershell
ollama --version
ollama list
```

`qwen2.5:3b` must appear in the list. If it does not:

```powershell
ollama pull qwen2.5:3b
```

Make sure the Ollama server is running (it usually runs as a background
service; `ollama serve` starts it manually if needed).

### 5. Prepare the database

```powershell
cd database
python init_db.py
```

Expected output:

```
[OK] Database created: ...\database\restaurant.db
[OK] Menu items inserted: 16
     - Appetizers: 3 items
     - Desserts: 3 items
     - Drinks: 3 items
     - Main Dishes: 5 items
     - Rice: 2 items
[OK] Out-of-stock items (for testing): ['Vegetable Spring Rolls', 'Grilled Bangus']
```

Then return to the project root:

```powershell
cd ..
```

**Warning:** re-running `init_db.py` resets the database and deletes every
open session and cart. Only run it when you want a fresh state. The CLI
entry point (`virtual_waiter_prototype.py`) also resets the database at
startup by design; the TUI does not.

---

## How to Run

### CLI — `virtual_waiter_prototype.py`

From the project root, with the venv active:

```powershell
cd backend
python virtual_waiter_prototype.py
```

You will see a banner and the first greeting.

At the `You:` prompt, type messages and press Enter. Suggested opening:

```
Hi
Table 5
What appetizers do you have?
Add 1 Chicken Adobo, no onions
Show my order
Confirm my order
Finalize my order
```

#### CLI commands

| Command | Meaning |
|---------|---------|
| `/quit` or `/exit` | End the session and save the log |
| `/state` | Print the current FSM state as JSON |
| `/order` | Print the current order snapshot from SQLite |
| `/reset` | Reset the database and start a new session |

Every CLI session writes `logs/sample_conversation_log.json` on exit.

### TUI — `tui_app.py`

From the `backend/` folder, with the venv active:

```powershell
python tui_app.py
```

You will see:

- A top bar: `PERPETUAL BISTRO — Virtual Waiter`
- A left panel: conversation log
- A right panel: active order table (Item / Qty / Notes / Price) with a
  status line showing the FSM state, table number, subtotal, fee, and total
- A bottom input bar
- A footer with key bindings

#### TUI controls

| Control | Behavior |
|---------|----------|
| Type + Enter | Send a message to Leighton |
| `/menu` or `F2` | Show the full menu grouped by category |
| `/confirm` or `Alt+Enter` or `F3` | Review then confirm the order |
| `/clear` or `F4` | Clear the current cart |
| `Ctrl+C` | Quit |

**Important:** VS Code's integrated terminal intercepts some function keys
and Ctrl-letter chords before they reach the TUI. The **text commands
(`/confirm`, `/menu`, `/clear`) always work** and are the guaranteed path.
`Alt+Enter` and `F3` also work in a standalone Windows Terminal. `F2` and
`F4` were observed to work in VS Code's terminal as well, but this can vary
by terminal emulator.

The TUI runs **in-process** — it imports `fsm_agent.py` and `db_tools.py`
directly, with no HTTP server involved. It does not write a JSON
conversation log; that is a CLI-only behavior.

### Running both at once

The CLI and TUI share the same SQLite database at
`database/restaurant.db`. Avoid running both at the same time against the
same DB — the CLI resets the DB on startup, which would wipe any TUI
session in progress.

---

## Project Structure

```
Leighton-virtual-waiter/
├── README.md                        # this file
├── requirements.txt                 # pip dependencies
├── test_tool_call.py                # quick Ollama tool-calling smoke test
├── pair_collaboration_log.md        # Lab Activity 6.1 deliverable
├── .gitignore
│
├── backend/
│   ├── fsm_agent.py                 # FSM controller + Ollama client + pre-parsers
│   ├── virtual_waiter_prototype.py  # CLI entry point (required deliverable)
│   ├── tui_app.py                   # Textual TUI (activity Option 2)
│   ├── test_fsm_agent.py            # interactive CLI smoke test
│   ├── check_note_change.py         # note-change regex tester
│   └── verify_log.py                # log inspector for sample_conversation_log.json
│
├── database/
│   ├── init_restaurant_db.sql       # schema + 16 seed rows
│   ├── init_db.py                   # runs the SQL file, creates restaurant.db
│   ├── db_tools.py                  # 16 tool functions + Ollama tool schemas
│   ├── restaurant.db                # SQLite database (generated — safe to delete)
│   ├── test_db_tools.py             # scripted test of every tool
│   └── check_stock.py               # quick stock inspection
│
├── logs/
│   └── sample_conversation_log.json # written by the CLI on /quit (required deliverable)
│
├── frontend/                        # reserved — not in use (no Web UI implemented)
└── docs/                            # reserved — empty
```

**Key files to open first:**

- `database/db_tools.py` — every tool and its schema
- `backend/fsm_agent.py` — the FSM, the Ollama loop, and the deterministic pre-parsers
- `backend/virtual_waiter_prototype.py` — the CLI shell and log writer
- `backend/tui_app.py` — the terminal UI

---

## Architecture

```
┌────────────────────────────┐        ┌────────────────────────────┐
│  CLI                       │        │  TUI (Textual)             │
│  virtual_waiter_prototype  │        │  tui_app.py                │
└──────────────┬─────────────┘        └──────────────┬─────────────┘
               │                                     │
               └──────────────┬──────────────────────┘
                              ▼
                   ┌──────────────────────┐
                   │  LeightonAgent         │
                   │  (fsm_agent.py)      │
                   │                      │
                   │  Deterministic       │
                   │  pre-parsers:        │
                   │   • greeting / table │
                   │   • view order       │
                   │   • note change      │
                   │   • allergen scan    │
                   │   • cancel (confirm) │
                   │   • remove item      │
                   │   • change qty       │
                   │   • multi-item add   │
                   │   • single add       │
                   │   • confirm          │
                   │   • off-topic        │
                   └─────┬──────────┬─────┘
                         │          │
                         │          └────► Ollama /api/chat
                         │                 model: qwen2.5:3b
                         │                 with tools=[...]
                         │                 (used only for read-only
                         │                  queries and polite refusals)
                         ▼
                   ┌──────────────────────┐
                   │  db_tools.py         │
                   │  (16 tool functions) │
                   └─────────┬────────────┘
                             ▼
                   ┌──────────────────────┐
                   │  restaurant.db       │
                   │  (single source of   │
                   │   truth)             │
                   └──────────────────────┘
```

### Flow of a single turn (either interface)

1. The interface reads a line of user text and calls
   `LeightonAgent.handle_user_message(text)`.
2. Python shortcut checks run first (greeting, off-topic, review/confirm,
   note change, allergen, cancel, remove, change qty, multi-item add,
   single add). If any of them produces an answer, the LLM is skipped.
3. Otherwise, the message is appended to `self.messages` and sent to
   Ollama's `/api/chat` with `tools=db.TOOL_SCHEMAS`.
4. If the model replies with `tool_calls`, each call is executed by
   `_execute_tool_call`, with argument validation and auto-injection of
   the real `session_id`. Tool results are appended to the history as
   `role="tool"` messages.
5. This loop repeats up to `MAX_TOOL_ITERATIONS = 6` times or until the
   model emits a plain-text reply.
6. The reply, the FSM state, the session id, and the tool calls are
   returned to the interface.

### Deterministic pre-parsers

Because `qwen2.5:3b` was observed to narrate state changes without calling
the corresponding tool, all state-changing intents are handled in Python
before the LLM is invoked. This makes the DB the single source of truth
even when the model misbehaves.

The pre-parsers cover:

- Table number capture
- Off-topic refusal (whitelist + blocklist + math regex)
- Review intent, confirm intent
- Note change on an existing item
- Allergen questions (single-item and whole-menu)
- Cancel with two-step confirmation
- Remove item
- Change quantity
- Multi-item add, single-item add
- Confirm in REVIEW

---

## Finite State Machine

Five states:

| State | Purpose |
|-------|---------|
| `STATE_GREETING` | Welcome the customer and capture the table number |
| `STATE_TAKING_ORDER` | Handle queries, add/modify items, remove items, change notes |
| `STATE_REVIEW` | Present the itemized order with totals for verification |
| `STATE_CONFIRMED` | Order is committed; stock has been deducted; receipt printed |
| `STATE_COMPLETED` | Session is closed; next input will invite a new order |

Transitions:

```
GREETING ──(table number)──► TAKING_ORDER
TAKING_ORDER ◄──(cart change)── REVIEW
TAKING_ORDER ──(review/confirm)──► REVIEW
REVIEW ──(confirm)──► CONFIRMED
REVIEW ──(cancel)──► COMPLETED
CONFIRMED ──(next user turn)──► COMPLETED
```

Note on the fifth state: the activity describes "5 distinct states" but
lists only four. `STATE_COMPLETED` was added to handle the post-confirmation
farewell and to reset session memory for the next customer. This is
documented in `pair_collaboration_log.md`.

---

## Database and Menu

### Schema

Three tables:

```
menu_items
    id, name UNIQUE, category, description, ingredients,
    price REAL, stock_qty INTEGER, allergens TEXT

table_sessions
    session_id TEXT PRIMARY KEY, table_no INTEGER,
    status TEXT CHECK(OPEN|REVIEWING|CONFIRMED|CANCELLED),
    created_at, confirmed_at

order_line_items
    line_id, session_id, item_id, quantity,
    special_instructions, added_at
```

`order_line_items` cascades on `table_sessions` deletion.

### Menu

16 items across 5 categories:

- **Appetizers (3):** Crispy Lumpia Shanghai, Calamari Fritters,
  Vegetable Spring Rolls *(out of stock at seed time)*
- **Main Dishes (5):** Chicken Adobo, Beef Kare-Kare, Pork Sinigang,
  Grilled Bangus *(out of stock at seed time)*, Vegetable Pad Thai
- **Rice (2):** Steamed White Rice, Garlic Fried Rice
- **Drinks (3):** Iced Tea, Fresh Buko Juice, Calamansi Juice
- **Desserts (3):** Halo-Halo, Leche Flan, Mango Graham *(low stock: 2)*

Prices are in Philippine pesos.

### Business rules (implemented in code)

| Rule | Where |
|------|-------|
| Service fee = 10% of subtotal | `SERVICE_FEE_RATE` in `db_tools.py` |
| Maximum quantity per line = 20 | `MAX_QTY_PER_LINE` in `db_tools.py` |
| Stock deduction happens at confirm time, not at add time | `confirm_order()` |
| Adding never exceeds remaining stock | `add_item_to_order()` |
| Notes are free-text on the line item | `special_instructions` column |
| Same item + same note merges into one line | `add_item_to_order()` |
| Same item + different note creates a second line | `add_item_to_order()` |
| Sessions become `REVIEWING` once the first item is added | `add_item_to_order()` |
| Confirmed sessions are locked; further edits are refused | `_validate_session_open()` |
| Stock is re-checked at confirm time | `confirm_order()` |
| Notes can be replaced but not cleared (via CLI) | `update_item_instructions()` rejects empty strings |

### Totals

```
subtotal    = Σ (item.price × line.quantity)
service_fee = round(subtotal × 0.10, 2)
grand_total = round(subtotal + service_fee, 2)
```

---

## Tools Reference

All tools live in `database/db_tools.py`. Every tool validates its
arguments and returns a JSON-serializable dict of the shape
`{"status": "success" | "error", "message": ..., ...}`.

| Tool | Purpose |
|------|---------|
| `create_session(table_no, session_id=None)` | Open a new session (not exposed to the LLM — called by the greeting pre-parser) |
| `get_session(session_id)` | Fetch a session row |
| `get_menu_by_category(category)` | List all items in a category |
| `get_all_menu()` | List the full menu |
| `get_item_by_name(item_name)` | Fetch one item by name |
| `check_item_allergen(item_id, allergen)` | Does the item list the allergen? |
| `search_menu_by_allergen(allergen, contain=True)` | Scan the whole menu for items with/without an allergen |
| `check_item_availability(item_name, qty=1)` | Stock check before adding |
| `add_item_to_order(session_id, item_name, qty, instructions='')` | Add or increase a line |
| `change_item_quantity(session_id, item_name, new_qty, instructions=None)` | Set an existing line's quantity |
| `update_item_instructions(session_id, item_name, new_instructions)` | Replace a line's note (empty string rejected) |
| `remove_item_from_order(session_id, item_name, instructions=None)` | Delete a line |
| `clear_session_cart(session_id)` | Delete all lines from a session |
| `view_current_order(session_id)` | Return the cart with totals |
| `calculate_totals(session_id)` | Subtotal, fee, grand total |
| `confirm_order(session_id)` | Lock the session, deduct stock, return receipt |
| `cancel_order(session_id)` | Cancel and clear the session |

`TOOL_SCHEMAS` is the JSON schema list sent to Ollama with every `/api/chat`
call. `TOOL_REGISTRY` maps tool names to their Python callables.

---

## Conversation Logging

The CLI (`virtual_waiter_prototype.py`) writes a JSON log to
`logs/sample_conversation_log.json` when the user runs `/quit` or `/exit`.

Log structure:

```
{
  "lab": "Lesson 6 - ...",
  "agent": "Leighton",
  "model": "qwen2.5:3b (Ollama)",
  "started_at": "...",
  "ended_at": "...",
  "final_state": "STATE_COMPLETED",
  "final_session_id": "...",
  "final_table_no": ...,
  "final_order": { ... },
  "turns": [
    {
      "turn": 0,
      "user": "...",
      "state_before": "STATE_GREETING",
      "state_after": "STATE_TAKING_ORDER",
      "reply": "...",
      "tool_calls": [
        {
          "name": "create_session",
          "arguments": { ... },
          "result_status": "success",
          "result_message": "..."
        }
      ]
    }
  ]
}
```

The checked-in `logs/sample_conversation_log.json` is a 32-turn session
that covers every required test scenario from the lab:

- Menu browsing across categories
- Ingredient descriptions
- Whole-menu allergen scan (preference phrasing and allergy phrasing)
- Single-item allergen check
- Unsupported customization refusal
- Off-topic refusal
- Multi-item add with a note
- Ambiguous add (clarification question)
- Single-item add
- Out-of-stock refusal (returns `add_item_to_order -> error`)
- Quantity change
- Note change
- Item removal
- Order review (twice)
- Cancel with confirmation, then decline
- Final confirmation (`STATE_CONFIRMED`)
- Farewell (`STATE_COMPLETED`)

You can inspect a log with the helper script:

```powershell
cd backend
python verify_log.py
```

This prints turn count, state coverage, every tool call and its result,
the final order, and the user messages. It does **not** modify the log.

The TUI does not write a JSON log (only the CLI does).

---

## Testing and Verification

### Verified via transcripts

The following scenarios were exercised against the current code and their
outcomes are visible in `logs/sample_conversation_log.json` and the
development test transcripts:

- Database init
- Table number capture and FSM transition to `STATE_TAKING_ORDER`
- Menu browsing by category
- Ingredient description retrieval
- Single-item allergen check
- Whole-menu allergen scan (with correct polarity for "with", "free",
  "allergic")
- Unsupported customization refusal
- Off-topic refusal (capital, weather, math, election)
- Multi-item add with a note
- Ambiguous add → clarification question
- Single-item add
- Out-of-stock refusal with `add_item_to_order -> error`
- Quantity change
- Note change (replacement, not appending)
- Item removal
- Order review (`STATE_REVIEW`)
- Cart modification in REVIEW returns to `STATE_TAKING_ORDER`
- Cancel with two-step confirmation (accepted and declined)
- Final confirm (`STATE_CONFIRMED`)
- Post-confirm farewell (`STATE_COMPLETED`)
- Stock deduction after confirm

The TUI was verified through the pasted terminal transcripts for:

- Chat and order panel rendering
- F2 / `/menu` menu display
- F4 / `/clear` cart clearing with `STATE_REVIEW` → `STATE_TAKING_ORDER`
  reset
- `/confirm` and `Alt+Enter` confirm flow
- Right-panel synchronization after every turn

### Not systematically tested

- The behavior of the LLM path on unusual phrasings outside the
  pre-parser patterns
- Running with `qwen2.5:7b` instead of `3b`
- Non-Windows platforms
- Multiple lines of the same item with different notes
  (`update_item_instructions` returns an error, which is documented as a
  deliberate limitation)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: requests` or `textual` | venv not active, or installed into a different Python | Activate `.venv`, then `pip install -r requirements.txt` |
| `Cannot reach Ollama at http://localhost:11434` | Ollama server not running | Run `ollama serve` in another terminal |
| `model "qwen2.5:3b" not found` | Model not pulled | `ollama pull qwen2.5:3b` |
| `Session 'T5-S001' not found` | Fresh DB after code ran | Re-run `python init_db.py` from `database/` |
| `Tool 'x' is not registered` | Tool missing from `TOOL_REGISTRY` | Add the function to `TOOL_REGISTRY` in `db_tools.py` |
| Leighton calls the wrong tool | Small-model confusion | Add or extend a Python pre-parser in `fsm_agent.py` |
| Leighton says "$" instead of "₱" | LLM style drift | The persona instructs ₱; the CLI's deterministic replies always use ₱ |
| `sqlite3.OperationalError: no such table` | DB missing or wrong path | Run `init_db.py`; check `DB_PATH` in `db_tools.py` |
| TUI renders garbled or misaligned | Terminal emulator not compatible with alt-screen | Use **Windows Terminal**; avoid legacy PowerShell host |
| F3 or Ctrl+K does nothing in the TUI | VS Code intercepts the key | Use `/confirm` (text command) — guaranteed path |
| `TypeError: handle_user_message() missing 1 required positional argument` | Calling the method without a string | Pass the user text as a string |

---

## Developer Handoff and Extension Guide

### Where to look first

- **Behavior is wrong for a specific phrase** → `backend/fsm_agent.py`, the
  `_handle_*` pre-parsers.
- **A tool call is rejected or malformed** → `database/db_tools.py`, the
  tool function itself, and `_execute_tool_call` in `fsm_agent.py`.
- **Menu / price / stock is wrong** → `database/init_restaurant_db.sql` and
  `init_db.py`.
- **Persona style is wrong** → `BASE_PERSONA` in `fsm_agent.py`.
- **TUI colors need changing** → the labeled `COLOR CONFIGURATION` block
  near the top of `backend/tui_app.py`.

### How to add a new tool

1. Add a function to `database/db_tools.py`:
   ```python
   def my_new_tool(arg1: str, arg2: int) -> dict:
       # validate args, hit SQLite, return {"status": "success"|"error", ...}
   ```
2. Add a schema entry to `TOOL_SCHEMAS` in the same file, matching the
   function's arguments.
3. Add the mapping to `TOOL_REGISTRY`:
   ```python
   "my_new_tool": my_new_tool,
   ```
4. If the new tool modifies the cart, add its name to the `modify_tools`
   set in `_maybe_transition_after_tools` in `fsm_agent.py` so REVIEW
   transitions back to `STATE_TAKING_ORDER`.
5. If the new tool needs `session_id` and the model might omit it, add its
   name to the `session_tools` set in `_execute_tool_call`.
6. Update `BASE_PERSONA` with a short rule describing when to call it.
7. Test directly first:
   ```python
   import db_tools; print(db_tools.my_new_tool("x", 1))
   ```
8. Then test through the CLI and the TUI.

### Preserving state / SQLite sync

- Never write the cart or menu directly from the LLM path. Always go
  through a tool function in `db_tools.py`.
- Never read from the model's memory — read from `view_current_order()` or
  `get_item_by_name()`.
- After every successful cart-modifying tool, the FSM must move back to
  `STATE_TAKING_ORDER` if it was in `STATE_REVIEW`.

### Testing changes safely

1. Copy `logs/sample_conversation_log.json` aside before re-running.
2. Reset the DB only if the change requires it:
   `cd database && python init_db.py`.
3. Run `python test_db_tools.py` to smoke-test the tools directly.
4. Run `python virtual_waiter_prototype.py` and paste the transcript back
   for review.
5. Run `python tui_app.py` to sanity-check the UI.

---

## Future Work

The following features are **planned or discussed but not implemented**:

- **Web UI (Flask + HTML/CSS/JS).** The activity's Option 1. The
  `frontend/` folder is reserved but empty. A Flask server would wrap
  `LeightonAgent` behind HTTP endpoints (`/api/chat`, `/api/order`,
  `/api/menu`) with an HTML frontend polling `/api/order` every few
  seconds. Nothing in the current architecture blocks this — the agent is
  already usable in-process by any frontend.
- **Speech-to-text (STT).** The browser's Web Speech API is the simplest
  path but requires network access on most browsers. An offline
  alternative (Vosk, faster-whisper) is possible but not chosen yet.
- **Text-to-speech (TTS).** The browser's SpeechSynthesis API is the
  simplest offline path on Windows.
- **Wake phrase "Hey, Leighton".** Requires a dedicated engine
  (openWakeWord, Porcupine). Not implemented. Trade-offs are not resolved
  yet.
- **Clear-note command.** `update_item_instructions` currently rejects
  empty strings. A dedicated "Clear note" action should use a separate
  tool rather than loosening this guard.

### What can be reused

The entire `backend/fsm_agent.py` and `database/db_tools.py` layer can be
reused unchanged by a Web UI. The Flask server would only need to hold a
single `LeightonAgent` in memory behind HTTP endpoints. Nothing in the FSM
assumes a terminal.

---

## Lab Deliverables

`Lab Activity 6.1` required these files:

| Deliverable | Path | Status |
|-------------|------|--------|
| SQLite schema & seed | `database/init_restaurant_db.sql` | ✅ |
| Python tool functions | `database/db_tools.py` | ✅ |
| FSM controller | `backend/fsm_agent.py` | ✅ |
| Interactive CLI | `backend/virtual_waiter_prototype.py` | ✅ |
| Tandem collaboration log | `pair_collaboration_log.md` | ✅ |
| Multi-turn conversation log | `logs/sample_conversation_log.json` | ✅ |

Optional (per the activity):

| Optional feature | Status |
|------------------|--------|
| Web-based dashboard (Option 1) | Not implemented |
| Terminal-based TUI (Option 2) | ✅ Implemented as `backend/tui_app.py` |