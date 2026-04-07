"""
Flask web app — Farfalla | ENSA Béni Mellal
Roles : admin | student
Run   : python app.py  →  http://localhost:9000

Default accounts:
  admin    / admin123
  student1 / student123
"""

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from local_db import LocalDatabase
from edge_assistant import EdgeAssistant

app = Flask(__name__)
app.secret_key = "ensa-edge-ai-2025-secret"

# ── Shared DB instance ────────────────────────────────────────
db = LocalDatabase()

# ── Per-user assistant instances ──────────────────────────────
assistants: dict[str, EdgeAssistant] = {}

def get_assistant(student_id: str) -> EdgeAssistant:
    if student_id not in assistants:
        assistants[student_id] = EdgeAssistant(student_id=student_id)
    return assistants[student_id]


# ── Auth decorators ───────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session["user"]["role"] != "admin":
            return redirect(url_for("chat_page"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    if "user" in session:
        if session["user"]["role"] == "admin":
            return redirect(url_for("admin_page"))
        return redirect(url_for("chat_page"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.verify_user(username, password)
        if user:
            session["user"] = {"username": user["username"],
                               "role": user["role"],
                               "full_name": user["full_name"]}
            if user["role"] == "admin":
                return redirect(url_for("admin_page"))
            return redirect(url_for("chat_page"))
        error = "Identifiant ou mot de passe incorrect."
    return render_template("login.html", error=error)


@app.route("/register", methods=["POST"])
def register():
    first_name = request.form.get("first_name", "").strip()
    last_name  = request.form.get("last_name",  "").strip()
    username   = request.form.get("username",   "").strip()
    password   = request.form.get("password",   "")
    password2  = request.form.get("password2",  "")

    if not all([first_name, last_name, username, password]):
        return render_template("login.html", reg_error="Tous les champs sont obligatoires.")
    if password != password2:
        return render_template("login.html", reg_error="Les mots de passe ne correspondent pas.")
    if len(password) < 6:
        return render_template("login.html", reg_error="Le mot de passe doit contenir au moins 6 caractères.")

    full_name = f"{first_name} {last_name}"
    ok = db.create_user(username, password, role="student", full_name=full_name)
    if not ok:
        return render_template("login.html", reg_error="Cet identifiant est déjà pris.")

    return render_template("login.html", success="Compte créé avec succès ! Connectez-vous.")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════
#  STUDENT — CHAT
# ══════════════════════════════════════════════════════════════
@app.route("/chat")
@login_required
def chat_page():
    return render_template("chat.html", user=session["user"])


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data       = request.json
    user_input = data.get("message", "").strip()
    if not user_input:
        return jsonify({"error": "Message vide"}), 400

    student_id = session["user"]["username"]
    assistant  = get_assistant(student_id)

    import time
    start = time.time()

    stress      = assistant.stress_detector.analyze(user_input)
    edge_result = assistant.edge.process(user_input, student_id)

    if edge_result["source"] in ("edge_cache", "edge_local_degraded", "edge_ollama"):
        response = edge_result["response"]
        source   = edge_result["source"]
        latency  = edge_result["latency_ms"]
    else:
        response, latency = assistant._call_cloud_llm(user_input)
        source = "cloud"
        assistant.edge.cache_response(user_input, response)

    assistant.db.log_interaction(
        student_id, user_input, response,
        stress["level"], source, latency
    )

    total_latency = (time.time() - start) * 1000
    return jsonify({
        "response":        response,
        "support":         stress["message"],
        "stress_level":    stress["level"],
        "source":          source,
        "latency_ms":      round(total_latency, 1),
        "cache_size":      assistant.edge.get_cache_size(),
        "cloud_available": assistant.edge.cloud_available,
        "ollama_available":assistant.edge._ollama_available,
    })


@app.route("/api/toggle-mode", methods=["POST"])
@login_required
def api_toggle_mode():
    student_id = session["user"]["username"]
    assistant  = get_assistant(student_id)
    if assistant.edge.cloud_available:
        assistant.edge.simulate_cloud_outage()
    else:
        assistant.edge.restore_cloud()
    return jsonify({"cloud_available": assistant.edge.cloud_available})


@app.route("/api/stats")
@login_required
def api_stats():
    student_id = session["user"]["username"]
    assistant  = get_assistant(student_id)
    s = db.get_stats(student_id=student_id)
    return jsonify({**s,
                    "cache_size":      assistant.edge.get_cache_size(),
                    "cloud_available": assistant.edge.cloud_available,
                    "ollama_available":assistant.edge._ollama_available})


@app.route("/api/history")
@login_required
def api_history():
    student_id = session["user"]["username"]
    rows = db.get_student_history(student_id, limit=10)
    return jsonify([
        {"query": r[0], "response": r[1], "stress": r[2],
         "source": r[3], "latency": r[4], "timestamp": r[5]}
        for r in rows
    ])


# ══════════════════════════════════════════════════════════════
#  STUDENT — PLANNING
# ══════════════════════════════════════════════════════════════
@app.route("/api/planning/generate", methods=["POST"])
@login_required
def api_planning_generate():
    import time, openai, os
    data         = request.json
    courses      = data.get("courses", [])      # [{"name":"Maths","level":"difficile","hours":3}, ...]
    exams        = data.get("exams", [])         # [{"name":"Maths","date":"2026-04-20"}, ...]
    hours_per_day= int(data.get("hours_per_day", 4))
    student_id   = session["user"]["username"]

    if not courses:
        return jsonify({"error": "Ajoutez au moins une matière."}), 400

    # Build prompt
    courses_txt = "\n".join(f"- {c['name']} (niveau: {c.get('level','moyen')}, {c.get('hours',2)}h/semaine souhaitées)" for c in courses)
    exams_txt   = "\n".join(f"- {e['name']} le {e['date']}" for e in exams) if exams else "Aucun examen spécifié."
    prompt = f"""Tu es Farfalla, un assistant pédagogique expert en planification d'études.

Un étudiant de l'ENSA Béni Mellal a les matières suivantes :
{courses_txt}

Examens à venir :
{exams_txt}

Disponibilité : {hours_per_day} heures d'étude par jour.

Génère un planning de révision détaillé pour les 7 prochains jours (lundi à dimanche).
Pour chaque jour, indique :
- Les matières à étudier avec le nombre d'heures
- Les objectifs concrets de la session
- Un conseil de méthode de travail

Tiens compte des niveaux de difficulté pour prioriser. Commence par les matières difficiles. Inclus des pauses.
Réponds en français, de façon claire et structurée."""

    start = time.time()
    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        plan = completion.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"Erreur API : {str(e)}"}), 500

    latency = round((time.time() - start) * 1000, 1)
    db.save_planning(student_id, courses, exams, hours_per_day, plan)

    return jsonify({"plan": plan, "latency_ms": latency})


@app.route("/api/planning/saved")
@login_required
def api_planning_saved():
    student_id = session["user"]["username"]
    p = db.get_latest_planning(student_id)
    return jsonify(p or {})


# ══════════════════════════════════════════════════════════════
#  STUDENT — RÉSUMÉ DE COURS
# ══════════════════════════════════════════════════════════════
@app.route("/api/resume", methods=["POST"])
@login_required
def api_resume():
    import time, openai, os
    data    = request.json
    content = data.get("content", "").strip()
    style   = data.get("style", "standard")   # standard | bullet | fiche

    if not content:
        return jsonify({"error": "Collez le contenu du cours à résumer."}), 400

    style_instructions = {
        "standard": "Rédige un résumé clair en paragraphes (300-400 mots).",
        "bullet":   "Rédige un résumé sous forme de points clés (bullet points), organisés par thème.",
        "fiche":    "Crée une fiche de révision structurée avec : Définitions clés, Concepts principaux, Formules/Méthodes, Points à retenir.",
    }

    prompt = f"""Tu es Farfalla, un assistant pédagogique pour étudiants de l'ENSA Béni Mellal.

{style_instructions.get(style, style_instructions['standard'])}

Voici le contenu du cours à traiter :
---
{content[:3000]}
---

Réponds en français."""

    start = time.time()
    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        result = completion.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"Erreur API : {str(e)}"}), 500

    latency = round((time.time() - start) * 1000, 1)
    return jsonify({"resume": result, "latency_ms": latency})


