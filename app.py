from flask import Flask, render_template, request, redirect, session, jsonify
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

from config import Config
from models import db, Session, Message, UsageLog
from prompts import build_system_prompt

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

db.init_app(app)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Pricing constants — source: https://ai.google.dev/gemini-api/docs/pricing (checked July 31, 2026)
INPUT_RATE_PER_MILLION = 0.30
OUTPUT_RATE_PER_MILLION = 2.50


@app.route("/")
def home():
    return render_template("onboarding.html")


@app.route("/start", methods=["POST"])
def start():
    name = request.form["name"]
    level = request.form["level"]
    topic = request.form["topic"]
    goal = request.form["goal"]

    onboarding = {"level": level, "topic": topic, "goal": goal}

    new_session = Session(
        user_name=name,
        onboarding_data=json.dumps(onboarding)
    )
    db.session.add(new_session)
    db.session.commit()

    session["session_id"] = new_session.id
    return redirect("/chat")


@app.route("/chat", methods=["GET"])
def chat_page():
    return render_template("chat.html")


@app.route("/chat", methods=["POST"])
def chat_api():
    session_id = session.get("session_id")
    if not session_id:
        return jsonify({"error": "No active session. Please start from the onboarding page."}), 400

    db_session = Session.query.get(session_id)
    if not db_session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json()
    user_text = data["message"]

    # 1. Save the user's message to the database FIRST
    user_msg = Message(session_id=session_id, role="user", content=user_text)
    db.session.add(user_msg)
    db.session.commit()

    # 2. Pull the FULL conversation history for this session from the DB
    all_messages = Message.query.filter_by(session_id=session_id) \
                                  .order_by(Message.created_at.asc()).all()

    # 3. Build the "contents" list Gemini expects, from every past message
    contents = []
    for m in all_messages:
        gemini_role = "model" if m.role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": m.content}]})

    # 4. Build the dynamic, hardened system prompt from onboarding data
    onboarding = json.loads(db_session.onboarding_data)
    system_prompt = build_system_prompt(
        user_name=db_session.user_name,
        level=onboarding["level"],
        topic=onboarding["topic"],
        goal=onboarding["goal"],
    )

    # 5. Call Gemini with FULL history + system instruction
    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )

    reply_text = response.text

    # 6. Save the assistant's reply to the database
    assistant_msg = Message(session_id=session_id, role="assistant", content=reply_text)
    db.session.add(assistant_msg)
    db.session.commit()

    # 7. Extract real usage_metadata and compute cost
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    total_tokens = usage.total_token_count or 0

    cost = (input_tokens / 1_000_000 * INPUT_RATE_PER_MILLION) + \
           (output_tokens / 1_000_000 * OUTPUT_RATE_PER_MILLION)

    # 8. Log it to UsageLogs — one row per API call
    usage_log = UsageLog(
        session_id=session_id,
        message_id=assistant_msg.id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        model_name=Config.GEMINI_MODEL,
    )
    db.session.add(usage_log)
    db.session.commit()

    return jsonify({"reply": reply_text})


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/usage")
def api_usage():
    logs = UsageLog.query.order_by(UsageLog.created_at.desc()).all()

    total_requests = len(logs)
    total_input_tokens = sum(l.input_tokens for l in logs)
    total_output_tokens = sum(l.output_tokens for l in logs)
    total_cost = sum(l.estimated_cost_usd for l in logs)

    session_totals = {}
    for l in logs:
        sid = l.session_id
        if sid not in session_totals:
            sess = Session.query.get(sid)
            session_totals[sid] = {
                "session_id": sid,
                "user_name": sess.user_name if sess else "Unknown",
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost": 0.0,
            }
        session_totals[sid]["requests"] += 1
        session_totals[sid]["input_tokens"] += l.input_tokens
        session_totals[sid]["output_tokens"] += l.output_tokens
        session_totals[sid]["total_cost"] += l.estimated_cost_usd

    recent = [
        {
            "id": l.id,
            "session_id": l.session_id,
            "model_name": l.model_name,
            "input_tokens": l.input_tokens,
            "output_tokens": l.output_tokens,
            "total_tokens": l.total_tokens,
            "estimated_cost_usd": round(l.estimated_cost_usd, 6),
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for l in logs[:50]
    ]

    return jsonify({
        "total_requests": total_requests,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "total_cost_usd": round(total_cost, 6),
        "sessions": list(session_totals.values()),
        "recent_requests": recent,
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)