"""
app.py - Flask entry point for the Leighton Virtual Waiter web application.

Serves the dashboard UI at / and exposes JSON/audio API endpoints used by
ui_dashboard/static/app.js.

This module does NOT reset the database on startup. Run init_db.py manually
for a fresh state. This prevents accidental data loss during development.
"""
from __future__ import annotations
import base64
import io
import os
import sys
import tempfile

from flask import Flask, jsonify, request, render_template, send_file, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import db_tools as db
from fsm_controller import LeightonAgent
from speech_engine import SpeechEngine, get_engine

TEMPLATE_DIR = os.path.join(HERE, "ui_dashboard", "templates")
STATIC_DIR = os.path.join(HERE, "ui_dashboard", "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# Single in-process agent, matching how the TUI worked.
# Restart the server or POST /api/reset to start a fresh session.
AGENT = LeightonAgent()
SPEECH: SpeechEngine = get_engine()

# Prime the STT prompt with menu vocabulary.
_menu = db.get_all_menu()
if _menu.get("status") == "success":
    SPEECH.set_menu_prompt([item["name"] for item in _menu["items"]])

# Force-load the STT model now so the first user request is fast and
# so a missing model cache surfaces at startup rather than mid-demo.
_warm = SPEECH.warmup()
if _warm.get("status") == "success":
    print("[OK] STT model warmed up.", flush=True)
else:
    print(f"[WARN] {_warm.get('message')}", flush=True)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _order_snapshot():
    if not AGENT.session_id:
        return None
    res = db.view_current_order(AGENT.session_id)
    if res.get("status") == "success":
        return res["order"]
    return None


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.get("/images/<path:filename>")
def images(filename):
    img_dir = os.path.join(HERE, "ui_dashboard", "images")
    return send_from_directory(img_dir, filename)

# ------------------------------------------------------------
# Read-only API
# ------------------------------------------------------------
@app.get("/api/menu")
def api_menu():
    res = db.get_all_menu()
    if res.get("status") != "success":
        return jsonify(res), 500
    return jsonify(res)


@app.get("/api/state")
def api_state():
    return jsonify({
        "state": AGENT.state,
        "session_id": AGENT.session_id,
        "table_no": AGENT.table_no,
        "order": _order_snapshot(),
    })


@app.get("/api/order")
def api_order():
    snap = _order_snapshot()
    return jsonify({
        "status": "success" if snap else "empty",
        "order": snap,
        "state": AGENT.state,
        "table_no": AGENT.table_no,
    })


# ------------------------------------------------------------
# Chat
# ------------------------------------------------------------
@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"status": "error",
                        "message": "No message provided."}), 400
    result = AGENT.handle_user_message(message)
    return jsonify({
        "status": "success",
        "reply": result.get("reply", ""),
        "state": result.get("state"),
        "session_id": result.get("session_id"),
        "table_no": result.get("table_no"),
        "tool_calls": [
            {"name": tc["name"],
             "result_status": tc["result"].get("status")}
            for tc in result.get("tool_calls", [])
        ],
        "order": _order_snapshot(),
    })


# ------------------------------------------------------------
# Speech
# ------------------------------------------------------------
@app.post("/api/stt")
def api_stt():
    """Accept audio as multipart 'audio' OR JSON {audio_b64}.

    Both paths write a temp .wav and call SpeechEngine.transcribe()."""
    audio_bytes = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        b64 = data.get("audio_b64") or ""
        if not b64:
            return jsonify({"status": "error",
                            "message": "audio_b64 required."}), 400
        try:
            audio_bytes = base64.b64decode(b64)
        except Exception as e:
            return jsonify({"status": "error",
                            "message": f"Invalid base64: {e}"}), 400
    elif "audio" in request.files:
        audio_bytes = request.files["audio"].read()
    else:
        return jsonify({
            "status": "error",
            "message": "Send audio as multipart 'audio' or JSON audio_b64.",
        }), 400

    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
        result = SPEECH.transcribe(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return jsonify(result)


@app.post("/api/tts")
def api_tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"status": "error",
                        "message": "No text provided."}), 400
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        res = SPEECH.synthesize(text, tmp_path)
        if res.get("status") != "success":
            return jsonify(res), 500
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return send_file(io.BytesIO(audio_bytes), mimetype="audio/wav")


