import streamlit as st

st.set_page_config(
    page_title="Bot Mi Casa Ya",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d3b6e 0%, #1a5276 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: white !important; }
    .main-header {
        background: linear-gradient(90deg, #0d3b6e, #1a5276);
        padding: 1.2rem 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .status-card {
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .status-marcado { background: #e8f5e9; border-color: #2e7d32; }
    .status-pagado { background: #e3f2fd; border-color: #1565c0; }
    .status-otro { background: #fff3e0; border-color: #e65100; }
    .status-error { background: #fce4ec; border-color: #b71c1c; }
    .metric-box {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-number { font-size: 2rem; font-weight: 700; color: #0d3b6e; }
    .metric-label { font-size: 0.85rem; color: #666; margin-top: 0.2rem; }
    .log-box {
        background: #1e1e1e;
        color: #00ff88;
        font-family: monospace;
        font-size: 0.82rem;
        padding: 1rem;
        border-radius: 8px;
        height: 320px;
        overflow-y: auto;
    }
    .stButton > button {
        width: 100%;
        background: #0d3b6e;
        color: white;
        border: none;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .stButton > button:hover { background: #1a5276; }
    .btn-stop > button { background: #c0392b !important; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h2 style="margin:0">🏠 Bot Mi Casa Ya</h2>
    <p style="margin:0.3rem 0 0; opacity:0.85; font-size:0.9rem">
        Automatización de consulta de estado y marcación para pago — Constructora Bolívar
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar navegación
with st.sidebar:
    st.markdown("## 🏠 Mi Casa Ya Bot")
    st.markdown("---")
    pagina = st.radio(
        "Navegación",
        ["🏠 Inicio", "⚙️ Configuración", "▶️ Ejecutar Bot", "📊 Historial"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown("**Versión:** 1.0.0")
    st.markdown("**Constructora Bolívar**")

# Routing de páginas
if pagina == "🏠 Inicio":
    from pages.inicio import mostrar
    mostrar()
elif pagina == "⚙️ Configuración":
    from pages.configuracion import mostrar
    mostrar()
elif pagina == "▶️ Ejecutar Bot":
    from pages.ejecutar import mostrar
    mostrar()
elif pagina == "📊 Historial":
    from pages.historial import mostrar
    mostrar()
