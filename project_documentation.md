# Leighton Virtual Waiter for Perpetual Bistro

**Final Project — Artificial Intelligence Lab**
**Section:** BSCS 3112 Artificial Intelligence (9420-AY12)
**Members:** Marco Enrico Go, Lee Michiko Garcia, Samuel Angelo Arnaiz
**Date submitted:** November 6, 2026

---

## 1. Project Overview

Leighton is a fully local, offline conversational restaurant agent for Perpetual Bistro. It takes orders via voice or text, browses the menu, answers ingredient and allergen questions, modifies active carts, and produces an itemized receipt on confirmation. All data lives in a single SQLite database. There are no cloud dependencies: the language model runs locally via Ollama (`qwen2.5:3b`), speech-to-text runs locally via faster-whisper (`base.en`), and text-to-speech runs locally via pyttsx3 (Windows SAPI5).

The system satisfies the Lesson 6 stateful-workflow requirements and the Lesson 7 Milestone 1 (voice I/O, FSM, SQLite tool engine) and Milestone 2 (integrated web dashboard) requirements.

**Deliverables included:**

| File | Purpose |
|---|---|
| `init_restaurant_db.sql` | SQLite schema and 16-item seed dataset |
| `init_db.py` | Database initialization script |
| `db_tools.py` | 16 tool functions with argument validation |
| `fsm_controller.py` | Five-state FSM + deterministic pre-parsers + Ollama client |
| `speech_engine.py` | STT (faster-whisper) and TTS (pyttsx3) wrappers |
| `app.py` | Flask entry point |
| `ui_dashboard/` | HTML/CSS/JS for the web dashboard |
| `virtual_waiter_prototype.py` | Required CLI prototype (Lesson 6) |
| `logs/sample_conversation_log.json` | 32-turn conversation log with tool calls and state transitions |
| `pair_collaboration_log.md` | Detailed tandem collaboration log |
| `project_documentation.md` | This document |

---

## 2. System Architecture

The system has five layers:

1. **Interface.** Two front ends share the same backend: a Flask web dashboard (`app.py` + `ui_dashboard/`) for voice interaction, and a CLI (`virtual_waiter_prototype.py`) used for reproducible testing and log generation.
2. **Conversational agent.** `fsm_controller.py` contains the `LeightonAgent` class: the five-state FSM, deterministic Python pre-parsers for every state-changing intent, and the Ollama client for read-only queries and polite refusals.
3. **Speech.** `speech_engine.py` wraps STT and TTS. It is decoupled from both interfaces, so either front end can use it.
4. **Tool layer.** `db_tools.py` exposes 16 functions that read and write SQLite. Every function validates its own arguments before touching the database — the LLM is never trusted to supply valid arguments.
5. **Persistence.** `restaurant.db` (SQLite) is the single source of truth for menu, stock, sessions, and order lines.

```
┌─────────────────────────────────────────────────────────────┐
│  INTERFACE                                                  │
│  ┌──────────────────────┐       ┌──────────────────────┐    │
│  │  Web UI (Flask)      │       │  CLI Prototype       │    │
│  └──────────┬───────────┘       └──────────┬───────────┘    │
└─────────────┼──────────────────────────────┼────────────────┘
              └──────────────┬───────────────┘
                             ▼
              ┌──────────────────────────────┐
              │   LeightonAgent              │
              │   (fsm_controller.py)        │
              │                              │
              │   • deterministic pre-parsers│
              │   • 5-state FSM              │
              │   • Ollama client            │
              └────┬───────────┬─────────────┘
                   │           │
        ┌──────────┘           └────────────┐
        ▼                                   ▼
┌──────────────────┐            ┌──────────────────────┐
│  Ollama          │            │  Speech Engine       │
│  qwen2.5:3b      │            │  STT + TTS (offline) │
└──────────────────┘            └──────────────────────┘
        │
        │ tool calls
        ▼
┌────────────────────────────────────────────┐
│  Tool Layer (db_tools.py)                  │
│  16 functions with argument validation     │
└──────────────────┬─────────────────────────┘
                   ▼
┌────────────────────────────────────────────┐
│  SQLite (restaurant.db)                    │
│  menu_items · table_sessions ·             │
│  order_line_items                          │
└────────────────────────────────────────────┘
```

