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
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def conectar_desde_secrets():
    """Conecta a Google Sheets usando st.secrets (Streamlit Cloud)"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = st.secrets.get("SPREADSHEET_ID", "")
        return client, sheet_id
    except Exception as e:
        raise Exception(f"Error leyendo secrets: {e}")

def mostrar():
    st.markdown("## Configuracion")
    config = cargar_config()

    tab1, tab2, tab3, tab4 = st.tabs(["Credenciales TransUnion", "Google Sheets", "Cargar Cedulas", "Opciones del Bot"])

    with tab1:
        st.markdown("### Credenciales Mi Portafolio TransUnion")
        st.info("Estas credenciales se guardan localmente en tu equipo.")
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

        # Detectar si estamos en Streamlit Cloud (secrets disponibles)
        usando_secrets = "gcp_service_account" in st.secrets

        if usando_secrets:
            st.success("Modo nube detectado: usando credenciales desde Secrets de Streamlit.")
            sheet_id = st.secrets.get("SPREADSHEET_ID", "")
            st.info(f"Sheet ID configurado: `{sheet_id}`")

            if st.button("Probar conexion a Sheets"):
                try:
                    import gspread
                    from google.oauth2.service_account import Credentials
                    scopes = [
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive"
                    ]
                    creds_dict = dict(st.secrets["gcp_service_account"])
                    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                    client = gspread.authorize(creds)
                    spreadsheet = client.open_by_key(sheet_id)
                    hoja = spreadsheet.worksheet("Entrada")
                    datos = hoja.get_all_values()
                    # Buscar columna de cédulas
                    cedulas = []
                    for fila in datos[1:]:  # saltar encabezado
                        for celda in fila:
                            celda = str(celda).strip()
                            if celda.isdigit() and 7 <= len(celda) <= 12:
                                cedulas.append(celda)
                                break
                    st.success(f"Conexion exitosa: {len(cedulas)} cedulas en la hoja Entrada")
                    config["sheet_id"] = sheet_id
                    config["usar_sheets"] = True
                    guardar_config(config)
                    if cedulas:
                        st.dataframe(pd.DataFrame({"cedula": cedulas[:5]}), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Error de conexion: {e}")
        else:
            # Modo local: usar archivo JSON
            st.info("Modo local: ingresa la ruta al archivo de credenciales.")
            col1, col2 = st.columns(2)
            with col1:
                ruta_creds = st.text_input("Archivo JSON de credenciales", value=config.get("google_creds", "credenciales_google.json"))
            with col2:
                sheet_id = st.text_input("ID del Google Sheets", value=config.get("sheet_id", ""), placeholder="1jVhPKD9XFO7p-ErF-Bxt4BIMjIO_Qg0w3CAv5OUkIeA")
            if st.button("Probar conexion a Sheets"):
                if not os.path.exists(ruta_creds):
                    st.error(f"No se encontro el archivo: {ruta_creds}")
                elif not sheet_id:
                    st.error("Ingresa el ID del Sheets")
                else:
                    try:
                        from utils.sheets import conectar_sheets, leer_cedulas
                        wb = conectar_sheets(ruta_creds, sheet_id)
                        cedulas = leer_cedulas(wb)
                        st.success(f"Conexion exitosa: {len(cedulas)} cedulas en la hoja Entrada")
                        config["google_creds"] = ruta_creds
                        config["sheet_id"] = sheet_id
                        config["usar_sheets"] = True
                        guardar_config(config)
                        st.dataframe(pd.DataFrame(cedulas[:5]), use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.error(f"Error de conexion: {e}")

        if config.get("usar_sheets"):
            st.success("Sheets conectado actualmente")
            if st.button("Desconectar Sheets"):
                config["usar_sheets"] = False
                guardar_config(config)
                st.rerun()

    with tab3:
        st.markdown("### Cargar cedulas desde Excel")
        if config.get("usar_sheets"):
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
            if "df_cedulas" in st.session_state:
                st.success(f"{len(st.session_state['df_cedulas'])} cedulas listas: {st.session_state.get('archivo_nombre','')}")

    with tab4:
        st.markdown("### Opciones de ejecucion")
        col1, col2 = st.columns(2)
        with col1:
            mostrar_navegador = st.toggle("Mostrar navegador", value=config.get("mostrar_navegador", False))
            solo_fase1 = st.toggle("Solo Fase 1 (solo consultar estados)", value=config.get("solo_fase1", True))
        with col2:
            delay = st.slider("Pausa entre cedulas (segundos)", 1, 10, config.get("delay", 3))
            reintentos = st.slider("Reintentos en caso de error", 1, 5, config.get("reintentos", 2))
        if st.button("Guardar opciones"):
            config["mostrar_navegador"] = mostrar_navegador
            config["solo_fase1"] = solo_fase1
            config["delay"] = delay
            config["reintentos"] = reintentos
            guardar_config(config)
            st.success("Opciones guardadas")
        st.markdown("---")
        checks = {
            "Credenciales TransUnion": bool(config.get("usuario") and config.get("password")),
            "Google Sheets conectado": bool(config.get("usar_sheets")),
            "Cedulas cargadas (Excel)": "df_cedulas" in st.session_state,
        }
        for label, ok in checks.items():
            if ok:
                st.success(f"OK: {label}")
            else:
                st.warning(f"Pendiente: {label}")
