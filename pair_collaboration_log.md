# Pair Collaboration Log — Leighton Virtual Waiter

## Project Overview

The Leighton Virtual Waiter is a stateful restaurant ordering agent built for the AI course lab on Conversational State Machines and Workflows. It presents a five-state Finite State Machine that manages a customer conversation, invokes Python tools that read and write a local SQLite database, and records every turn to a JSON conversation log. Two interfaces are delivered: `virtual_waiter_prototype.py`, the required command-line prototype, and `tui_app.py`, a Textual-based terminal interface matching the activity's Option 2 layout. The agent runs locally against Ollama using the `qwen2.5:3b` model, with no cloud dependencies.

## Collaboration Model

Each of the six tasks was carried out with one member acting as Driver and the other two as Navigators. The Driver performed the direct implementation — editing code, running commands, and configuring the environment. The Navigators reviewed the approach, checked the work against the activity's requirements, reasoned through implementation decisions, and verified the Driver's output. Members held the Driver role on different tasks and the Navigator role on others, so all three participated in both roles throughout the project.

## Task Breakdown and Role Rotations

### Task 1 — Database schema, seed data, and menu modeling

- **Driver:** Marco Enrico Go designed and implemented the SQLite schema for the three tables (`menu_items`, `table_sessions`, `order_line_items`), including foreign keys and the status constraint, and authored `init_restaurant_db.sql` and `init_db.py` with the 16-item seed dataset across five categories.
- **Navigators:** Lee Michiko Garcia and Samuel Angelo Arnaiz reviewed the schema against the activity's Step-by-Step requirements, checked whether the extra columns were justified, and verified that the seeded stock and allergen values would support later edge-case testing.
- **Key design decision:** An `ingredients` column was added to `menu_items` beyond what the activity lists, so the agent could distinguish recorded allergen data from full ingredient composition. Two items were seeded out of stock and one at low stock so the out-of-stock and quantity-cap paths could be exercised during testing.

### Task 2 — Python tool layer with argument validation

- **Driver:** Marco Enrico Go implemented the tool layer in `db_tools.py`, including the four required tools (`get_menu_by_category`, `check_item_allergen`, `add_item_to_order`, `view_current_order`) plus supporting tools for quantity change, item removal, note change, allergen scan, totals, confirmation, and cancellation, each with input validation and a uniform return shape.
- **Navigators:** Lee Michiko Garcia and Samuel Angelo Arnaiz reviewed the return-dict contract every tool had to follow, identified which tools needed `session_id`, and checked the validation rules for quantity bounds, stock availability, and rejection of empty note strings.
- **Key design decision:** Every tool returns `{"status": "success" | "error", "message": ..., ...}` and validates its own arguments in Python rather than trusting values supplied by the model, keeping SQLite as the single source of truth for menu, stock, and order state.

### Task 3 — FSM controller and Ollama integration

- **Driver:** Lee Michiko Garcia implemented `fsm_agent.py`, including the five-state conversation loop, the Ollama `/api/chat` integration with native `tools` support, the tool-dispatch loop that executes Qwen's `tool_calls`, and the JSON schema list (`TOOL_SCHEMAS`) that Qwen reads.
- **Navigators:** Samuel Angelo Arnaiz and Marco Enrico Go reviewed the transition rules between states, confirmed that illegal transitions (such as confirming outside `STATE_REVIEW`) were blocked by the dispatch layer, and reasoned through the message history shape Ollama expects for tool exchanges.
- **Key design decision:** A fifth state, `STATE_COMPLETED`, was introduced to resolve the activity's inconsistency (it asks for five states but names only four) and to handle the post-confirmation farewell. Native Ollama tool calling was chosen over prompt-based JSON parsing after verifying that `qwen2.5:3b` returns a proper `tool_calls` array from the `/api/chat` endpoint.

### Task 4 — Deterministic pre-parser architecture for state-changing actions

- **Driver:** Lee Michiko Garcia implemented the pre-parser layer in `fsm_agent.py` — the set of deterministic Python handlers that intercept state-changing intents (table capture, view order, add item, remove item, change quantity, change note, allergen scan, cancel with confirmation, off-topic refusal, and confirm-in-review) before the LLM is invoked.
- **Navigators:** Marco Enrico Go and Samuel Angelo Arnaiz reviewed each pre-parser against observed failure modes, discussed which intents should remain on the LLM path, and checked that read-only questions still routed correctly through the model.
- **Key design decision:** During testing, `qwen2.5:3b` frequently narrated state changes without calling the corresponding tool and sometimes contradicted the tool results it received. All state-changing intents were therefore moved to deterministic Python pre-parsers; the LLM is now used only for genuine conversational queries and polite refusals.

### Task 5 — Item modification feature and CLI prototype with JSON logging

- **Driver:** Lee Michiko Garcia implemented the item-modification feature (`update_item_instructions` in `db_tools.py` plus its pre-parser in `fsm_agent.py`) and authored `virtual_waiter_prototype.py`, the required CLI entry point that runs the agent interactively and writes a per-turn JSON log to `logs/sample_conversation_log.json`.
- **Navigators:** Marco Enrico Go and Samuel Angelo Arnaiz reviewed the note-replacement behavior versus note-append behavior, checked that empty note strings were rejected, and tested the log file's turn structure against the activity's "tool calls, state transitions, and database state updates" requirement.
- **Key design decision:** The note-change pre-parser uses two narrow regex patterns — `change the note on X to Y` and `change X's note to Y` — so the model cannot misroute a phrasing such as "change the note to 'requested vegetarian'" into the recipe-change refusal path. Clearing a note via the CLI is deliberately rejected; the note must be replaced, not emptied.

### Task 6 — Textual TUI and comprehensive sample_conversation_log.json

- **Driver:** Samuel Angelo Arnaiz implemented `tui_app.py`, the Textual-based terminal interface described by the activity's Option 2 — a chat panel, a live order table with Item/Qty/Notes/Price columns, a status line showing FSM state and totals, and function-key plus text-command shortcuts. He also produced the final 32-turn `sample_conversation_log.json` used as the submitted log artifact.
- **Navigators:** Lee Michiko Garcia and Marco Enrico Go reviewed the TUI's synchronization with SQLite after each turn, verified that clearing the cart reset the FSM from `STATE_REVIEW` back to `STATE_TAKING_ORDER`, and confirmed that the log covered all five states and every rubric edge case (out-of-stock, allergen, unsupported customization, off-topic refusal, cancellation, quantity change, note change).
- **Key design decision:** VS Code's integrated terminal intercepts some function keys and Ctrl-letter chords before they reach the TUI. The interface therefore exposes text commands (`/confirm`, `/menu`, `/clear`) as the guaranteed path and keeps function keys as secondary bindings, so the application works consistently regardless of which terminal emulator is used.