# ------------------------------------------------------------
# Manual cart controls (used by the +/- buttons in Phase 6)
# ------------------------------------------------------------
@app.post("/api/cart/update")
def api_cart_update():
    data = request.get_json(silent=True) or {}
    item_name = (data.get("item_name") or "").strip()
    action = (data.get("action") or "").strip().lower()
    raw_instructions = data.get("instructions")
    # Frontend always sends a string (possibly ""); accept null too.
    if raw_instructions is None:
        instructions = None
    else:
        instructions = str(raw_instructions).strip()

    if not item_name or action not in ("inc", "dec", "remove"):
        return jsonify({"status": "error",
                        "message": "item_name and action (inc|dec|remove) required."}), 400
    if not AGENT.session_id:
        return jsonify({"status": "error",
                        "message": "No active session."}), 400

    # Find the exact line (item name + instructions) so + / − on one of
    # two "Chicken Adobo" lines with different notes targets the right one.
    order = _order_snapshot()
    line = None
    if order:
        for ln in order["lines"]:
            if ln["name"] == item_name and (ln["instructions"] or "") == (instructions or ""):
                line = ln
                break
    if line is None:
        return jsonify({"status": "error",
                        "message": f"'{item_name}' is not in your order."}), 400

    if action == "remove":
        result = db.remove_item_from_order(
            AGENT.session_id, item_name,
            instructions=instructions, qty=line["quantity"],
        )
    elif action == "inc":
        new_qty = line["quantity"] + 1
        result = db.change_item_quantity(
            AGENT.session_id, item_name, new_qty,
            instructions=instructions,
        )
    else:  # dec
        new_qty = line["quantity"] - 1
        if new_qty <= 0:
            result = db.remove_item_from_order(
                AGENT.session_id, item_name,
                instructions=instructions, qty=line["quantity"],
            )
        else:
            result = db.change_item_quantity(
                AGENT.session_id, item_name, new_qty,
                instructions=instructions,
            )

    if result.get("status") == "success" and AGENT.state == "STATE_REVIEW":
        AGENT._set_state("STATE_TAKING_ORDER")

    return jsonify({
        "status": result.get("status"),
        "message": result.get("message"),
        "order": _order_snapshot(),
        "state": AGENT.state,
    })


@app.post("/api/cart/clear")
def api_cart_clear():
    if not AGENT.session_id:
        return jsonify({"status": "error",
                        "message": "No active session."}), 400
    result = db.clear_session_cart(AGENT.session_id)
    if result.get("status") == "success" and AGENT.state == "STATE_REVIEW":
        AGENT._set_state("STATE_TAKING_ORDER")
    return jsonify({
        "status": result.get("status"),
        "message": result.get("message"),
        "order": _order_snapshot(),
        "state": AGENT.state,
    })


# ------------------------------------------------------------
# Review & confirm
# ------------------------------------------------------------
@app.post("/api/review")
def api_review():
    if not AGENT.session_id:
        return jsonify({"status": "error",
                        "message": "No active session."}), 400
    result = AGENT.handle_user_message("show my order")
    return jsonify({
        "status": "success",
        "reply": result.get("reply", ""),
        "state": result.get("state"),
        "order": _order_snapshot(),
    })


@app.post("/api/confirm")
def api_confirm():
    data = request.get_json(silent=True) or {}
    yes = bool(data.get("yes", False))
    if not yes:
        return jsonify({"status": "success",
                        "message": "Cancelled.",
                        "state": AGENT.state,
                        "order": _order_snapshot()})
    if not AGENT.session_id:
        return jsonify({"status": "error",
                        "message": "No active session."}), 400
    if AGENT.state != "STATE_REVIEW":
        return jsonify({"status": "error",
                        "message": "Please review your order first.",
                        "state": AGENT.state}), 400
    result = AGENT.handle_user_message("finalize my order")
    return jsonify({
        "status": "success",
        "reply": result.get("reply", ""),
        "state": result.get("state"),
        "order": _order_snapshot(),
    })


# ------------------------------------------------------------
# Reset
# ------------------------------------------------------------
@app.post("/api/reset")
def api_reset():
    global AGENT
    AGENT = LeightonAgent()
    return jsonify({"status": "success", "state": AGENT.state})


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)