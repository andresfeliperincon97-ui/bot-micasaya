import streamlit as st

def mostrar():
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="metric-box">
            <div class="metric-number">2</div>
            <div class="metric-label">Plataformas automatizadas</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="metric-box">
            <div class="metric-number">100%</div>
            <div class="metric-label">Proceso automatizado</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="metric-box">
            <div class="metric-number">~3 min</div>
            <div class="metric-label">Ahorrado por cédula</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Como funciona el bot")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
        #### Fase 1 — Consulta de Estado
        **Plataforma:** subsidiosfonvivienda.minvivienda.gov.co

        1. Ingresa la cedula en el formulario
        2. Extrae el **estado del hogar**
        3. Captura los **datos del proyecto**
        4. Registra todos los **miembros del hogar** (1 o 2)
        5. Guarda todo en el reporte

        Si el estado es **"MARCADO PARA PAGO"** activa Fase 2 automaticamente.
        """)

    with col_b:
        st.markdown("""
        #### Fase 2 — Marcar para Pago
        **Plataforma:** miportafolio.transunion.co

        1. Inicia sesion con credenciales del area
        2. Navega a Mi Casa Ya > Realizar Cobro
        3. Selecciona Departamento > Municipio > Proyecto
        4. Agrega cada cedula del hogar una por una
        5. Hace clic en MARCAR PARA PAGO
        6. Registra el resultado
        7. Hace clic en Nuevo para el siguiente caso
        """)

    st.markdown("---")
    st.markdown("### Estados posibles")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="status-card status-marcado"><strong>MARCADO PARA PAGO</strong><br><small>Activa Fase 2</small></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="status-card status-pagado"><strong>PAGADO</strong><br><small>Solo registra estado</small></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="status-card status-otro"><strong>OTRO ESTADO</strong><br><small>Registra el estado encontrado</small></div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="status-card status-error"><strong>ERROR</strong><br><small>Registra para revision manual</small></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Ve a Configuracion para ingresar credenciales y cargar el archivo con cedulas antes de ejecutar.")
