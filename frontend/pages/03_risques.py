import streamlit as st
import json
import plotly.graph_objects as go
import pandas as pd
from frontend.utils.api_client import APIClient

st.set_page_config(page_title="Risques — PilotIA", page_icon="⚠️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F5F5F3; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E5E3; }
    .card { background:#FFFFFF; border:1px solid #E5E5E3; border-radius:12px; padding:20px; margin-bottom:12px; }
    .badge-critique { background:#FCEBEB; color:#E24B4A; border-radius:8px; padding:3px 10px; font-size:11px; font-weight:500; }
    .badge-eleve    { background:#FAEEDA; color:#EF9F27; border-radius:8px; padding:3px 10px; font-size:11px; font-weight:500; }
    .badge-modere   { background:#E6F1FB; color:#378ADD; border-radius:8px; padding:3px 10px; font-size:11px; font-weight:500; }
    .badge-faible   { background:#E1F5EE; color:#1D9E75; border-radius:8px; padding:3px 10px; font-size:11px; font-weight:500; }
    .risk-card { background:#FFFFFF; border:1px solid #E5E5E3; border-radius:12px; padding:16px; margin-bottom:8px; }
    .source-tag { font-size:11px; color:#888; font-style:italic; }
    #MainMenu { visibility:hidden; } footer { visibility:hidden; } header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

client = APIClient()

# ── Guard ────────────────────────────────────────────────────
if not st.session_state.get("project_id"):
    st.title("⚠️ Risques")
    st.markdown("""
    <div class="card" style="text-align:center; padding:48px;">
        <h3 style="color:#888; font-weight:500;">Aucun projet sélectionné</h3>
        <p style="color:#aaa; font-size:14px;">Retournez à l'accueil et entrez l'UUID de votre projet.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

project_id = st.session_state.project_id

# ── En-tête ──────────────────────────────────────────────────
st.title("⚠️ Risques")
st.caption(f"Projet : {st.session_state.get('project_name', project_id)}")

# ── Sélection document ───────────────────────────────────────
docs = st.session_state.get("uploaded_docs", [])

if not docs:
    st.markdown("""
    <div class="card" style="text-align:center; padding:48px;">
        <h3 style="color:#888; font-weight:500;">Aucun document disponible</h3>
        <p style="color:#aaa; font-size:14px;">Importez des documents pour extraire les risques.</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("frontend/pages/01_upload.py", label="📁 Importer des documents")
    st.stop()

doc_options = {doc["filename"]: doc["id"] for doc in docs}

col_sel, col_multi = st.columns([2, 2])
with col_sel:
    selected_name = st.selectbox(
        "Document cible",
        options=list(doc_options.keys()),
        label_visibility="visible"
    )
    selected_id = doc_options[selected_name]

with col_multi:
    multi_names = st.multiselect(
        "Ou sélectionnez plusieurs documents",
        options=list(doc_options.keys()),
        default=[]
    )
    multi_ids = [doc_options[n] for n in multi_names]

# ── Boutons d'action ─────────────────────────────────────────
col_btn1, col_btn2, col_space = st.columns([1, 1, 3])
with col_btn1:
    extract_simple = st.button(
        "⚠️ Extraire les risques",
        type="primary",
        use_container_width=True
    )
with col_btn2:
    extract_multi = st.button(
        f"⚠️ Multi ({len(multi_ids)} docs)",
        use_container_width=True,
        disabled=len(multi_ids) == 0
    )

# ── Exécution ────────────────────────────────────────────────
if extract_simple:
    with st.spinner("Extraction des risques en cours..."):
        result = client.extract_risks(project_id, selected_id)
    if result:
        st.session_state.last_risks = result
        risks = result.get("risks", [])
        critiques = len([r for r in risks if r.get("niveau") == "critique"])
        st.success(f"{len(risks)} risques identifiés — dont {critiques} critiques.")

if extract_multi and multi_ids:
    with st.spinner(f"Extraction sur {len(multi_ids)} documents..."):
        result = client.extract_risks_multi(project_id, multi_ids)
    if result:
        st.session_state.last_risks = result
        risks = result.get("risks", [])
        st.success(f"{len(risks)} risques identifiés sur {len(multi_ids)} documents.")

# Récupérer depuis la base si pas encore extrait
if not st.session_state.get("last_risks"):
    with st.spinner("Chargement des derniers risques..."):
        stored = client.get_risks(project_id)
    if stored:
        st.session_state.last_risks = stored

data = st.session_state.get("last_risks")

# ── Résultats ────────────────────────────────────────────────
if not data or not data.get("risks"):
    st.markdown("---")
    st.markdown("""
    <div class="card" style="text-align:center; padding:32px;">
        <p style="color:#aaa; font-size:14px;">Aucun risque analysé pour l'instant.</p>
        <p style="color:#aaa; font-size:13px;">Lancez une extraction pour identifier les risques de votre projet.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

risks = data.get("risks", [])

# ── Compteurs ────────────────────────────────────────────────
st.markdown("---")
critiques = [r for r in risks if r.get("niveau") == "critique"]
eleves    = [r for r in risks if r.get("niveau") == "eleve"]
moderes   = [r for r in risks if r.get("niveau") == "modere"]
faibles   = [r for r in risks if r.get("niveau") == "faible"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Critiques",     len(critiques), delta=None)
col2.metric("Élevés",        len(eleves),    delta=None)
col3.metric("Modérés",       len(moderes),   delta=None)
col4.metric("Faibles",       len(faibles),   delta=None)

st.markdown("---")

# ── Layout : Heatmap + Liste ──────────────────────────────────
col_matrix, col_list = st.columns([1, 1])

with col_matrix:
    st.markdown("#### Matrice des risques")

    # Construction de la heatmap 5x5
    matrix = [[0]*5 for _ in range(5)]
    risk_labels = [[[] for _ in range(5)] for _ in range(5)]

    for r in risks:
        p = int(r.get("probabilite", 1)) - 1
        i = int(r.get("impact", 1)) - 1
        if 0 <= p <= 4 and 0 <= i <= 4:
            matrix[4-p][i] += 1
            risk_labels[4-p][i].append(r.get("id", "?"))

    # Couleurs par zone
    colors = []
    for row_idx in range(5):
        row_colors = []
        for col_idx in range(5):
            p_val = 5 - row_idx
            i_val = col_idx + 1
            score = p_val * i_val
            if score >= 15:
                row_colors.append("#FCEBEB")
            elif score >= 10:
                row_colors.append("#FAEEDA")
            elif score >= 5:
                row_colors.append("#E6F1FB")
            else:
                row_colors.append("#E1F5EE")
        colors.append(row_colors)

    text_matrix = []
    for row_idx in range(5):
        row_text = []
        for col_idx in range(5):
            ids = risk_labels[row_idx][col_idx]
            row_text.append("<br>".join(ids) if ids else "")
        text_matrix.append(row_text)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        text=text_matrix,
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#E1F5EE"],
            [0.33, "#E6F1FB"],
            [0.66, "#FAEEDA"],
            [1.0, "#FCEBEB"]
        ],
        showscale=False,
        hovertemplate="Probabilité: %{y+1}<br>Impact: %{x+1}<br>Risques: %{text}<extra></extra>",
    ))

    fig.update_layout(
        xaxis=dict(title="Impact →", tickvals=list(range(5)), ticktext=["1","2","3","4","5"]),
        yaxis=dict(title="← Probabilité", tickvals=list(range(5)), ticktext=["5","4","3","2","1"]),
        height=350,
        margin=dict(l=40, r=20, t=20, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12)
    )
    st.plotly_chart(fig, use_container_width=True)

with col_list:
    st.markdown("#### Liste des risques")

    # Filtres
    filtre_niveau = st.selectbox(
        "Filtrer par niveau",
        ["Tous", "critique", "eleve", "modere", "faible"],
        label_visibility="visible"
    )

    filtered = risks if filtre_niveau == "Tous" else [
        r for r in risks if r.get("niveau") == filtre_niveau
    ]

    for r in filtered:
        niveau = r.get("niveau", "faible")
        badge = f'<span class="badge-{niveau}">{niveau.upper()}</span>'
        st.markdown(f"""
        <div class="risk-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:13px; font-weight:500;">{r.get('id','?')} — {r.get('description','')[:60]}...</span>
                {badge}
            </div>
            <div style="display:flex; gap:16px; font-size:12px; color:#888;">
                <span>Probabilité : <b>{r.get('probabilite')}</b></span>
                <span>Impact : <b>{r.get('impact')}</b></span>
                <span>Score : <b>{r.get('score')}</b></span>
                <span>Catégorie : <b>{r.get('categorie','?')}</b></span>
            </div>
            <p style="font-size:12px; color:#555; margin-top:8px;">
                <b>Mitigation :</b> {r.get('mitigation','Non définie')}
            </p>
            <span class="source-tag">Source : {selected_name}</span>
        </div>
        """, unsafe_allow_html=True)

# ── Résumé global ────────────────────────────────────────────
if data.get("resume"):
    st.markdown("---")
    st.markdown(f"""
    <div class="card" style="border-left:4px solid #378ADD;">
        <p style="font-size:13px; color:#378ADD; font-weight:500;">Synthèse globale des risques</p>
        <p style="font-size:14px; line-height:1.7;">{data.get('resume')}</p>
        <span class="source-tag">Généré par Groq LLaMA 3.3-70B</span>
    </div>
    """, unsafe_allow_html=True)

# ── Export ───────────────────────────────────────────────────
st.markdown("---")
col_exp1, col_exp2 = st.columns([1, 4])
with col_exp1:
    st.download_button(
        label="⬇️ Exporter JSON",
        data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name=f"risques_{project_id}.json",
        mime="application/json"
    )

# ── Prochaine étape ──────────────────────────────────────────
st.markdown("---")
st.markdown("**Prochaine étape →** Générez la synthèse COPIL avec ces risques.")
st.page_link("frontend/pages/04_copil.py", label="📋 Aller à la Synthèse COPIL")