**Flow of one turn.** The interface calls `LeightonAgent.handle_user_message(text)`. The FSM runs its deterministic pre-parsers first. If any pre-parser handles the message, the LLM is skipped entirely. Otherwise, the message is sent to Ollama's `/api/chat` endpoint with `tools=[...]`; tool calls are executed with argument validation and the loop continues up to six iterations. The reply, FSM state, session id, and tool-call record are returned to the interface.

---

## 3. FSM State Diagram

Five states:

| State | Purpose |
|---|---|
| `STATE_GREETING` | Welcome the guest and capture the table number |
| `STATE_TAKING_ORDER` | Handle queries, add/modify/remove items, change notes |
| `STATE_REVIEW` | Present the itemized order with totals for verification |
| `STATE_CONFIRMED` | Order is committed; stock deducted; receipt printed |
| `STATE_COMPLETED` | Session closed; next input invites a new order |

Transitions:

| From | Trigger | To |
|---|---|---|
| GREETING | table number received | TAKING_ORDER |
| TAKING_ORDER | cart change | TAKING_ORDER |
| TAKING_ORDER | "show my order" / "finalize" | REVIEW |
| REVIEW | cart modification | TAKING_ORDER |
| REVIEW | "confirm" | CONFIRMED |
| REVIEW | cancel with "yes" | COMPLETED |
| CONFIRMED | any next user turn | COMPLETED |
| COMPLETED | any post-confirm edit intent | COMPLETED (deterministic refusal) |

```
GREETING ──(table number)──► TAKING_ORDER ◄──(cart change)── REVIEW
                                 │                              ▲
                                 │ "show my order"              │
                                 │ "finalize"                   │
                                 ▼                              │
                              REVIEW ─────(cart modification)───┘
                                 │
                                 ├─(confirm)──► CONFIRMED ──(next turn)──► COMPLETED
                                 │
                                 └─(cancel with "yes")────────────────────► COMPLETED
```

**Fifth state rationale.** The Lesson 6 brief described "five distinct states" but listed only four. `STATE_COMPLETED` resolves this inconsistency and provides a distinct polite-farewell state, allowing the next customer to start a fresh session without restarting the server.

---

## 4. Database Schema

Three tables:

| Table | Columns |
|---|---|
| `menu_items` | id (PK), name (UNIQUE), category, description, ingredients, price, stock_qty, allergens |
| `table_sessions` | session_id (PK), table_no, status (OPEN \| REVIEWING \| CONFIRMED \| CANCELLED), created_at, confirmed_at |
| `order_line_items` | line_id (PK), session_id (FK), item_id (FK), quantity, special_instructions, added_at |

`order_line_items` cascades on `table_sessions` deletion. `table_sessions.status` is enforced with a SQL `CHECK` constraint, so invalid states cannot be written even by a buggy tool.

**Seed data.** 16 items across 5 categories (Appetizers, Main Dishes, Rice, Drinks, Desserts). Two items are seeded out of stock (Vegetable Spring Rolls, Grilled Bangus) and one at low stock (Mango Graham, 2 units) so edge-case tests are reproducible.

**Business rules enforced inside the tool layer** (not the LLM):

- Service fee = 10% of subtotal.
- Maximum quantity per line = 20.
- Stock is deducted only at confirmation time, not at add time.
- Adding never exceeds remaining stock.
- Notes are replaced, not appended (empty string is rejected).
- Same item + same note merges into one line; same item + different note creates a second line.
- A confirmed session is locked; further edits are refused.
- Stock is re-checked at confirmation.

---

## 5. Tool Layer (`db_tools.py`)

