import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from utils.bot import ejecutar_bot_sync, ejecutar_fase2_desde_sheets

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
            datos = json.load(f)
    datos.extend(resultados)
    with open(RESULTADOS_FILE, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def obtener_cedulas(config):
    if config.get("usar_sheets"):
        from utils.sheets import conectar_sheets, leer_cedulas
        wb = conectar_sheets(config["google_creds"], config["sheet_id"])
        st.session_state["_workbook"] = wb
        return leer_cedulas(wb)
    elif "df_cedulas" in st.session_state:
        return st.session_state["df_cedulas"].to_dict("records")
    return []

def mostrar():
    st.markdown("## Ejecutar Bot")
    config = cargar_config()

    alertas = []
    if not config.get("usuario") or not config.get("password"):
        alertas.append("Credenciales TransUnion no configuradas")
    if not config.get("usar_sheets") and "df_cedulas" not in st.session_state:
        alertas.append("No hay cedulas cargadas - conecta Sheets o carga un Excel")

    if alertas:
        for a in alertas:
            st.error(f"Pendiente: {a}")
        return

    if "bot_corriendo" not in st.session_state:
        st.session_state["bot_corriendo"] = False
    if "bot_resultados" not in st.session_state:
        st.session_state["bot_resultados"] = []

    # Tabs de modo
    modo_tab = st.radio("Modo de ejecucion", ["Fase 1 — Consultar estados", "Fase 1 + 2 — Consultar y marcar cobros", "Solo Fase 2 — Marcar cobros pendientes desde Sheets"], horizontal=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if modo_tab in ["Fase 1 — Consultar estados", "Fase 1 + 2 — Consultar y marcar cobros"]:
        try:
            registros = obtener_cedulas(config)
            cedulas = [r["cedula"] for r in registros]
            nombres = {r["cedula"]: r.get("nombre","") for r in registros}
        except Exception as e:
            st.error(f"Error al cargar cedulas: {e}")
            return

        fuente = "Google Sheets" if config.get("usar_sheets") else "Excel local"
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="metric-box"><div class="metric-number">{len(cedulas)}</div><div class="metric-label">Cedulas ({fuente})</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-box"><div class="metric-number" style="font-size:1rem">{modo_tab.split(" — ")[0]}</div><div class="metric-label">Modo activo</div></div>', unsafe_allow_html=True)
        with col3:
            mins = len(cedulas) * (config.get("delay",3) + 8) // 60
            st.markdown(f'<div class="metric-box"><div class="metric-number">~{mins} min</div><div class="metric-label">Tiempo estimado</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        iniciar = st.button("Iniciar Bot", disabled=st.session_state["bot_corriendo"], use_container_width=True)

        if iniciar:
            st.session_state["bot_corriendo"] = True
            st.session_state["bot_resultados"] = []
            config["solo_fase1"] = (modo_tab == "Fase 1 — Consultar estados")

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
                    resultado["nombre"] = nombres.get(resultado.get("cedula",""),"")
                    resultados.append(resultado)
                    if wb and config.get("usar_sheets"):
                        try:
                            from utils.sheets import escribir_resultado
                            escribir_resultado(wb, idx, resultado)
                        except Exception as e:
                            logs.append(f"Error Sheets: {e}")
                    estado = resultado.get("estado","Sin estado")
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {resultado.get('cedula','')} - {estado}")
                pct = idx / total if total > 0 else 0
                progreso_bar.progress(pct, text=f"Procesando {idx} de {total}...")
                log_placeholder.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
                if resultados:
                    df_p = pd.DataFrame(resultados)
                    cols = [c for c in ["cedula","nombre","estado","departamento","municipio","nombre_proyecto","error"] if c in df_p.columns]
                    tabla_placeholder.dataframe(df_p[cols], use_container_width=True, hide_index=True)

            try:
                resultados_finales = ejecutar_bot_sync(cedulas, config, callback)
                st.session_state["bot_resultados"] = resultados_finales
                st.session_state["bot_corriendo"] = False
                guardar_resultados(resultados_finales)
                progreso_bar.progress(1.0, text="Bot finalizado")
                marcadas = sum(1 for r in resultados_finales if r.get("estado","").upper() == "MARCADO PARA PAGO")
                st.success(f"Completado: {len(resultados_finales)} cedulas — {marcadas} marcadas para pago")
            except Exception as e:
                st.session_state["bot_corriendo"] = False
                st.error(f"Error critico: {e}")

    else:
        # SOLO FASE 2
        if not config.get("usar_sheets"):
            st.error("Esta opcion requiere Google Sheets conectado")
            return

        try:
            from utils.sheets import conectar_sheets, leer_marcadas_para_pago
            wb = conectar_sheets(config["google_creds"], config["sheet_id"])
            st.session_state["_workbook"] = wb
            marcadas = leer_marcadas_para_pago(wb)
        except Exception as e:
            st.error(f"Error al leer Sheets: {e}")
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="metric-box"><div class="metric-number">{len(marcadas)}</div><div class="metric-label">Pendientes de cobro</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-box"><div class="metric-number" style="font-size:1rem">Solo Fase 2</div><div class="metric-label">Modo activo</div></div>', unsafe_allow_html=True)
        with col3:
            mins = len(marcadas) * (config.get("delay",3) + 15) // 60
            st.markdown(f'<div class="metric-box"><div class="metric-number">~{mins} min</div><div class="metric-label">Tiempo estimado</div></div>', unsafe_allow_html=True)

        if not marcadas:
            st.info("No hay cedulas pendientes de cobro en la hoja Resultados.")
            return

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Cedulas a marcar para pago:**")
        df_marc = pd.DataFrame(marcadas)[["cedula","nombre","departamento","municipio","nombre_proyecto"]]
        st.dataframe(df_marc, use_container_width=True, hide_index=True)

        iniciar2 = st.button("Ejecutar Fase 2 — Marcar cobros", disabled=st.session_state["bot_corriendo"], use_container_width=True)

        if iniciar2:
            st.session_state["bot_corriendo"] = True
            progreso_bar = st.progress(0, text="Iniciando sesion en TransUnion...")
            log_placeholder = st.empty()
            logs = []
            wb = st.session_state.get("_workbook")

            def callback2(idx, total, resultado, mensaje):
                if mensaje:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}")
                if resultado:
                    cobro = resultado.get("cobro_aplicado", False)
                    estado_cobro = "OK" if cobro else "NO"
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {resultado.get('cedula','')} - Cobro: {estado_cobro}")
                    if wb:
                        try:
                            from utils.sheets import actualizar_cobro_fila
                            actualizar_cobro_fila(wb, resultado["fila_sheets"], cobro, resultado.get("mensaje_cobro",""), resultado.get("timestamp",""))
                        except Exception as e:
                            logs.append(f"Error Sheets: {e}")
                pct = idx / total if total > 0 else 0
                progreso_bar.progress(pct, text=f"Procesando {idx} de {total}...")
                log_placeholder.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)

            try:
                resultados_f2 = ejecutar_fase2_desde_sheets(marcadas, config, callback2)
                st.session_state["bot_corriendo"] = False
                progreso_bar.progress(1.0, text="Fase 2 completada")
                exitosos = sum(1 for r in resultados_f2 if r.get("cobro_aplicado"))
                st.success(f"Completado: {len(resultados_f2)} procesadas — {exitosos} cobros exitosos")
            except Exception as e:
                st.session_state["bot_corriendo"] = False
                st.error(f"Error critico: {e}")

    if st.session_state["bot_resultados"] and modo_tab != "Solo Fase 2 — Marcar cobros pendientes desde Sheets":
        st.markdown("---")
        df_res = pd.DataFrame(st.session_state["bot_resultados"])
        cols = [c for c in ["cedula","nombre","estado","departamento","municipio","nombre_proyecto","cobro_aplicado","error","timestamp"] if c in df_res.columns]
        st.dataframe(df_res[cols], use_container_width=True, hide_index=True)
        import io
        buf = io.BytesIO()
        df_res.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button("Descargar Excel", data=buf.read(), file_name=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
