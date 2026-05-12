# app.py - Gestión de Partidos de Pádel (versión completa)
# pip install streamlit pandas openpyxl plotly

import streamlit as st
import pandas as pd
import json, os, hashlib, io
from datetime import datetime
from itertools import combinations
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────
# PERSISTENCIA
# ─────────────────────────────────────────────

DB_DIR = "padel_db"
os.makedirs(DB_DIR, exist_ok=True)

FILES = {
    "users":   os.path.join(DB_DIR, "users.json"),
    "courts":  os.path.join(DB_DIR, "courts.json"),
    "slots":   os.path.join(DB_DIR, "slots.json"),
    "matches": os.path.join(DB_DIR, "matches.json"),
    "history": os.path.join(DB_DIR, "history.json"),  # histórico de puntos
}

def load(key):
    if os.path.exists(FILES[key]):
        with open(FILES[key], "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save(key, data):
    with open(FILES[key], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

# ─────────────────────────────────────────────
# PUNTUACIÓN
# ─────────────────────────────────────────────

def calc_points(games_won, sets_won, match_won):
    return round(games_won * 0.1 + sets_won * 0.2 + (2.0 if match_won else 0), 2)

def parse_sets(sets_str):
    sw = sl = gw = gl = 0
    for s in sets_str.strip().split(","):
        s = s.strip()
        if "-" not in s:
            raise ValueError(f"Formato incorrecto: '{s}'")
        a, b = s.split("-")
        a, b = int(a.strip()), int(b.strip())
        gw += a; gl += b
        if a > b: sw += 1
        else:     sl += 1
    if sw + sl > 3:
        raise ValueError("Máximo 3 sets por partido")
    return sw, sl, gw, gl

def record_history(username, points_total, event):
    """Guarda snapshot del estado de puntos tras cada partido."""
    history = load("history")
    history.append({
        "username": username,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "points": points_total,
        "event": event,
    })
    save("history", history)

# ─────────────────────────────────────────────
# INIT ADMIN
# ─────────────────────────────────────────────

def init_admin():
    users = load("users")
    if not any(u["role"] == "admin" for u in users):
        users.append({
            "id": "admin", "username": "admin",
            "email": "admin@padel.com", "phone": "000000000",
            "password": hp("admin123"), "role": "admin",
            "wins": 0, "losses": 0, "points": 0.0,
        })
        save("users", users)

init_admin()

# ─────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────

if "user" not in st.session_state: st.session_state.user = None
if "page" not in st.session_state: st.session_state.page = "login"

def go(page): st.session_state.page = page

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #f0f4f8; font-family: 'Segoe UI', sans-serif;
}
.block-container { max-width: 520px !important; margin: auto;
                   padding: 1rem 1rem 4rem 1rem; }
.app-title { text-align: center; font-size: 1.8rem; font-weight: 800;
             color: #1a73e8; margin-bottom: 0.2rem; }
.app-sub { text-align: center; color: #666; font-size: 0.9rem; margin-bottom: 1.4rem; }
.card { background: white; border-radius: 16px; padding: 1rem 1.2rem;
        margin-bottom: 0.8rem; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.card-title { font-weight: 700; font-size: 1rem; color: #1a1a2e; margin-bottom: 0.3rem; }
.card-sub   { font-size: 0.82rem; color: #555; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
         font-size: 0.75rem; font-weight: 600; }
.badge-blue  { background:#e8f0fe; color:#1a73e8; }
.badge-green { background:#e6f4ea; color:#1e8e3e; }
.badge-orange{ background:#fef3e2; color:#e37400; }
.badge-red   { background:#fce8e6; color:#c5221f; }
div.stButton > button { width: 100%; border-radius: 12px; height: 3rem;
                        font-size: 0.95rem; font-weight: 600; border: none; }
.section-label { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
                 text-transform: uppercase; color: #999; margin: 1rem 0 0.4rem 0; }
label { font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────

def card(title, body="", badge=None, badge_type="blue"):
    bh = f'<span class="badge badge-{badge_type}">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="card"><div class="card-title">{title} {bh}</div>'
        f'<div class="card-sub">{body}</div></div>', unsafe_allow_html=True)

def section(label):
    st.markdown(f'<div class="section-label">{label}</div>', unsafe_allow_html=True)

def page_header(icon, title, back=True):
    st.markdown(f'<div class="app-title">{icon} {title}</div>', unsafe_allow_html=True)
    if back and st.button("← Volver al menú", key=f"back_{title}"):
        go("home"); st.rerun()
    st.write("")

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def page_login():
    st.markdown('<div class="app-title">🏓 Pádel Manager</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-sub">Gestión de partidos por parejas</div>',
                unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Usuario o Email")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        users = load("users")
        m = next((x for x in users
                  if (x["username"] == u or x["email"] == u)
                  and x["password"] == hp(p)), None)
        if m:
            st.session_state.user = m
            go("home"); st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

# ─────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────

def page_home():
    u = st.session_state.user
    st.markdown('<div class="app-title">🏓 Pádel Manager</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-sub">Hola, <b>{u["username"]}</b> '
                f'{"👑 Admin" if u["role"]=="admin" else "🎾 Jugador"}</div>',
                unsafe_allow_html=True)

    section("Partidos")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Partido\nManual"): go("create_match"); st.rerun()
    with c2:
        if st.button("🤖 Partido\nAutomático"): go("auto_match"); st.rerun()
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📋 Ver\nResultados"): go("results"); st.rerun()
    with c4:
        if st.button("✏️ Introducir\nResultado"): go("enter_result"); st.rerun()

    section("Estadísticas")
    c5, c6 = st.columns(2)
    with c5:
        if st.button("📊 Métricas\npor partido"): go("metrics"); st.rerun()
    with c6:
        if st.button("📈 Histórico\nde posición"): go("history"); st.rerun()

    if u["role"] == "admin":
        section("Administración")
        if st.button("👥 Gestionar Usuarios"): go("manage_users"); st.rerun()
        if st.button("🏟️ Gestionar Pistas"):   go("manage_courts"); st.rerun()
        if st.button("🕐 Gestionar Horarios"): go("manage_slots"); st.rerun()
        if st.button("📤 Importar / Exportar Excel"): go("io_excel"); st.rerun()

    section("")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        go("login"); st.rerun()

# ─────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────

def page_manage_users():
    page_header("👥", "Usuarios")
    section("Crear nuevo usuario")
    with st.form("new_user"):
        username = st.text_input("Nombre de usuario")
        email    = st.text_input("Email")
        phone    = st.text_input("Teléfono")
        password = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Crear Usuario")
    if ok:
        if not all([username, email, phone, password]):
            st.error("Completa todos los campos.")
        else:
            users = load("users")
            if any(u["username"] == username or u["email"] == email for u in users):
                st.error("El usuario o email ya existe.")
            else:
                uid = username.lower().replace(" ", "_")
                users.append({
                    "id": uid, "username": username, "email": email,
                    "phone": phone, "password": hp(password), "role": "player",
                    "wins": 0, "losses": 0, "points": 0.0,
                })
                save("users", users)
                record_history(username, 0.0, "alta")
                st.success(f"✅ Usuario '{username}' creado."); st.rerun()

    section("Usuarios registrados")
    users = sorted(
        [u for u in load("users") if u["role"] == "player"],
        key=lambda u: u.get("points", 0), reverse=True
    )
    if not users:
        st.info("No hay jugadores registrados aún.")
    for i, u in enumerate(users, 1):
        card(f"#{i} · 🧑 {u['username']}",
             f"📧 {u['email']} · 📱 {u['phone']}<br>"
             f"⭐ <b>{u.get('points',0)} pts</b> · "
             f"🏆 {u.get('wins',0)}V / {u.get('losses',0)}D")

# ─────────────────────────────────────────────
# PISTAS
# ─────────────────────────────────────────────

def page_manage_courts():
    page_header("🏟️", "Pistas")
    section("Añadir pista")
    with st.form("new_court"):
        name = st.text_input("Nombre de la pista")
        loc  = st.text_input("Dirección / Ubicación")
        ok   = st.form_submit_button("Añadir")
    if ok:
        if not name or not loc:
            st.error("Completa nombre y ubicación.")
        else:
            courts = load("courts")
            courts.append({"id": f"court_{len(courts)+1}", "name": name, "location": loc})
            save("courts", courts)
            st.success("✅ Pista añadida."); st.rerun()
    section("Pistas disponibles")
    for c in load("courts"):
        card(f"🏟️ {c['name']}", c["location"])

# ─────────────────────────────────────────────
# HORARIOS
# ─────────────────────────────────────────────

def page_manage_slots():
    page_header("🕐", "Horarios")
    courts = load("courts")
    if not courts:
        st.warning("Primero debes crear al menos una pista."); return
    section("Añadir horario")
    with st.form("new_slot"):
        date  = st.date_input("Fecha")
        time  = st.time_input("Hora")
        court = st.selectbox("Pista", [c["name"] for c in courts])
        ok    = st.form_submit_button("Añadir Horario")
    if ok:
        slots = load("slots")
        slots.append({
            "id": f"slot_{len(slots)+1}",
            "date": str(date), "time": str(time)[:5],
            "court": court, "booked": False,
        })
        save("slots", slots)
        st.success("✅ Horario añadido."); st.rerun()
    section("Horarios")
    for s in load("slots"):
        estado = "🔒 Ocupado" if s.get("booked") else "✅ Libre"
        bt = "red" if s.get("booked") else "green"
        card(f"📅 {s['date']} {s['time']} — {s['court']}", badge=estado, badge_type=bt)

# ─────────────────────────────────────────────
# PARTIDO MANUAL
# ─────────────────────────────────────────────

def page_create_match():
    page_header("➕", "Partido Manual")
    users = [u for u in load("users") if u["role"] == "player"]
    slots = [s for s in load("slots") if not s.get("booked")]
    if len(users) < 4:
        st.warning("Necesitas al menos 4 jugadores."); return
    if not slots:
        st.warning("No hay horarios libres."); return

    names = [u["username"] for u in users]
    slot_labels = [f"{s['date']} {s['time']} — {s['court']}" for s in slots]

    section("Pareja 1")
    p1a = st.selectbox("Jugador 1A", names, key="p1a")
    p1b = st.selectbox("Jugador 1B", names, key="p1b")
    section("Pareja 2")
    p2a = st.selectbox("Jugador 2A", names, key="p2a")
    p2b = st.selectbox("Jugador 2B", names, key="p2b")
    section("Horario")
    slot_sel = st.selectbox("Horario", slot_labels)

    if st.button("✅ Crear Partido"):
        if len({p1a, p1b, p2a, p2b}) < 4:
            st.error("Los 4 jugadores deben ser distintos."); return
        slot_obj = next(s for s in slots
                        if f"{s['date']} {s['time']} — {s['court']}" == slot_sel)
        matches = load("matches")
        matches.append({
            "id": f"match_{len(matches)+1}",
            "pair1": [p1a, p1b], "pair2": [p2a, p2b],
            "pair1_name": f"{p1a} / {p1b}",
            "pair2_name": f"{p2a} / {p2b}",
            "date": slot_obj["date"], "time": slot_obj["time"],
            "court": slot_obj["court"],
            "result": None, "winner": None,
            "created_by": st.session_state.user["username"],
        })
        save("matches", matches)
        all_slots = load("slots")
        for s in all_slots:
            if s["id"] == slot_obj["id"]: s["booked"] = True
        save("slots", all_slots)
        st.success(f"✅ Partido creado: {p1a}/{p1b} vs {p2a}/{p2b}")
        st.balloons()

# ─────────────────────────────────────────────
# PARTIDO AUTOMÁTICO con selección de disponibles
# ─────────────────────────────────────────────

def best_balanced_pairing(players):
    """
    Dados 4 jugadores con 'points', encuentra el emparejamiento
    cuya diferencia de suma de puntos entre las dos parejas sea mínima.
    """
    p = players
    options = [
        ((p[0], p[1]), (p[2], p[3])),
        ((p[0], p[2]), (p[1], p[3])),
        ((p[0], p[3]), (p[1], p[2])),
    ]
    best = None
    best_diff = float("inf")
    for (a, b), (c, d) in options:
        diff = abs((a["points"] + b["points"]) - (c["points"] + d["points"]))
        if diff < best_diff:
            best_diff = diff
            best = ((a, b), (c, d), diff)
    return best

def group_players_for_matches(available):
    """
    Ordena por puntos y agrupa de 4 en 4 (los más próximos juegan entre sí).
    Devuelve lista de grupos de 4 jugadores. Si sobran <4, los ignora.
    """
    sorted_p = sorted(available, key=lambda u: u.get("points", 0), reverse=True)
    return [sorted_p[i:i+4] for i in range(0, len(sorted_p) - 3, 4)]

def page_auto_match():
    page_header("🤖", "Partido Automático")

    st.markdown("""
    <div class="card">
    <div class="card-title">¿Cómo funciona?</div>
    <div class="card-sub">
    1. Selecciona qué jugadores están <b>disponibles</b> hoy.<br>
    2. El sistema los agrupa de 4 en 4 según su puntuación.<br>
    3. Dentro de cada grupo, forma las 2 parejas más equilibradas (mínima diferencia de puntos).<br>
    4. Los partidos quedan listos para introducir resultado.
    </div></div>
    """, unsafe_allow_html=True)

    users = [u for u in load("users") if u["role"] == "player"]
    slots = [s for s in load("slots") if not s.get("booked")]

    if len(users) < 4:
        st.warning("Necesitas al menos 4 jugadores."); return
    if not slots:
        st.warning("No hay horarios libres."); return

    section("Jugadores disponibles")
    available_names = []
    for u in sorted(users, key=lambda u: u.get("points", 0), reverse=True):
        if st.checkbox(
            f"{u['username']} ({u.get('points',0)} pts)",
            key=f"avail_{u['username']}",
        ):
            available_names.append(u["username"])

    n = len(available_names)
    if n < 4:
        st.info(f"Selecciona al menos 4 jugadores ({n} marcados).")
        return

    n_matches = n // 4
    extras = n % 4
    st.success(f"✅ {n} jugadores → se crearán **{n_matches} partido(s)**" +
               (f" · {extras} jugador(es) descansan" if extras else ""))

    # Vista previa
    available = [u for u in users if u["username"] in available_names]
    groups = group_players_for_matches(available)

    section("Emparejamiento propuesto")
    pairings_preview = []
    for idx, grp in enumerate(groups, 1):
        (a, b), (c, d), diff = best_balanced_pairing(grp)
        pairings_preview.append(((a, b), (c, d), diff))
        col1, col2 = st.columns(2)
        with col1:
            card(f"Partido {idx} · Pareja 1",
                 f"🎾 {a['username']} ({a['points']} pts)<br>"
                 f"🎾 {b['username']} ({b['points']} pts)<br>"
                 f"Σ = {round(a['points']+b['points'],2)} pts",
                 badge_type="blue")
        with col2:
            card(f"Partido {idx} · Pareja 2",
                 f"🎾 {c['username']} ({c['points']} pts)<br>"
                 f"🎾 {d['username']} ({d['points']} pts)<br>"
                 f"Σ = {round(c['points']+d['points'],2)} pts",
                 badge_type="orange")
        st.caption(f"⚖️ Diferencia de nivel: {round(diff,2)} pts")

    section("Asignación de horarios")
    if len(slots) < n_matches:
        st.error(f"No hay suficientes horarios libres ({len(slots)} disponibles, "
                 f"{n_matches} necesarios)."); return

    slot_labels = [f"{s['date']} {s['time']} — {s['court']}" for s in slots]
    chosen_slots = []
    for i in range(n_matches):
        sel = st.selectbox(f"Horario partido {i+1}", slot_labels,
                           index=i, key=f"auto_slot_{i}")
        chosen_slots.append(sel)

    if len(set(chosen_slots)) != len(chosen_slots):
        st.warning("Cada partido debe tener un horario distinto.")
        return

    if st.button("🤖 Generar todos los partidos"):
        matches = load("matches")
        all_slots = load("slots")
        for idx, ((a, b), (c, d), diff) in enumerate(pairings_preview):
            slot_obj = next(s for s in slots
                            if f"{s['date']} {s['time']} — {s['court']}" == chosen_slots[idx])
            matches.append({
                "id": f"match_{len(matches)+1}",
                "pair1": [a["username"], b["username"]],
                "pair2": [c["username"], d["username"]],
                "pair1_name": f"{a['username']} / {b['username']}",
                "pair2_name": f"{c['username']} / {d['username']}",
                "date": slot_obj["date"], "time": slot_obj["time"],
                "court": slot_obj["court"],
                "result": None, "winner": None,
                "created_by": "AUTO",
                "balance_diff": round(diff, 2),
            })
            for s in all_slots:
                if s["id"] == slot_obj["id"]: s["booked"] = True
        save("matches", matches)
        save("slots", all_slots)
        st.success(f"✅ {n_matches} partido(s) creado(s). Ve a **Introducir Resultado**.")
        st.balloons()

# ─────────────────────────────────────────────
# INTRODUCIR RESULTADO
# ─────────────────────────────────────────────

def page_enter_result():
    page_header("✏️", "Introducir Resultado")
    pending = [m for m in load("matches") if not m.get("result")]
    if not pending:
        st.info("No hay partidos pendientes."); return

    labels = [f"{m['pair1_name']} vs {m['pair2_name']} ({m['date']} {m['time']})"
              for m in pending]
    sel = st.selectbox("Partido", labels)
    match = pending[labels.index(sel)]

    st.markdown(f"""
    <div class="card">
    <div class="card-title">🆚 {match['pair1_name']}</div>
    <div class="card-sub">contra</div>
    <div class="card-title">{match['pair2_name']}</div>
    <div class="card-sub">📅 {match['date']} {match['time']} · 🏟️ {match['court']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.caption("Formato: sets separados por comas. Ej: `6-4,4-6,7-5`")
    s1 = st.text_input(f"Sets de {match['pair1_name']}", placeholder="6-4,4-6,7-5")
    s2 = st.text_input(f"Sets de {match['pair2_name']}", placeholder="4-6,6-4,5-7")

    if st.button("💾 Guardar Resultado"):
        try:
            sw1, sl1, gw1, gl1 = parse_sets(s1)
            sw2, sl2, gw2, gl2 = parse_sets(s2)
            if sw1 != sl2 or sw2 != sl1:
                st.error("Los sets ganados de una pareja deben ser los perdidos de la otra."); return
            if gw1 != gl2 or gw2 != gl1:
                st.error("Los juegos no cuadran entre ambas parejas."); return

            winner_pair = "pair1" if sw1 > sw2 else "pair2"
            loser_pair  = "pair2" if winner_pair == "pair1" else "pair1"
            winner_name = match[f"{winner_pair}_name"]
            loser_name  = match[f"{loser_pair}_name"]

            pts_winner = calc_points(
                gw1 if winner_pair == "pair1" else gw2,
                sw1 if winner_pair == "pair1" else sw2, True)
            pts_loser = calc_points(
                gw1 if loser_pair == "pair1" else gw2,
                sw1 if loser_pair == "pair1" else sw2, False)

            # Update matches
            all_matches = load("matches")
            for m in all_matches:
                if m["id"] == match["id"]:
                    m["result"]    = f"{match['pair1_name']}: {s1}  |  {match['pair2_name']}: {s2}"
                    m["winner"]    = winner_name
                    m["pts_pair1"] = pts_winner if winner_pair == "pair1" else pts_loser
                    m["pts_pair2"] = pts_winner if winner_pair == "pair2" else pts_loser
                    m["sets_pair1"] = sw1; m["sets_pair2"] = sw2
                    m["games_pair1"] = gw1; m["games_pair2"] = gw2
                    m["completed_at"] = datetime.now().isoformat(timespec="seconds")
                    break
            save("matches", all_matches)

            # Update users + history
            users = load("users")
            for u in users:
                if u["username"] in match[winner_pair]:
                    u["wins"]   = u.get("wins", 0) + 1
                    u["points"] = round(u.get("points", 0) + pts_winner, 2)
                    record_history(u["username"], u["points"],
                                   f"victoria vs {loser_name} (+{pts_winner})")
                elif u["username"] in match[loser_pair]:
                    u["losses"] = u.get("losses", 0) + 1
                    u["points"] = round(u.get("points", 0) + pts_loser, 2)
                    record_history(u["username"], u["points"],
                                   f"derrota vs {winner_name} (+{pts_loser})")
            save("users", users)

            st.success(f"✅ Ganador: **{winner_name}** (+{pts_winner} pts c/u)")
            st.info(f"🥈 {loser_name} suma +{pts_loser} pts c/u")
            st.balloons()
        except ValueError as e:
            st.error(f"Error de formato: {e}")

# ─────────────────────────────────────────────
# RESULTADOS Y RANKING
# ─────────────────────────────────────────────

def page_results():
    page_header("📋", "Resultados & Ranking")
    section("🏆 Ranking de Jugadores")
    users = sorted([u for u in load("users") if u["role"] == "player"],
                   key=lambda u: u.get("points", 0), reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users):
        total = u.get("wins", 0) + u.get("losses", 0)
        pct   = f"{int(u['wins']/total*100)}%" if total else "–"
        medal = medals[i] if i < 3 else f"{i+1}."
        card(f"{medal} {u['username']}",
             f"⭐ <b>{u.get('points',0)} pts</b> · "
             f"✅ {u.get('wins',0)}V / ❌ {u.get('losses',0)}D · {pct}")

    with st.expander("ℹ️ Sistema de puntuación"):
        st.markdown("""
        | Hito | Puntos |
        |---|---|
        | Juego ganado | +0.1 |
        | Set ganado   | +0.2 |
        | Ganar partido| +2.0 |
        """)

    section("📅 Historial de Partidos")
    for m in reversed(load("matches")):
        if m.get("result"):
            winner = m.get("winner", "–")
            pts = m.get("pts_pair1") if m["pair1_name"] == winner else m.get("pts_pair2")
            card(f"🏆 {m['pair1_name']} vs {m['pair2_name']}",
                 f"📅 {m['date']} {m['time']} · 🏟️ {m['court']}<br>"
                 f"Sets: {m.get('sets_pair1','?')}-{m.get('sets_pair2','?')}<br>"
                 f"🥇 <b>{winner}</b> (+{pts} pts)",
                 badge="Jugado", badge_type="green")
        else:
            card(f"⏳ {m['pair1_name']} vs {m['pair2_name']}",
                 f"📅 {m['date']} {m['time']} · 🏟️ {m['court']}",
                 badge="Pendiente", badge_type="orange")

# ─────────────────────────────────────────────
# IMPORT / EXPORT EXCEL
# ─────────────────────────────────────────────

def build_excel():
    users   = load("users")
    matches = load("matches")
    df_u = pd.DataFrame(users)
    df_m = pd.DataFrame(matches)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_u.to_excel(w, sheet_name="usuarios", index=False)
        df_m.to_excel(w, sheet_name="partidos", index=False)
    buf.seek(0)
    return buf

def page_io_excel():
    page_header("📤", "Importar / Exportar")

    section("Exportar a Excel")
    st.markdown("Descarga un archivo con todos los usuarios y partidos.")
    if st.button("⬇️ Generar Excel"):
        buf = build_excel()
        st.download_button(
            "📥 Descargar padel_export.xlsx", data=buf,
            file_name=f"padel_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    section("Importar desde Excel")
    st.markdown("Sube un Excel con hojas `usuarios` y/o `partidos`.")
    file = st.file_uploader("Archivo .xlsx", type=["xlsx"])
    overwrite = st.checkbox("Sobrescribir datos actuales (si no, se fusiona)")

    if file and st.button("📤 Importar"):
        try:
            xl = pd.ExcelFile(file)
            imported = []

            if "usuarios" in xl.sheet_names:
                df_u = xl.parse("usuarios").fillna("")
                new_users = df_u.to_dict(orient="records")
                # Normalizar tipos
                for u in new_users:
                    u["wins"]   = int(u.get("wins", 0) or 0)
                    u["losses"] = int(u.get("losses", 0) or 0)
                    u["points"] = float(u.get("points", 0) or 0)
                if overwrite:
                    save("users", new_users)
                else:
                    existing = load("users")
                    ex_names = {u["username"] for u in existing}
                    for u in new_users:
                        if u["username"] not in ex_names:
                            existing.append(u)
                    save("users", existing)
                imported.append(f"{len(new_users)} usuarios")

            if "partidos" in xl.sheet_names:
                df_m = xl.parse("partidos").fillna("")
                new_m = df_m.to_dict(orient="records")
                if overwrite:
                    save("matches", new_m)
                else:
                    existing = load("matches")
                    ex_ids = {m["id"] for m in existing}
                    for m in new_m:
                        if m.get("id") not in ex_ids:
                            existing.append(m)
                    save("matches", existing)
                imported.append(f"{len(new_m)} partidos")

            st.success("✅ Importado: " + ", ".join(imported))
            st.rerun()
        except Exception as e:
            st.error(f"Error al importar: {e}")

# ─────────────────────────────────────────────
# MÉTRICAS POR PARTIDO
# ─────────────────────────────────────────────

def page_metrics():
    page_header("📊", "Métricas por Partido")

    played = [m for m in load("matches") if m.get("result")]
    if not played:
        st.info("Aún no hay partidos finalizados."); return

    # KPIs globales
    total = len(played)
    total_sets  = sum((m.get("sets_pair1",0)+m.get("sets_pair2",0)) for m in played)
    total_games = sum((m.get("games_pair1",0)+m.get("games_pair2",0)) for m in played)
    avg_diff = round(sum(m.get("balance_diff", 0) for m in played) / total, 2)

    section("Resumen global")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎾 Partidos", total)
    c2.metric("📦 Sets", total_sets)
    c3.metric("🎯 Juegos", total_games)
    st.metric("⚖️ Equilibrio medio (auto)", f"{avg_diff} pts")

    # Selector de partido
    section("Detalle por partido")
    labels = [f"{m['pair1_name']} vs {m['pair2_name']} ({m['date']})" for m in played]
    sel = st.selectbox("Selecciona partido", labels)
    m   = played[labels.index(sel)]

    sets1, sets2   = m.get("sets_pair1", 0),  m.get("sets_pair2", 0)
    games1, games2 = m.get("games_pair1", 0), m.get("games_pair2", 0)
    pts1, pts2     = m.get("pts_pair1", 0),   m.get("pts_pair2", 0)

    # Gráfico comparativo
    df = pd.DataFrame({
        "Pareja":  [m["pair1_name"], m["pair2_name"]],
        "Sets":    [sets1, sets2],
        "Juegos":  [games1, games2],
        "Puntos":  [pts1, pts2],
    })
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Sets",   x=df["Pareja"], y=df["Sets"],   marker_color="#1a73e8"))
    fig.add_trace(go.Bar(name="Juegos", x=df["Pareja"], y=df["Juegos"], marker_color="#34a853"))
    fig.add_trace(go.Bar(name="Puntos", x=df["Pareja"], y=df["Puntos"], marker_color="#fbbc04"))
    fig.update_layout(
        barmode="group",
        title=f"Comparativa · {m['date']} {m['time']}",
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tarjeta resumen del partido
    winner = m.get("winner", "–")
    card(
        f"🏆 Ganador: {winner}",
        f"📅 {m['date']} {m['time']} · 🏟️ {m['court']}<br>"
        f"Sets: <b>{sets1} - {sets2}</b><br>"
        f"Juegos: <b>{games1} - {games2}</b><br>"
        f"Puntos otorgados: {pts1} / {pts2}<br>"
        f"⚖️ Equilibrio inicial: {m.get('balance_diff', '–')} pts",
        badge="Finalizado", badge_type="green"
    )

    # Distribución de victorias por jugador
    section("Top jugadores (victorias)")
    users = [u for u in load("users") if u["role"] == "player"]
    df_top = pd.DataFrame([
        {"Jugador": u["username"], "Victorias": u.get("wins", 0),
         "Derrotas": u.get("losses", 0), "Puntos": u.get("points", 0)}
        for u in users
    ]).sort_values("Puntos", ascending=False).head(10)

    if not df_top.empty:
        fig2 = px.bar(df_top, x="Jugador", y=["Victorias", "Derrotas"],
                      barmode="stack", color_discrete_map={
                          "Victorias": "#34a853", "Derrotas": "#ea4335"})
        fig2.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20),
                           legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────────
# HISTÓRICO DE POSICIÓN
# ─────────────────────────────────────────────

def page_history():
    page_header("📈", "Histórico de Posición")

    history = load("history")
    if not history:
        st.info("Aún no hay histórico registrado. Juega partidos para generar datos.")
        return

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # ── Evolución de puntos por jugador ──
    section("Evolución de puntos")
    players = sorted(df["username"].unique())
    selected = st.multiselect(
        "Selecciona jugadores",
        players,
        default=players[:5] if len(players) > 5 else players,
    )

    if selected:
        df_sel = df[df["username"].isin(selected)]
        fig = px.line(
            df_sel, x="timestamp", y="points", color="username",
            markers=True, title="Puntos acumulados a lo largo del tiempo",
            labels={"timestamp": "Fecha", "points": "Puntos", "username": "Jugador"},
        )
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20),
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)

    # ── Histórico de posición (ranking en el tiempo) ──
    section("Histórico de posición (ranking)")

    # Para cada timestamp, calcular ranking de cada jugador con sus puntos en ese momento
    # Estrategia: para cada evento, tomar el último 'points' conocido de cada jugador hasta esa fecha
    timestamps = sorted(df["timestamp"].unique())
    ranking_rows = []
    last_points = {p: 0.0 for p in players}

    for ts in timestamps:
        # Actualizar últimos puntos hasta este timestamp
        snapshot = df[df["timestamp"] == ts]
        for _, row in snapshot.iterrows():
            last_points[row["username"]] = row["points"]
        # Calcular posiciones
        sorted_players = sorted(last_points.items(), key=lambda x: x[1], reverse=True)
        for pos, (pname, _) in enumerate(sorted_players, 1):
            ranking_rows.append({
                "timestamp": ts, "username": pname, "posicion": pos
            })

    df_rank = pd.DataFrame(ranking_rows)
    if selected:
        df_rank_sel = df_rank[df_rank["username"].isin(selected)]
        fig_r = px.line(
            df_rank_sel, x="timestamp", y="posicion", color="username",
            markers=True, title="Posición en el ranking (1 = mejor)",
            labels={"timestamp": "Fecha", "posicion": "Posición", "username": "Jugador"},
        )
        fig_r.update_yaxes(autorange="reversed")  # posición 1 arriba
        fig_r.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20),
                            legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_r, use_container_width=True)

    # ── Resumen tabla ──
    section("Resumen actual")
    users = sorted([u for u in load("users") if u["role"] == "player"],
                   key=lambda u: u.get("points", 0), reverse=True)
    df_now = pd.DataFrame([
        {"Pos": i+1, "Jugador": u["username"],
         "Puntos": u.get("points", 0),
         "V": u.get("wins", 0), "D": u.get("losses", 0)}
        for i, u in enumerate(users)
    ])
    st.dataframe(df_now, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────

def main():
    page = st.session_state.page
    u    = st.session_state.user

    if not u and page != "login":
        go("login"); st.rerun()

    routes = {
        "login":         page_login,
        "home":          page_home,
        "manage_users":  page_manage_users,
        "manage_courts": page_manage_courts,
        "manage_slots":  page_manage_slots,
        "create_match":  page_create_match,
        "auto_match":    page_auto_match,
        "enter_result":  page_enter_result,
        "results":       page_results,
        "io_excel":      page_io_excel,
        "metrics":       page_metrics,
        "history":       page_history,
    }

    admin_only = {"manage_users", "manage_courts", "manage_slots", "io_excel"}
    if page in admin_only and (not u or u["role"] != "admin"):
        st.error("Acceso solo para administradores.")
        go("home"); return

    routes.get(page, page_login)()

main()