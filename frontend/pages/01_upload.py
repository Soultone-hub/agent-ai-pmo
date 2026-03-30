import streamlit as st
from frontend.utils.api_client import APIClient

st.set_page_config(page_title="Documents — PilotIA", page_icon="📁", layout="wide")

# ── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #F5F5F3; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E5E3; }
    .card { background:#FFFFFF; border:1px solid #E5E5E3; border-radius:12px; padding:20px; margin-bottom:12px; }
    .doc-card { background:#FFFFFF; border:1px solid #E5E5E3; border-radius:12px; padding:16px; margin-bottom:8px; }
    .badge-pdf   { background:#FCEBEB; color:#E24B4A; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:500; }
    .badge-docx  { background:#E6F1FB; color:#378ADD; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:500; }
    .badge-xlsx  { background:#E1F5EE; color:#1D9E75; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:500; }
    .badge-eml   { background:#FAEEDA; color:#EF9F27; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:500; }
    .source-tag  { font-size:11px; color:#888; font-style:italic; }
    #MainMenu { visibility:hidden; } footer { visibility:hidden; } header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

client = APIClient()

# ── Guard — projet requis ────────────────────────────────────
if not st.session_state.get("project_id"):
    st.title("📁 Documents")
    st.markdown("""
    <div class="card" style="text-align:center; padding:48px;">
        <h3 style="color:#888; font-weight:500;">Aucun projet sélectionné</h3>
        <p style="color:#aaa; font-size:14px;">Retournez à l'accueil et entrez l'UUID de votre projet pour commencer.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

project_id = st.session_state.project_id

# ── En-tête ──────────────────────────────────────────────────
st.title("📁 Documents")
st.caption(f"Projet : {st.session_state.get('project_name', project_id)}")

# ── Bandeau complétude ───────────────────────────────────────
docs = client.list_documents(project_id)
st.session_state.uploaded_docs = docs
total = len(docs)

if total == 0:
    st.warning("Aucun document chargé — uploadez vos documents pour activer les modules d'analyse.")
elif total < 3:
    st.warning(f"{total} document(s) chargé(s). Chargez au moins 3 documents pour activer 100% des modules.")
else:
    st.success(f"{total} document(s) chargé(s) — tous les modules d'analyse sont actifs.")

st.markdown("---")

# ── Zone d'upload ────────────────────────────────────────────
st.markdown("### Importer un document")

col_upload, col_info = st.columns([2, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "Glissez-déposez ou cliquez pour sélectionner",
        type=["pdf", "docx", "xlsx", "eml"],
        label_visibility="collapsed"
    )

with col_info:
    st.markdown("""
    <div class="card">
        <p style="font-size:13px; font-weight:500; margin-bottom:8px;">Formats acceptés</p>
        <span class="badge-pdf">PDF</span>&nbsp;
        <span class="badge-docx">DOCX</span>&nbsp;
        <span class="badge-xlsx">XLSX</span>&nbsp;
        <span class="badge-eml">EML</span>
        <p style="font-size:11px; color:#888; margin-top:12px;">
            Chaque document uploadé est automatiquement indexé dans la mémoire IA du projet.
        </p>
    </div>
    """, unsafe_allow_html=True)

if uploaded_file:
    col_btn, col_name = st.columns([1, 3])
    with col_name:
        st.caption(f"Fichier sélectionné : **{uploaded_file.name}** ({round(uploaded_file.size / 1024, 1)} Ko)")
    with col_btn:
        if st.button("⬆️ Uploader", type="primary", use_container_width=True):
            with st.spinner("Upload et indexation en cours..."):
                result = client.upload_document(project_id, uploaded_file)
            if result:
                st.success(f"Document importé — {result.get('nb_chunks', 0)} passages indexés dans la mémoire IA.")
                st.session_state.uploaded_docs = client.list_documents(project_id)
                st.rerun()
            else:
                st.error("Erreur lors de l'upload. Vérifiez que le backend est démarré.")

st.markdown("---")

# ── Liste des documents ──────────────────────────────────────
st.markdown("### Documents du projet")

if not docs:
    st.markdown("""
    <div class="card" style="text-align:center; padding:32px;">
        <p style="color:#aaa; font-size:14px;">Aucun document importé pour l'instant.</p>
        <p style="color:#aaa; font-size:13px;">Importez un document ci-dessus pour commencer l'analyse.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    for doc in docs:
        ext = doc.get("filename", "").split(".")[-1].lower()
        badge_class = f"badge-{ext}" if ext in ["pdf", "docx", "xlsx", "eml"] else "badge-pdf"

        with st.container():
            col_info, col_select, col_delete = st.columns([5, 2, 1])

            with col_info:
                st.markdown(f"""
                <div style="padding:4px 0;">
                    <span class="{badge_class}">{ext.upper()}</span>&nbsp;
                    <span style="font-size:14px; font-weight:500;">{doc.get('filename')}</span><br>
                    <span class="source-tag">Importé le {doc.get('uploaded_at', '')[:10]}</span>
                </div>
                """, unsafe_allow_html=True)

            with col_select:
                if st.button("Sélectionner", key=f"sel_{doc['id']}", use_container_width=True):
                    st.session_state.selected_doc_id = doc["id"]
                    st.session_state.selected_doc_name = doc["filename"]
                    st.success(f"**{doc['filename']}** sélectionné pour les analyses.")

            with col_delete:
                if st.button("🗑️", key=f"del_{doc['id']}", help="Supprimer ce document"):
                    if client.delete_document(doc["id"]):
                        st.success("Document supprimé.")
                        st.rerun()

        st.markdown("<hr style='border:none; border-top:1px solid #E5E5E3; margin:4px 0;'>", unsafe_allow_html=True)

# ── Document sélectionné ─────────────────────────────────────
if st.session_state.get("selected_doc_id"):
    st.markdown("---")
    st.markdown(f"""
    <div class="card" style="border-left:4px solid #378ADD;">
        <p style="font-size:13px; color:#378ADD; font-weight:500; margin:0;">Document actif pour les analyses</p>
        <p style="font-size:14px; font-weight:500; margin:4px 0 0;">{st.session_state.get('selected_doc_name')}</p>
    </div>
    """, unsafe_allow_html=True)

# ── Prochaine étape ──────────────────────────────────────────
if docs:
    st.markdown("---")
    st.markdown("**Prochaine étape →** Analysez vos documents pour extraire les informations clés.")
    st.page_link("frontend/pages/03_analyse.py", label="🔍 Aller à l'Analyse IA")