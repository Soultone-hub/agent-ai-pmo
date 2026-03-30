import streamlit as st

st.set_page_config(
    page_title="PilotIA",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS global ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Fond général */
    .stApp { background-color: #F5F5F3; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E5E3;
        min-width: 240px;
    }

    /* Cartes */
    .card {
        background: #FFFFFF;
        border: 1px solid #E5E5E3;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
    }

    /* Badges statut */
    .badge-vert    { background:#E1F5EE; color:#1D9E75; border-radius:8px; padding:3px 10px; font-size:12px; font-weight:500; }
    .badge-orange  { background:#FAEEDA; color:#EF9F27; border-radius:8px; padding:3px 10px; font-size:12px; font-weight:500; }
    .badge-rouge   { background:#FCEBEB; color:#E24B4A; border-radius:8px; padding:3px 10px; font-size:12px; font-weight:500; }
    .badge-bleu    { background:#E6F1FB; color:#378ADD; border-radius:8px; padding:3px 10px; font-size:12px; font-weight:500; }

    /* Masquer le menu Streamlit par défaut */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* Boutons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        font-size: 13px;
    }

    /* Métriques */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E5E5E3;
        border-radius: 12px;
        padding: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────
def init_session():
    defaults = {
        "project_id": None,
        "project_name": "Mon Projet",
        "uploaded_docs": [],
        "selected_doc_id": None,
        "selected_doc_name": None,
        "chat_history": [],
        "last_analysis": None,
        "last_risks": None,
        "last_copil": None,
        "last_kpis": None,
        "kpi_score": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧭 PilotIA")
    st.markdown("---")

    # Sélecteur de projet
    st.markdown("**Projet actif**")
    project_name = st.text_input(
        "Nom du projet",
        value=st.session_state.project_name,
        label_visibility="collapsed"
    )
    if project_name != st.session_state.project_name:
        st.session_state.project_name = project_name

    project_id = st.text_input(
        "ID du projet (UUID)",
        value=st.session_state.project_id or "",
        placeholder="Coller votre UUID projet ici",
        label_visibility="visible"
    )
    if project_id and project_id != st.session_state.project_id:
        st.session_state.project_id = project_id
        st.success("Projet chargé !")

    st.markdown("---")

    # Indicateur de santé
    score = st.session_state.kpi_score
    if score >= 70:
        st.markdown('<span class="badge-vert">Projet en bonne santé</span>', unsafe_allow_html=True)
    elif score >= 40:
        st.markdown('<span class="badge-orange">Attention requise</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-rouge">Situation critique</span>', unsafe_allow_html=True)

    st.progress(score / 100 if score else 0)
    st.caption(f"Score de santé : {score}/100")

    st.markdown("---")

    # Navigation
    st.markdown("**Navigation**")
    pages = {
        "🏠  Tableau de bord":    "pages/01_dashboard.py",
        "📁  Documents":          "pages/02_documents.py",
        "🔍  Analyse IA":         "pages/03_analyse.py",
        "⚠️  Risques":            "pages/04_risques.py",
        "📋  Synthèse COPIL":     "pages/05_copil.py",
        "📊  KPI":                "pages/06_kpi.py",
        "💬  Chat IA":            "pages/07_chat.py",
    }
    for label in pages:
        st.page_link(f"frontend/{pages[label]}", label=label)

    st.markdown("---")

    # Bloc utilisateur
    st.markdown("**Utilisateur**")
    st.caption("PMO — Projet académique 2026")

# ── Page d'accueil ───────────────────────────────────────────
st.title("Bienvenue sur PilotIA 🧭")
st.markdown("#### Votre assistant IA pour le pilotage de projets stratégiques")

if not st.session_state.project_id:
    st.info("Commencez par entrer l'UUID de votre projet dans la barre latérale.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="card"><h4>📁 Uploadez vos documents</h4><p>PDF, DOCX, XLSX, EML — l\'IA les analyse automatiquement.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card"><h4>🤖 L\'IA travaille pour vous</h4><p>Extraction de risques, synthèse COPIL, KPI — en quelques secondes.</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="card"><h4>💬 Posez vos questions</h4><p>Le Chat IA connait tous vos documents et répond avec précision.</p></div>', unsafe_allow_html=True)
else:
    st.success(f"Projet actif : **{st.session_state.project_name}** — `{st.session_state.project_id}`")
    st.markdown("Utilisez la navigation à gauche pour accéder aux modules.")