"""
utils/bot.py — Consulta Mi Casa Ya usando HTTP requests (sin Selenium).
Funciona 100% en Streamlit Cloud.
"""

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime

BASE_URL = "https://subsidiosfonvivienda.minvivienda.gov.co/MiCasaYa"

def obtener_token_y_sesion():
    """Obtiene el _RequestVerificationToken y las cookies de sesión."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CO,es;q=0.9",
    })
    resp = session.get(f"{BASE_URL}/", timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if not token_input:
        # Buscar en meta tag
        token_meta = soup.find("meta", {"name": "RequestVerificationToken"})
        if token_meta:
            return session, token_meta.get("content", "")
        raise Exception("No se encontró el token de verificación en la página")
    return session, token_input.get("value", "")

def consultar_cedula(session, token, cedula, tipo_doc=1):
    """Consulta el estado de una cédula en Mi Casa Ya."""
    resultado = {
        "cedula": cedula,
        "estado": "",
        "miembros": [],
        "departamento": "",
        "municipio": "",
        "nombre_proyecto": "",
        "tipo_vivienda": "",
        "constructor": "",
        "cobro_aplicado": None,
        "mensaje_cobro": "",
        "error": "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/",
            "Origin": "https://subsidiosfonvivienda.minvivienda.gov.co",
        }
        data = {
            "tipo_documento": str(tipo_doc),
            "numero_documento": str(cedula).strip(),
            "__RequestVerificationToken": token,
        }
        resp = session.post(
            f"{BASE_URL}/consulta/consultarhogar",
            data=data,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        json_resp = resp.json()

        if json_resp.get("error"):
            resultado["error"] = json_resp.get("msg", "Error del servidor")
            return resultado

        # Parsear el HTML de respuesta
        html_data = json_resp.get("loadHtml", [])
        if not html_data:
            resultado["error"] = "Sin datos en la respuesta"
            return resultado

        html_content = html_data[0].get("data", "")
        soup = BeautifulSoup(html_content, "html.parser")

        # Extraer estado
        estado_span = soup.find("span", class_="text-important")
        if estado_span:
            resultado["estado"] = estado_span.text.strip().upper()

        # Extraer tablas
        tablas = soup.find_all("table")
        for tabla in tablas:
            headers_tabla = [th.text.strip() for th in tabla.find_all("th")]
            filas = tabla.find_all("tr")

            # Tabla de miembros del hogar
            if any("Documento de identificación" in h for h in headers_tabla):
                for fila in filas[1:]:
                    celdas = fila.find_all("td")
                    if len(celdas) >= 3:
                        ced_m = celdas[2].text.strip()
                        nombre_m = celdas[3].text.strip() if len(celdas) > 3 else ""
                        if ced_m.replace(" ", "").isdigit() and len(ced_m.replace(" ", "")) >= 5:
                            resultado["miembros"].append({
                                "cedula_miembro": ced_m.replace(" ", ""),
                                "nombre": nombre_m,
                                "tipo_doc": "CEDULA"
                            })

            # Tabla de proyecto (Departamento, Municipio, etc.)
            if any("Municipio" in h or "Depatramento" in h or "Departamento" in h for h in headers_tabla):
                for fila in filas[1:]:
                    celdas = fila.find_all("td")
                    if len(celdas) >= 4:
                        resultado["departamento"] = celdas[0].text.strip()
                        resultado["municipio"] = celdas[1].text.strip()
                        resultado["constructor"] = celdas[2].text.strip()
                        resultado["nombre_proyecto"] = celdas[3].text.strip()
                        if len(celdas) >= 6:
                            resultado["tipo_vivienda"] = celdas[5].text.strip()

        # Si no se encontraron miembros, usar la cédula consultada
        if not resultado["miembros"]:
            resultado["miembros"] = [{"cedula_miembro": cedula, "tipo_doc": "CEDULA"}]

    except requests.exceptions.Timeout:
        resultado["error"] = "Timeout al consultar"
    except requests.exceptions.ConnectionError:
        resultado["error"] = "Error de conexión"
    except Exception as e:
        resultado["error"] = str(e)[:200]

    return resultado

def ejecutar_bot_sync(cedulas, config, callback=None):
    """Ejecuta la consulta de todas las cédulas usando HTTP (sin Selenium)."""
    resultados = []
    delay = config.get("delay", 2)
    reintentos = config.get("reintentos", 2)

    if callback:
        callback(0, len(cedulas), None, "Iniciando sesión en Mi Casa Ya...")

    # Obtener token y sesión una sola vez
    try:
        session, token = obtener_token_y_sesion()
    except Exception as e:
        if callback:
            callback(0, len(cedulas), None, f"Error al conectar: {e}")
        return resultados

    if callback:
        callback(0, len(cedulas), None, f"Sesión iniciada. Procesando {len(cedulas)} cédulas...")

    token_refresh_cada = 20  # Renovar token cada 20 cédulas

    for idx, cedula in enumerate(cedulas):
        cedula = str(cedula).strip()
        if not cedula or len(cedula) < 5:
            continue

        # Renovar token periódicamente
        if idx > 0 and idx % token_refresh_cada == 0:
            try:
                session, token = obtener_token_y_sesion()
            except Exception:
                pass  # Continuar con el token anterior

        if callback:
            callback(idx, len(cedulas), None, f"Consultando cédula {cedula}...")

        resultado = None
        for intento in range(reintentos):
            resultado = consultar_cedula(session, token, cedula)
            if not resultado.get("error"):
                break
            if intento < reintentos - 1:
                time.sleep(2)
                # Renovar sesión en caso de error
                try:
                    session, token = obtener_token_y_sesion()
                except Exception:
                    pass

        resultados.append(resultado)

        if callback:
            callback(idx + 1, len(cedulas), resultado, "")

        time.sleep(delay)

    return resultados

def ejecutar_fase2_desde_sheets(marcadas, config, callback=None):
    """
    Fase 2 requiere login en TransUnion — no es posible sin Selenium.
    Esta función retorna un aviso claro.
    """
    resultados = []
    if callback:
        callback(0, len(marcadas), None, "⚠ Fase 2 (marcar cobros en TransUnion) requiere ejecución local con Selenium.")
    for datos in marcadas:
        datos["cobro_aplicado"] = False
        datos["mensaje_cobro"] = "Fase 2 no disponible en nube — ejecutar bot_local.py"
        datos["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resultados.append(datos)
    return resultados