# ══════════════════════════════════════════════════════════════
#  ADMIN — DASHBOARD
# ══════════════════════════════════════════════════════════════
@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html", user=session["user"])


@app.route("/api/admin/stats")
@admin_required
def api_admin_stats():
    s = db.get_stats()
    users = db.get_all_users()
    return jsonify({**s, "total_users": len(users)})


@app.route("/api/admin/users")
@admin_required
def api_admin_users():
    return jsonify(db.get_all_users())


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def api_admin_create_user():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role     = data.get("role", "student")
    fullname = data.get("full_name", "").strip()
    if not username or not password:
        return jsonify({"error": "Champs obligatoires manquants"}), 400
    if role not in ("student", "admin"):
        return jsonify({"error": "Rôle invalide"}), 400
    ok = db.create_user(username, password, role, fullname)
    if ok:
        return jsonify({"success": True})
    return jsonify({"error": "Nom d'utilisateur déjà pris"}), 409


@app.route("/api/admin/users/<username>", methods=["DELETE"])
@admin_required
def api_admin_delete_user(username):
    if username == session["user"]["username"]:
        return jsonify({"error": "Impossible de supprimer votre propre compte"}), 400
    ok = db.delete_user(username)
    if ok:
        return jsonify({"success": True})
    return jsonify({"error": "Utilisateur introuvable ou protégé"}), 404


@app.route("/api/admin/interactions")
@admin_required
def api_admin_interactions():
    return jsonify(db.get_all_interactions(limit=50))


@app.route("/api/admin/alerts")
@admin_required
def api_admin_alerts():
    return jsonify(db.get_stress_alerts(limit=20))


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Farfalla — ENSA Béni Mellal")
    print("  Ouvrez votre navigateur : http://localhost:9000")
    print("  Admin    : admin    / admin123")
    print("  Étudiant : student1 / student123")
    print("="*55 + "\n")
    app.run(debug=False, port=9000)
