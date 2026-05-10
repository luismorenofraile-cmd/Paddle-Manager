# app.py - Gestión de Partidos de Pádel
# pip install streamlit
# Ejecutar: streamlit run app.py

import streamlit as st
import json, os, hashlib, itertools
from datetime import datetime

# ─────────────────────────────────────────────
# PERSISTENCIA JSON
# ─────────────────────────────────────────────

DB_DIR = "padel_db"
os.makedirs(DB_DIR, exist_ok=True)

FILES = {
    "users":   os.path.join(DB_DIR, "users.json"),
    "courts":  os.path.join(DB_DIR, "courts.json"),
    "slots":   os.path.join(DB_DIR, "slots.json"),
    "matches": os.path.join(DB_DIR, "matches.json"),
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
# puntos por juego ganado : 0.1
# puntos por set ganado   : 0.2
# puntos por ganar partido: 2.0
# Partido al mejor de 3 sets
# ─────────────────────────────────────────────

def calc_points(games_won, sets_won, match_won):
    return round(games_won * 0.1 + sets_won * 0.2 + (2.0 if match_won else 0), 2)

def parse_sets(sets_str):
    """
    Recibe una cadena tipo '6-4,3-6,7-5'
    Devuelve (sets_ganados, sets_perdidos, juegos_ganados, juegos_perdidos)
    """
    sets_w = sets_l = games_w = games_l = 0
    for s in sets_str.strip().split(","):
        s = s.strip()
        if "-" not in s:
            raise ValueError(f"Formato incorrecto: '{s}'")
        a, b = s.split("-")
        a, b = int(a.strip()), int(b.strip())
        games_w += a
        games_l += b
        if a > b:
            sets_w += 1
        else:
            sets_l += 1
    if sets_w + sets_l > 3:
        raise ValueError("Máximo 3 sets por partido")
    return sets_w, sets_l, games_w, games_l

# ─────────────────────────────────────────────
# INIT ADMIN
# ─────────────────────────────────────────────

def init_admin():
    users = load("users")
    if not any(u["role"] == "admin" for u in users):
        users.append({
            "id": "admin",
            "username": "admin",
            "email": "admin@padel.com",
            "phone": "000000000",
            "password": hp("admin123"),
            "role": "admin",
            "wins": 0, "losses": 0,
            "points": 0.0,
        })
        save("users", users)

init_admin()

# ─────────────────────────────────────────────
# SESIÓN
# ─────────────────────────────────────────────

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"

def go(page): st.session_state.page = page

# ─────────────────────────────────────────────
# CSS MÓVIL
# ─────────────────────────────────────────────

st.markdown("""
<style>
    /* Fondo y tipografía general */
    html, body, [data-testid="stAppViewContainer"] {
        background: #f0f4f8;
        font-family: 'Segoe UI', sans-serif;
    }
    /* Contenedor central estrecho (aspecto móvil) */
    .block-container {
        max-width: 480px !important;
        margin: auto;
        padding: 1rem 1rem 4rem 1rem;
    }
    /* Título principal */
    .app-title {
        text-align: center;
        font-size: 1.8rem;
        font-weight: 800;
        color: #1a73e8;
        margin-bottom: 0.2rem;
    }
    .app-sub {
        text-align: center;
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 1.4rem;
    }
    /* Tarjetas */
    .card {
        background: white;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    }
    .card-title {
        font-weight: 700;
        font-size: 1rem;
        color: #1a1a2e;
        margin-bottom: 0.3rem;
    }
    .card-sub {
        font-size: 0.82rem;
        color: #555;
    }
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-blue  { background:#e8f0fe; color:#1a73e8; }
    .badge-green { background:#e6f4ea; color:#1e8e3e; }
    .badge-orange{ background:#fef3e2; color:#e37400; }
    .badge-red   { background:#fce8e6; color:#c5221f; }
    /* Botones grandes tipo móvil */
    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        height: 3rem;
        font-size: 0.95rem;
        font-weight: 600;
        border: none;
    }
    /* Separador de sección */
    .section-label {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #999;
        margin: 1rem 0 0.4rem 0;
    }
    /* Ranking podio */
    .rank-1 { color: #f9a825; font-weight:800; }
    .rank-2 { color: #78909c; font-weight:700; }
    .rank-3 { color: #a1674a; font-weight:700; }
    /* Input labels */
    label { font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS DE UI
# ─────────────────────────────────────────────

def card(title, body="", badge=None, badge_type="blue"):
    badge_html = (f'<span class="badge badge-{badge_type}">{badge}</span>'
                  if badge else "")
    st.markdown(
        f'<div class="card"><div class="card-title">{title} {badge_html}</div>'
        f'<div class="card-sub">{body}</div></div>',
        unsafe_allow_html=True)

def section(label):
    st.markdown(f'<div class="section-label">{label}</div>', unsafe_allow_html=True)

def page_header(icon, title, back=True):
    st.markdown(f'<div class="app-title">{icon} {title}</div>', unsafe_allow_html=True)
    if back:
        if st.button("← Volver al menú", key=f"back_{title}"):
            go("home")
        st.write("")

# ─────────────────────────────────────────────
# PÁGINA: LOGIN
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
        match = next((x for x in users
                      if (x["username"] == u or x["email"] == u)
                      and x["password"] == hp(p)), None)
        if match:
            st.session_state.user = match
            go("home")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

# ─────────────────────────────────────────────
# PÁGINA: HOME / MENÚ
# ─────────────────────────────────────────────

def page_home():
    u = st.session_state.user
    st.markdown(f'<div class="app-title">🏓 Pádel Manager</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-sub">Hola, <b>{u["username"]}</b> '
                f'{"👑 Admin" if u["role"]=="admin" else "🎾 Jugador"}</div>',
                unsafe_allow_html=True)

    section("Partidos")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Partido\nManual"):     go("create_match")
    with c2:
        if st.button("🤖 Partido\nAutomático"): go("auto_match")

    c3, c4 = st.columns(2)
    with c3:
        if st.button("📋 Ver\nResultados"):     go("results")
    with c4:
        if st.button("✏️ Introducir\nResultado"): go("enter_result")

    if u["role"] == "admin":
        section("Administración")
        if st.button("👥 Gestionar Usuarios"):  go("manage_users")
        if st.button("🏟️ Gestionar Pistas"):    go("manage_courts")
        if st.button("🕐 Gestionar Horarios"):  go("manage_slots")

    section("")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        go("login")
        st.rerun()

# ─────────────────────────────────────────────
# PÁGINA: GESTIONAR USUARIOS (Admin)
# ─────────────────────────────────────────────

def page_manage_users():
    page_header("👥", "Usuarios")

    section("Crear nuevo usuario")
    with st.form("new_user"):
        username = st.text_input("Nombre de usuario")
        email    = st.text_input("Email")
        phone    = st.text_input("Teléfono")
        password = st.text_input("Contraseña", type="password")
        submit   = st.form_submit_button("Crear Usuario")

    if submit:
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
                    "phone": phone, "password": hp(password),
                    "role": "player",
                    "wins": 0, "losses": 0, "points": 0.0,
                })
                save("users", users)
                st.success(f"✅ Usuario '{username}' creado.")
                st.rerun()

    section("Usuarios registrados")
    users = load("users")
    players = [u for u in users if u["role"] == "player"]
    if not players:
        st.info("No hay jugadores registrados aún.")
    for u in players:
        card(
            f"🧑 {u['username']}",
            f"📧 {u['email']} · 📱 {u['phone']}<br>"
            f"🏆 {u['wins']}V / {u['losses']}D · ⭐ {u.get('points', 0)} pts",
        )

# ─────────────────────────────────────────────
# PÁGINA: GESTIONAR PISTAS
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
            st.success("✅ Pista añadida.")
            st.rerun()

    section("Pistas disponibles")
    courts = load("courts")
    if not courts:
        st.info("No hay pistas registradas.")
    for c in courts:
        card(f"🏟️ {c['name']}", c["location"])

# ─────────────────────────────────────────────
# PÁGINA: GESTIONAR HORARIOS
# ─────────────────────────────────────────────

def page_manage_slots():
    page_header("🕐", "Horarios")

    courts = load("courts")
    if not courts:
        st.warning("Primero debes crear al menos una pista.")
        return

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
        st.success("✅ Horario añadido.")
        st.rerun()

    section("Horarios")
    slots = load("slots")
    if not slots:
        st.info("No hay horarios registrados.")
    for s in slots:
        estado = "🔒 Ocupado" if s.get("booked") else "✅ Libre"
        badge_t = "red" if s.get("booked") else "green"
        card(f"📅 {s['date']} {s['time']} — {s['court']}",
             badge=estado, badge_type=badge_t)

# ─────────────────────────────────────────────
# PÁGINA: CREAR PARTIDO MANUAL
# ─────────────────────────────────────────────

def page_create_match():
    page_header("➕", "Partido Manual")

    users  = [u for u in load("users") if u["role"] == "player"]
    slots  = [s for s in load("slots") if not s.get("booked")]

    if len(users) < 4:
        st.warning("Necesitas al menos 4 jugadores registrados para formar 2 parejas.")
        return
    if not slots:
        st.warning("No hay horarios libres disponibles.")
        return

    user_names = [u["username"] for u in users]
    slot_labels = [f"{s['date']} {s['time']} — {s['court']}" for s in slots]

    section("Pareja 1")
    p1a = st.selectbox("Jugador 1A", user_names, key="p1a")
    p1b = st.selectbox("Jugador 1B", user_names, key="p1b")
    section("Pareja 2")
    p2a = st.selectbox("Jugador 2A", user_names, key="p2a")
    p2b = st.selectbox("Jugador 2B", user_names, key="p2b")
    section("Horario")
    slot_sel = st.selectbox("Horario", slot_labels)

    if st.button("✅ Crear Partido"):
        chosen = {p1a, p1b, p2a, p2b}
        if len(chosen) < 4:
            st.error("Los 4 jugadores deben ser distintos.")
        else:
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
                if s["id"] == slot_obj["id"]:
                    s["booked"] = True
            save("slots", all_slots)
            st.success(f"✅ Partido creado: {p1a}/{p1b} vs {p2a}/{p2b}")
            st.balloons()

# ─────────────────────────────────────────────
# PÁGINA: PARTIDO AUTOMÁTICO (por ranking)
# ─────────────────────────────────────────────

def page_auto_match():
    page_header("🤖", "Partido Automático")

    st.markdown("""
    <div class="card">
    <div class="card-title">¿Cómo funciona?</div>
    <div class="card-sub">
    El sistema ordena los jugadores por puntos y forma 2 parejas equilibradas:<br>
    · Ordena de mayor a menor puntuación<br>
    · Pareja 1: jugadores #1 y #3<br>
    · Pareja 2: jugadores #2 y #4<br>
    Esto equilibra el nivel entre ambas parejas.
    </div></div>
    """, unsafe_allow_html=True)

    users = [u for u in load("users") if u["role"] == "player"]
    slots = [s for s in load("slots") if not s.get("booked")]

    if len(users) < 4:
        st.warning("Necesitas al menos 4 jugadores registrados.")
        return
    if not slots:
        st.warning("No hay horarios libres disponibles.")
        return

    # Vista previa del emparejamiento
    sorted_users = sorted(users, key=lambda u: u.get("points", 0), reverse=True)
    p1a, p2a, p1b, p2b = sorted_users[0], sorted_users[1], sorted_users[2], sorted_users[3]

    section("Emparejamiento propuesto")
    col1, col2 = st.columns(2)
    with col1:
        card("Pareja 1",
             f"🎾 {p1a['username']} ({p1a.get('points',0)} pts)<br>"
             f"🎾 {p1b['username']} ({p1b.get('points',0)} pts)",
             badge_type="blue")
    with col2:
        card("Pareja 2",
             f"🎾 {p2a['username']} ({p2a.get('points',0)} pts)<br>"
             f"🎾 {p2b['username']} ({p2b.get('points',0)} pts)",
             badge_type="orange")

    section("Horario")
    slot_labels = [f"{s['date']} {s['time']} — {s['court']}" for s in slots]
    slot_sel    = st.selectbox("Selecciona horario", slot_labels)

    if st.button("🤖 Generar Partido"):
        slot_obj = next(s for s in slots
                        if f"{s['date']} {s['time']} — {s['court']}" == slot_sel)
        matches = load("matches")
        matches.append({
            "id": f"match_{len(matches)+1}",
            "pair1": [p1a["username"], p1b["username"]],
            "pair2": [p2a["username"], p2b["username"]],
            "pair1_name": f"{p1a['username']} / {p1b['username']}",
            "pair2_name": f"{p2a['username']} / {p2b['username']}",
            "date": slot_obj["date"], "time": slot_obj["time"],
            "court": slot_obj["court"],
            "result": None, "winner": None,
            "created_by": "AUTO",
        })
        save("matches", matches)
        all_slots = load("slots")
        for s in all_slots:
            if s["id"] == slot_obj["id"]:
                s["booked"] = True
        save("slots", all_slots)
        st.success("✅ Partido generado automáticamente.")
        st.balloons()

# ─────────────────────────────────────────────
# PÁGINA: INTRODUCIR RESULTADO
# ─────────────────────────────────────────────

def page_enter_result():
    page_header("✏️", "Introducir Resultado")

    pending = [m for m in load("matches") if not m.get("result")]
    if not pending:
        st.info("No hay partidos pendientes de resultado.")
        return

    match_labels = [f"{m['pair1_name']} vs {m['pair2_name']} ({m['date']})"
                    for m in pending]
    sel = st.selectbox("Partido", match_labels)
    match = pending[match_labels.index(sel)]

    st.markdown(f"""
    <div class="card">
    <div class="card-title">📋 {match['pair1_name']}</div>
    <div class="card-sub">vs</div>
    <div class="card-title">📋 {match['pair2_name']}</div>
    <div class="card-sub">📅 {match['date']} {match['time']} · 🏟️ {match['court']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="card-sub" style="margin-bottom:0.5rem">
    Introduce cada set separado por comas. Ejemplo: <b>6-4,4-6,7-5</b>
    </div>
    """, unsafe_allow_html=True)

    s1_str = st.text_input(f"Sets de {match['pair1_name']}", placeholder="6-4,4-6,7-5")
    s2_str = st.text_input(f"Sets de {match['pair2_name']}", placeholder="4-6,6-4,5-7")

    if st.button("💾 Guardar Resultado"):
        try:
            sw1, sl1, gw1, gl1 = parse_sets(s1_str)
            sw2, sl2, gw2, gl2 = parse_sets(s2_str)

            # Consistencia cruzada
            if sw1 != sl2 or sw2 != sl1:
                st.error("Los sets de una pareja deben ser los perdidos de la otra.")
                return
            if gw1 != gl2 or gw2 != gl1:
                st.error("Los juegos no cuadran entre ambas parejas.")
                return

            # Ganador del partido (mejor de 3)
            winner_pair = "pair1" if sw1 > sw2 else "pair2"
            loser_pair  = "pair2" if winner_pair == "pair1" else "pair1"
            winner_name = match[f"{winner_pair}_name"]
            loser_name  = match[f"{loser_pair}_name"]

            # Calcular puntos
            pts_winner = calc_points(
                gw1 if winner_pair == "pair1" else gw2,
                sw1 if winner_pair == "pair1" else sw2,
                match_won=True
            )
            pts_loser = calc_points(
                gw1 if loser_pair == "pair1" else gw2,
                sw1 if loser_pair == "pair1" else sw2,
                match_won=False
            )

            # Actualizar matches
            all_matches = load("matches")
            for m in all_matches:
                if m["id"] == match["id"]:
                    m["result"]    = f"{match['pair1_name']}: {s1_str}  |  {match['pair2_name']}: {s2_str}"
                    m["winner"]    = winner_name
                    m["pts_pair1"] = pts_winner if winner_pair == "pair1" else pts_loser
                    m["pts_pair2"] = pts_winner if winner_pair == "pair2" else pts_loser
                    break
            save("matches", all_matches)

            # Actualizar stats de jugadores
            users = load("users")
            for u in users:
                if u["username"] in match[f"{winner_pair}"]:
                    u["wins"]   = u.get("wins", 0) + 1
                    u["points"] = round(u.get("points", 0) + pts_winner, 2)
                elif u["username"] in match[f"{loser_pair}"]:
                    u["losses"] = u.get("losses", 0) + 1
                    u["points"] = round(u.get("points", 0) + pts_loser, 2)
            save("users", users)

            st.success(f"✅ Ganador: **{winner_name}** (+{pts_winner} pts)")
            st.info(f"🥈 {loser_name} suma +{pts_loser} pts")
            st.balloons()

        except ValueError as e:
            st.error(f"Error en el formato: {e}")

# ─────────────────────────────────────────────
# PÁGINA: RESULTADOS Y RANKING
# ─────────────────────────────────────────────

def page_results():
    page_header("📋", "Resultados & Ranking")

    # Ranking
    section("🏆 Ranking de Jugadores")
    users = sorted(
        [u for u in load("users") if u["role"] == "player"],
        key=lambda u: u.get("points", 0), reverse=True
    )
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users):
        total   = u.get("wins", 0) + u.get("losses", 0)
        pct     = f"{int(u['wins']/total*100)}%" if total else "–"
        medal   = medals[i] if i < 3 else f"{i+1}."
        card(
            f"{medal} {u['username']}",
            f"⭐ <b>{u.get('points',0)} pts</b> · "
            f"✅ {u.get('wins',0)}V / ❌ {u.get('losses',0)}D · {pct} victorias"
        )

    # Tabla de puntuación
    with st.expander("ℹ️ Sistema de puntuación"):
        st.markdown("""
        | Hito | Puntos |
        |---|---|
        | Juego ganado | +0.1 |
        | Set ganado | +0.2 |
        | Ganar el partido | +1.0 |
        """)

    # Partidos
    section("📅 Historial de Partidos")
    matches = list(reversed(load("matches")))
    if not matches:
        st.info("No hay partidos registrados.")
    for m in matches:
        if m.get("result"):
            winner = m.get("winner", "–")
            card(
                f"🏆 {m['pair1_name']} vs {m['pair2_name']}",
                f"📅 {m['date']} {m['time']} · 🏟️ {m['court']}<br>"
                f"Sets: {m['result'].split('|')[0].split(':')[1].strip()} "
                f"/ {m['result'].split('|')[1].split(':')[1].strip()}<br>"
                f"🥇 Ganador: <b>{winner}</b> "
                f"(+{m.get('pts_pair1' if m['pair1_name']==winner else 'pts_pair2', 0)} pts)",
                badge="Jugado", badge_type="green"
            )
        else:
            card(
                f"⏳ {m['pair1_name']} vs {m['pair2_name']}",
                f"📅 {m['date']} {m['time']} · 🏟️ {m['court']}",
                badge="Pendiente", badge_type="orange"
            )

# ─────────────────────────────────────────────
# ROUTER PRINCIPAL
# ─────────────────────────────────────────────

def main():
    page = st.session_state.page
    u    = st.session_state.user

    # Redirigir a login si no hay sesión
    if not u and page != "login":
        go("login")
        st.rerun()

    routes = {
        "login":        page_login,
        "home":         page_home,
        "manage_users": page_manage_users,
        "manage_courts":page_manage_courts,
        "manage_slots": page_manage_slots,
        "create_match": page_create_match,
        "auto_match":   page_auto_match,
        "enter_result": page_enter_result,
        "results":      page_results,
    }

    # Proteger rutas de admin
    admin_only = {"manage_users", "manage_courts", "manage_slots"}
    if page in admin_only and (not u or u["role"] != "admin"):
        st.error("Acceso solo para administradores.")
        go("home")
        return

    routes.get(page, page_login)()

    # Rerun automático al cambiar de página
    if st.session_state.get("_last_page") != page:
        st.session_state["_last_page"] = page

main()
