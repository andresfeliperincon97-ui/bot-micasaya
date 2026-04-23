import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

RESULTADOS_FILE = "resultados.json"

def mostrar():
    st.markdown("## 📊 Historial de Ejecuciones")

    if not os.path.exists(RESULTADOS_FILE):
        st.info("Aún no hay ejecuciones registradas. Ejecuta el bot para ver el historial aquí.")
        return

    with open(RESULTADOS_FILE, "r") as f:
        todos = json.load(f)

    if not todos:
        st.info("El historial está vacío.")
        return

    df = pd.DataFrame(todos)

    # Métricas globales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-number">{len(df)}</div>
            <div class="metric-label">Total procesadas</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        cobros = df["cobro_aplicado"].sum() if "cobro_aplicado" in df.columns else 0
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-number">{int(cobros)}</div>
            <div class="metric-label">Cobros exitosos</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        pagados = (df["estado"] == "PAGADO").sum() if "estado" in df.columns else 0
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-number">{int(pagados)}</div>
            <div class="metric-label">Estado PAGADO</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        errores = df["error"].astype(str).str.len().gt(0).sum() if "error" in df.columns else 0
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-number">{int(errores)}</div>
            <div class="metric-label">Con errores</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Distribución de estados
    if "estado" in df.columns:
        st.markdown("### Distribución de estados")
        estados = df["estado"].value_counts().reset_index()
        estados.columns = ["Estado", "Cantidad"]
        st.dataframe(estados, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Tabla completa con filtros
    st.markdown("### Registros completos")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        if "estado" in df.columns:
            filtro = st.selectbox("Filtrar por estado", ["Todos"] + df["estado"].dropna().unique().tolist())
            if filtro != "Todos":
                df = df[df["estado"] == filtro]
    with col_f2:
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            fechas = df["timestamp"].dt.date.dropna().unique()
            if len(fechas) > 1:
                fecha_sel = st.selectbox("Filtrar por fecha", ["Todas"] + sorted([str(f) for f in fechas], reverse=True))
                if fecha_sel != "Todas":
                    df = df[df["timestamp"].dt.date.astype(str) == fecha_sel]

    columnas_mostrar = [c for c in [
        "cedula", "estado", "departamento", "municipio", "nombre_proyecto",
        "cobro_aplicado", "mensaje_cobro", "error", "timestamp"
    ] if c in df.columns]

    st.dataframe(df[columnas_mostrar], use_container_width=True, hide_index=True)

    # Descarga del historial completo
    import io
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        "⬇️ Descargar historial completo en Excel",
        data=buf.read(),
        file_name=f"historial_micasaya_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("---")
    if st.button("🗑️ Limpiar historial completo", type="secondary"):
        if st.checkbox("Confirmo que quiero borrar todo el historial"):
            os.remove(RESULTADOS_FILE)
            st.success("Historial eliminado")
            st.rerun()