Sixteen functions, all returning `{"status": "success" | "error", "message": ..., ...}`:

| Tool | Purpose |
|---|---|
| `create_session`, `get_session` | Open or fetch a table session |
| `get_menu_by_category`, `get_all_menu`, `get_item_by_name` | Menu lookups |
| `check_item_allergen`, `search_menu_by_allergen` | Allergen queries (single item and whole menu) |
| `check_item_availability` | Stock pre-check |
| `add_item_to_order` | Add or increment a line |
| `change_item_quantity` | Set a line's absolute quantity |
| `update_item_instructions` | Replace a line's note (empty rejected) |
| `remove_item_from_order` | Remove a line or a specific quantity of one |
| `clear_session_cart` | Empty the cart |
| `view_current_order`, `calculate_totals` | Cart snapshot with subtotal, fee, total |
| `confirm_order` | Lock the session and deduct stock |
| `cancel_order` | Cancel and clear |

`TOOL_SCHEMAS` (JSON schema list) is sent to Ollama with every request. `TOOL_REGISTRY` maps tool names to their Python callables.

---

## 6. Speech Pipeline (`speech_engine.py`)

**STT.** faster-whisper `base.en` on CPU with int8 quantization. Audio arrives as a 16 kHz mono WAV recorded in the browser via the Web Audio API and encoded client-side. The engine passes a numpy array directly to Whisper, bypassing PyAV. An `initial_prompt` biases recognition toward menu vocabulary (Adobo, Sinigang, Kare-Kare), so dish names survive the audio round-trip. The model (~145 MB) is cached after first use at `%USERPROFILE%\.cache\huggingface\hub`, making subsequent runs fully offline — a critical requirement for the live-defense scenario.

**TTS.** pyttsx3 (Windows SAPI5). Prices are rewritten from "₱220.00" to "220 pesos" before synthesis so the voice reads them naturally. The web UI plays TTS audio through an `<audio>` element with status indicators (Listening / Thinking / Speaking / Idle).

Both are lazy-loaded and warmed at server start so the first user request is fast.

---

## 7. Web Dashboard (`app.py` + `ui_dashboard/`)

Served by Flask at `http://127.0.0.1:5000/`. Components:

- Left panel with the restaurant heading and a status pill (Idle / Listening / Thinking / Speaking).
- Right menu panel with categories, prices, and out-of-stock markers.
- Order cart showing items, quantities, per-line customization badges, subtotal, 10% service fee, and grand total.
- Manual +/− quantity controls (human-in-the-loop overrides).
- A prominent "Confirm my Order" button with an "Are you sure?" Yes/No modal.
- A microphone button inside the chat drawer that records, transcribes, and submits in one action.
- A collapsible chat drawer with text input, Send, and auto-TTS of Leighton's replies.

**API endpoints.** `/api/menu`, `/api/chat`, `/api/order`, `/api/state`, `/api/stt`, `/api/tts`, `/api/cart/update`, `/api/cart/clear`, `/api/review`, `/api/confirm`, `/api/reset`. All endpoints proxy to the same `LeightonAgent` instance, so voice and text produce identical ordering results.

---

## 8. Tandem Collaboration

Work followed the Driver / Navigator tandem model. A single Driver performed the direct implementation of each file; the two Navigators reviewed the approach, checked the work against the activity requirements, reasoned through implementation decisions, and verified the Driver's output.

