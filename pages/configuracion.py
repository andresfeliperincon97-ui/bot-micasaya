import streamlit as st
import pandas as pd
import json
import os

CONFIG_FILE = "config.json"

def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass  # En Railway el filesystem es efímero

def _tiene_secrets():
    """Detecta si estamos en Streamlit Cloud con secrets."""
    try:
        import streamlit as st
        return "gcp_service_account" in st.secrets
    except Exception:
        return False

def _tiene_env():
    """Detecta si estamos en Railway con variables de entorno."""
    return bool(os.environ.get("GCP_SERVICE_ACCOUNT"))

def mostrar():
    st.markdown("## Configuracion")
    config = cargar_config()

    tab1, tab2, tab3, tab4 = st.tabs(["Credenciales TransUnion", "Google Sheets", "Cargar Cedulas", "Opciones del Bot"])

    with tab1:
        st.markdown("### Credenciales Mi Portafolio TransUnion")

        # En Railway leer desde variables de entorno
        usuario_env = os.environ.get("TRANSUNION_USUARIO", "")
        password_env = os.environ.get("TRANSUNION_PASSWORD", "")

        if usuario_env and password_env:
            st.success("Credenciales TransUnion cargadas desde variables de entorno del servidor.")
            # Guardar en config para que el bot las use
            config["usuario"] = usuario_env
            config["password"] = password_env
            guardar_config(config)
        else:
            st.info("Ingresa las credenciales manualmente.")
            col1, col2 = st.columns(2)
            with col1:
                usuario = st.text_input("Usuario", value=config.get("usuario", ""))
            with col2:
                password = st.text_input("Contrasena", value=config.get("password", ""), type="password")
            if st.button("Guardar credenciales"):
                if usuario and password:
                    config["usuario"] = usuario
                    config["password"] = password
                    guardar_config(config)
                    st.success("Credenciales guardadas correctamente")
                else:
                    st.error("Ingresa usuario y contrasena")

    with tab2:
        st.markdown("### Conexion a Google Sheets")

        usando_secrets = _tiene_secrets()
        usando_env = _tiene_env()

        if usando_secrets:
            st.success("Modo Streamlit Cloud: usando credenciales desde Secrets.")
            sheet_id = st.secrets.get("SPREADSHEET_ID", "")
            st.info(f"Sheet ID: `{sheet_id}`")
        elif usando_env:
            st.success("Modo Railway: usando credenciales desde variables de entorno.")
            sheet_id = os.environ.get("SPREADSHEET_ID", "")
            st.info(f"Sheet ID: `{sheet_id}`")
        else:
            st.info("Modo local: ingresa la ruta al archivo de credenciales.")
            col1, col2 = st.columns(2)
            with col1:
                ruta_creds = st.text_input("Archivo JSON", value=config.get("google_creds", "credenciales_google.json"))
            with col2:
                sheet_id = st.text_input("ID del Google Sheets", value=config.get("sheet_id", ""))

        if st.button("Probar conexion a Sheets"):
            try:
                from utils.sheets import conectar_sheets, leer_cedulas
                ruta = config.get("google_creds") if not (usando_secrets or usando_env) else None
                sid = sheet_id if not (usando_secrets or usando_env) else None
                wb = conectar_sheets(ruta, sid)
                cedulas = leer_cedulas(wb)
                st.success(f"Conexion exitosa: {len(cedulas)} cedulas en la hoja Entrada")
                config["sheet_id"] = sheet_id
                config["usar_sheets"] = True
                guardar_config(config)
                if cedulas:
                    st.dataframe(pd.DataFrame(cedulas[:5]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error de conexion: {e}")

        if config.get("usar_sheets") or usando_env or usando_secrets:
            st.success("Sheets conectado actualmente")

    with tab3:
        st.markdown("### Cargar cedulas desde Excel")
        if config.get("usar_sheets") or _tiene_secrets() or _tiene_env():
            st.info("Sheets conectado: el bot lee cedulas directamente desde Google Sheets.")
        else:
            archivo = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=["xlsx","xls"])
            if archivo:
                try:
                    df_raw = pd.read_excel(archivo, header=None)
                    col_cedula = None
                    mejor = 0
                    for col in df_raw.columns:
                        cnt = df_raw[col].astype(str).str.match(r'^\d{7,12}$').sum()
                        if cnt > mejor:
                            mejor = cnt
                            col_cedula = col
                    if col_cedula is None:
                        st.error("No se encontraron cedulas validas")
                    else:
                        ceds = df_raw[col_cedula].dropna().astype(str).str.strip()
                        ceds = ceds[ceds.str.match(r'^\d{7,12}$')].reset_index(drop=True)
                        df_f = pd.DataFrame({"cedula": ceds, "nombre": ""})
                        st.success(f"{len(df_f)} cedulas encontradas")
                        st.dataframe(df_f.head(10), use_container_width=True, hide_index=True)
                        st.session_state["df_cedulas"] = df_f
                        st.session_state["archivo_nombre"] = archivo.name
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab4:
        st.markdown("### Opciones de ejecucion")
        col1, col2 = st.columns(2)
        with col1:
            solo_fase1 = st.toggle("Solo Fase 1 (solo consultar estados)", value=config.get("solo_fase1", True))
        with col2:
            delay = st.slider("Pausa entre cedulas (segundos)", 1, 10, config.get("delay", 2))
            reintentos = st.slider("Reintentos en caso de error", 1, 5, config.get("reintentos", 2))
        if st.button("Guardar opciones"):
            config["solo_fase1"] = solo_fase1
            config["delay"] = delay
            config["reintentos"] = reintentos
            guardar_config(config)
            st.success("Opciones guardadas")
        st.markdown("---")
        checks = {
            "Credenciales TransUnion": bool(config.get("usuario") or os.environ.get("TRANSUNION_USUARIO")),
            "Google Sheets conectado": bool(config.get("usar_sheets") or _tiene_secrets() or _tiene_env()),
            "Cedulas cargadas": "df_cedulas" in st.session_state or _tiene_env() or _tiene_secrets(),
        }
        for label, ok in checks.items():
            if ok:
                st.success(f"OK: {label}")
            else:
                st.warning(f"Pendiente: {label}")
