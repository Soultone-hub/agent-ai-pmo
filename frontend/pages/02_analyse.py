import streamlit as st
import json
from frontend.utils.api_client import APIClient

st.set_page_config(page_title="Analyse IA — PilotIA", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F5F5F3; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E5E3; }
    .card { background:#FFFFFF; border:1px solid #E5E5E3; border-radius:12px; padding:20px; margin-bottom:12px; }
    .section-title { font-size:13px; font-weight:500; color:#888; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; }
    .item-row { padding:8px 0; border-bottom:1px solid #F0F0EE; font-size:14px; }
    .source-tag { font-size:11px; color:#888; font-style:italic; }
    .badge-info { background:#E6F1FB; color:#378ADD; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:500; }
    #MainMenu { visibility:hidden; } footer { visibility:hidden; } header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

client = APIClient()

# ── Guard ────────────────────────────────────────────────────
if not st.session_state.get("project_id"):
    st.title("🔍 Analyse IA")
    st.markdown("""
    <div class="card" style="text-align:center; padding:48px;">
        <h3 style="color:#888; font-weight:500;">Aucun projet sélectionné</h3>
        <p style="color:#aaa; font-size:14px;">Retournez à l'accueil et entrez l'UUID de votre projet.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

project_id = st.session_state.project_id

# ── En-tête ──────────────────────────────────────────────────
st.title("🔍 Analyse IA")
st.caption(f"Projet : {st.session_state.get('project_name', project_id)}")

# ── Sélection du document ────────────────────────────────────
docs = st.session_state.get("uploaded_docs", [])

if not docs:
    st.markdown("""
    <div class="card" style="text-align:center; padding:48px;">
        <h3 style="color:#888; font-weight:500;">Aucun document disponible</h3>
        <p style="color:#aaa; font-size:14px;">Importez d'abord des documents pour lancer une analyse.</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("frontend/pages/01_upload.py", label="📁 Aller à l'import de documents")
    st.stop()

st.markdown("### Sélection du document")

doc_options = {doc["filename"]: doc["id"] for doc in docs}
selected_name = st.selectbox(
    "Choisissez un document à analyser",
    options=list(doc_options.keys()),
    index=0,
    label_visibility="collapsed"
)
selected_id = doc_options[selected_name]

# Mode multi-documents
with st.expander("Analyser plusieurs documents à la fois"):
    multi_names = st.multiselect(
        "Sélectionnez les documents",
        options=list(doc_options.keys()),
        default=[]
    )
    multi_ids = [doc_options[n] for n in multi_names]

st.markdown("---")

# ── Lancement de l'analyse ───────────────────────────────────
st.markdown("### Lancer l'analyse")

col_btn, col_info = st.columns([1, 3])

with col_btn:
    analyse_simple = st.button(
        "🔍 Analyser ce document",
        type="primary",
        use_container_width=True,
        disabled=not selected_id
    )
    if multi_ids:
        analyse_multi = st.button(
            f"🔍 Analyser {len(multi_ids)} documents",
            use_container_width=True
        )
    else:
        analyse_multi = False

with col_info:
    st.markdown(f"""
    <div class="card">
        <p style="font-size:13px; color:#888; margin:0;">
            L'IA va extraire le résumé, les objectifs, les contraintes,
            les hypothèses et les parties prenantes depuis
            <strong>{selected_name if not multi_ids else f"{len(multi_ids)} documents sélectionnés"}</strong>.
        </p>
        <p class="source-tag" style="margin-top:8px;">
            Basé sur la recherche sémantique RAG — résultats en 2-5 secondes.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ── Exécution ────────────────────────────────────────────────
result = None

if analyse_simple:
    with st.spinner("Analyse en cours..."):
        result = client.analyze_document(selected_id)
    if result:
        st.session_state.last_analysis = result
        st.success("Analyse terminée.")

if analyse_multi and multi_ids:
    with st.spinner(f"Analyse de {len(multi_ids)} documents en cours..."):
        result = client.analyze_documents_multi(project_id, multi_ids)
    if result:
        st.session_state.last_analysis = result
        st.success("Analyse multi-documents terminée.")

# Afficher le dernier résultat si disponible
if not result and st.session_state.get("last_analysis"):
    result = st.session_state.last_analysis
    st.info("Résultats de la dernière analyse — relancez pour actualiser.")

# ── Affichage des résultats ──────────────────────────────────
if result and "analyse" in result:
    data = result["analyse"] if isinstance(result["analyse"], dict) else result
elif result and isinstance(result, dict) and "resume" in result:
    data = result
else:
    data = None

if data:
    st.markdown("---")
    st.markdown("### Résultats de l'analyse")

    # Résumé
    st.markdown('<p class="section-title">Résumé</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="card">
        <p style="font-size:14px; line-height:1.7;">{data.get('resume', 'Non disponible')}</p>
        <span class="source-tag">Source : {selected_name}</span>
    </div>
    """, unsafe_allow_html=True)

    # 3 colonnes : objectifs, contraintes, hypothèses
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<p class="section-title">Objectifs</p>', unsafe_allow_html=True)
        objectifs = data.get("objectifs", [])
        if objectifs:
            for o in objectifs:
                st.markdown(f'<div class="item-row">• {o}</div>', unsafe_allow_html=True)
        else:
            st.caption("Aucun objectif identifié")

    with col2:
        st.markdown('<p class="section-title">Contraintes</p>', unsafe_allow_html=True)
        contraintes = data.get("contraintes", [])
        if contraintes:
            for c in contraintes:
                st.markdown(f'<div class="item-row">• {c}</div>', unsafe_allow_html=True)
        else:
            st.caption("Aucune contrainte identifiée")

    with col3:
        st.markdown('<p class="section-title">Hypothèses</p>', unsafe_allow_html=True)
        hypotheses = data.get("hypotheses", [])
        if hypotheses:
            for h in hypotheses:
                st.markdown(f'<div class="item-row">• {h}</div>', unsafe_allow_html=True)
        else:
            st.caption("Aucune hypothèse identifiée")

    st.markdown("---")

    # Parties prenantes + points clés
    col4, col5 = st.columns(2)

    with col4:
        st.markdown('<p class="section-title">Parties prenantes</p>', unsafe_allow_html=True)
        parties = data.get("parties_prenantes", [])
        if parties:
            for p in parties:
                st.markdown(f"""
                <div class="item-row">
                    <span class="badge-info">{p}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("Aucune partie prenante identifiée")

    with col5:
        st.markdown('<p class="section-title">Points clés</p>', unsafe_allow_html=True)
        points = data.get("points_cles", [])
        if points:
            for pt in points:
                st.markdown(f'<div class="item-row">• {pt}</div>', unsafe_allow_html=True)
        else:
            st.caption("Aucun point clé identifié")

    # Export JSON
    st.markdown("---")
    st.download_button(
        label="⬇️ Exporter en JSON",
        data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name=f"analyse_{selected_name}.json",
        mime="application/json"
    )

# ── Prochaine étape ──────────────────────────────────────────
st.markdown("---")
st.markdown("**Prochaine étape →** Identifiez les risques de votre projet.")
st.page_link("frontend/pages/03_risques.py", label="⚠️ Aller aux Risques")