| Task / File | Driver | Navigators | Driver Focus | Navigator Focus | Verification Test |
|---|---|---|---|---|---|
| `init_restaurant_db.sql` | Marco Enrico Go | Lee Michiko Garcia, Samuel Angelo Arnaiz | Writing DDL table structures | Reviewing foreign key constraints and seed data | Database builds without SQL errors via `init_db.py` |
| `db_tools.py` | Marco Enrico Go | Lee Michiko Garcia, Samuel Angelo Arnaiz | Coding SQLite CRUD functions | Writing inventory guard checks | `add_item_to_order()` blocks items when `stock_qty = 0` |
| `fsm_controller.py` | Lee Michiko Garcia | Marco Enrico Go, Samuel Angelo Arnaiz | Implementing state class logic | Verifying transition rules and guardrails | Cannot jump from GREETING directly to CONFIRMED |
| `speech_engine.py` | Marco Enrico Go | Lee Michiko Garcia, Samuel Angelo Arnaiz | Configuring STT microphone input | Tuning TTS voice speed and pitch | Microphones capture audio and speak back agent responses |
| `app.py` & UI | Lee Michiko Garcia | Marco Enrico Go, Samuel Angelo Arnaiz | Assembling main execution loop | Designing frontend CSS layout | Cart UI updates automatically when a tool call occurs |

Every member served as both Driver and Navigator at some point in the project. A detailed task-by-task log with the specific design decisions at each stage is included in `pair_collaboration_log.md`.

---

## 9. Tested Edge Cases

The following scenarios were exercised against the current code and verified to behave deterministically, with no model hallucination:

- Out-of-stock items refused at the tool layer (Vegetable Spring Rolls, Grilled Bangus).
- Quantity above the 20-unit per-line cap refused.
- Allergen scan returns the correct set for both positive ("with peanuts") and negative ("gluten-free") phrasings, and correctly refuses a specific dish that contains a named allergen.
- Unsupported recipe changes ("make the Pork Sinigang vegetarian") refused with a scripted message that offers to add a note instead.
- Off-topic questions (weather, capitals, arithmetic) receive a scripted refusal with different wording before and after confirmation.
- Multi-item adds with mixed quantities and one note parsed correctly.
- Ambiguous adds ("add another one") trigger a clarifying question.
- Quantity change, note change (replace not append), and partial removal ("remove 1 of 3") update the cart accurately.
- "Remove the note on X" is refused with guidance; "remove everything" clears the cart deterministically.
- Table numbers in word form ("Table Five", "I'm at table four") are captured as well as digit form.
- Cancel is a two-step confirmation; declining leaves the order untouched.
- After a confirmed order, every modification intent (add, remove, cancel, change note, change quantity) is refused by a deterministic pre-parser, not by the model.
- "Start a new order" or the new-session button resets cleanly to GREETING, allowing a second demo without restarting the server.

Every path is exercised in `logs/sample_conversation_log.json`, a 32-turn session covering all five FSM states.

---

## 10. Setup and Run

**Prerequisites.** Windows 10/11, Python 3.10+, Ollama running locally with `qwen2.5:3b` pulled, and Python packages from `requirements.txt` (`flask`, `faster-whisper`, `pyttsx3`, `requests`).

From the project root, in PowerShell with the virtual environment activated:

```
python init_db.py
python app.py
```

Then open `http://127.0.0.1:5000/` in Chrome or Edge and click the chat icon to begin.

To run the CLI instead:

```
python virtual_waiter_prototype.py
```

The CLI writes `logs/sample_conversation_log.json` on `/quit`.

**Offline requirement.** After the first STT run (which downloads the Whisper model), the entire application runs without internet. This was verified by disconnecting Wi-Fi, restarting the server, and completing a full voice ordering session.

---

## 11. Known Limitations and Future Work

- The model `qwen2.5:3b` is chosen for RAM budget, not capability. All state-changing intents are pre-parsed deterministically; the model is consulted only for read-only conversational queries and polite refusals. This is a deliberate architecture choice — it makes the system reproducible and immune to hallucination on the paths that matter.
- Browser Web Speech API and cloud TTS/STT were evaluated and rejected because they either require internet or make the system non-deterministic. Offline operation is a hard requirement of the live defense.
- A "clear note" action is not implemented; notes must be replaced, which the system enforces with a helpful refusal.
- A hover description on each menu item was scoped but deferred; descriptions are available through the chat ("Tell me about Halo-Halo").

A 3–5 minute walkthrough video accompanies this submission and demonstrates a live voice ordering session end-to-end.

---

*End of document.*