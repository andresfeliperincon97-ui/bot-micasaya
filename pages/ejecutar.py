import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

CONFIG_FILE = "config.json"
RESULTADOS_FILE = "resultados.json"

def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_resultados(resultados):
    datos = []
    if os.path.exists(RESULTADOS_FILE):
        with open(RESULTADOS_FILE, "r") as f:
            try:
                datos = json.load(f)
            except Exception:
                datos = []
    datos.extend(resultados)
    with open(RESULTADOS_FILE, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def obtener_cedulas(config):
    if config.get("usar_sheets") or "gcp_service_account" in st.secrets:
        from utils.sheets import conectar_sheets, leer_cedulas
        sheet_id = config.get("sheet_id") or st.secrets.get("SPREADSHEET_ID", "")
        wb = conectar_sheets(sheet_id=sheet_id)
        st.session_state["_workbook"] = wb
        return leer_cedulas(wb)
    elif "df_cedulas" in st.session_state:
        return st.session_state["df_cedulas"].to_dict("records")
    return []

def mostrar():
    st.markdown("## Ejecutar Bot")
    config = cargar_config()

    tiene_sheets = config.get("usar_sheets") or ("gcp_service_account" in st.secrets)
    tiene_cedulas = tiene_sheets or ("df_cedulas" in st.session_state)

    if not tiene_cedulas:
        st.error("⚠ Pendiente: No hay cédulas cargadas — conecta Google Sheets o carga un Excel en Configuración")
        return

    if "bot_corriendo" not in st.session_state:
        st.session_state["bot_corriendo"] = False
    if "bot_resultados" not in st.session_state:
        st.session_state["bot_resultados"] = []

    try:
        registros = obtener_cedulas(config)
        cedulas = [r["cedula"] for r in registros]
        nombres = {r["cedula"]: r.get("nombre", "") for r in registros}
    except Exception as e:
        st.error(f"Error al cargar cédulas: {e}")
        return

    if not cedulas:
        st.warning("No se encontraron cédulas en la hoja Entrada del Google Sheets.")
        return

    fuente = "Google Sheets" if tiene_sheets else "Excel local"
    delay = config.get("delay", 2)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{len(cedulas)}</div><div class="metric-label">Cédulas ({fuente})</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box"><div class="metric-number" style="font-size:1rem">Fase 1</div><div class="metric-label">Modo activo</div></div>', unsafe_allow_html=True)
    with col3:
        mins = max(1, len(cedulas) * (delay + 2) // 60)
        st.markdown(f'<div class="metric-box"><div class="metric-number">~{mins} min</div><div class="metric-label">Tiempo estimado</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        iniciar = st.button("▶ Iniciar Bot", disabled=st.session_state["bot_corriendo"], use_container_width=True)
    with col_btn2:
        if st.button("🗑 Limpiar", use_container_width=True):
            st.session_state["bot_resultados"] = []
            st.rerun()

    if iniciar:
        st.session_state["bot_corriendo"] = True
        st.session_state["bot_resultados"] = []

        progreso_bar = st.progress(0, text="Iniciando...")
        log_placeholder = st.empty()
        tabla_placeholder = st.empty()
        logs = []
        resultados = []
        wb = st.session_state.get("_workbook")

        def callback(idx, total, resultado, mensaje):
            if mensaje:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}")
            if resultado:
                resultado["nombre"] = nombres.get(resultado.get("cedula", ""), "")
                resultados.append(resultado)
                if wb and tiene_sheets:
                    try:
                        from utils.sheets import escribir_resultado
                        escribir_resultado(wb, idx - 1, resultado)
                    except Exception as e:
                        logs.append(f"  ⚠ Error Sheets: {e}")
                estado = resultado.get("estado", "Sin estado")
                error = resultado.get("error", "")
                icono = "✓" if not error else "✗"
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {icono} {resultado.get('cedula','')} — {estado or error[:50]}")
            pct = idx / total if total > 0 else 0
            progreso_bar.progress(pct, text=f"Procesando {idx} de {total}...")
            log_placeholder.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
            if resultados:
                df_p = pd.DataFrame(resultados)
                cols = [c for c in ["cedula", "nombre", "estado", "departamento", "municipio", "nombre_proyecto", "error"] if c in df_p.columns]
                tabla_placeholder.dataframe(df_p[cols], use_container_width=True, hide_index=True)

        try:
            from utils.bot import ejecutar_bot_sync
            resultados_finales = ejecutar_bot_sync(cedulas, config, callback)
            st.session_state["bot_resultados"] = resultados_finales
            st.session_state["bot_corriendo"] = False
            guardar_resultados(resultados_finales)
            progreso_bar.progress(1.0, text="✅ Bot finalizado")
            marcadas = sum(1 for r in resultados_finales if "MARCADO" in r.get("estado", "").upper())
            asignadas = sum(1 for r in resultados_finales if "ASIGNADO" in r.get("estado", "").upper())
            errores = sum(1 for r in resultados_finales if r.get("error"))
            st.success(f"Completado: {len(resultados_finales)} cédulas — {marcadas} marcadas para pago — {asignadas} asignadas — {errores} errores")
        except Exception as e:
            st.session_state["bot_corriendo"] = False
            st.error(f"Error crítico: {e}")

    if st.session_state.get("bot_resultados"):
        st.markdown("---")
        st.markdown("### Resultados")
        df_res = pd.DataFrame(st.session_state["bot_resultados"])
        cols = [c for c in ["cedula", "nombre", "estado", "departamento", "municipio", "nombre_proyecto", "tipo_vivienda", "error", "timestamp"] if c in df_res.columns]
        st.dataframe(df_res[cols], use_container_width=True, hide_index=True)
        import io
        buf = io.BytesIO()
        df_res.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button(
            "⬇ Descargar Excel",
            data=buf.read(),
            file_name=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
