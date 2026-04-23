"""
utils/bot.py
- Fase 1: Consulta Mi Casa Ya usando HTTP requests (sin Selenium)
- Fase 2: Login via HTTP requests + Selenium para marcar cobros en TransUnion
"""

import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime

BASE_URL = "https://subsidiosfonvivienda.minvivienda.gov.co/MiCasaYa"
TRANSUNION_BASE = "https://miportafolio.transunion.co"

# ─── FASE 1: HTTP requests ────────────────────────────────────────────────────

def obtener_token_y_sesion():
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
        token_meta = soup.find("meta", {"name": "RequestVerificationToken"})
        if token_meta:
            return session, token_meta.get("content", "")
        raise Exception("No se encontró el token de verificación en la página")
    return session, token_input.get("value", "")

def consultar_cedula(session, token, cedula, tipo_doc=1):
    resultado = {
        "cedula": cedula, "estado": "", "miembros": [],
        "departamento": "", "municipio": "", "nombre_proyecto": "",
        "tipo_vivienda": "", "constructor": "", "cobro_aplicado": None,
        "mensaje_cobro": "", "error": "",
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
        resp = session.post(f"{BASE_URL}/consulta/consultarhogar", data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        json_resp = resp.json()

        if json_resp.get("error"):
            resultado["error"] = json_resp.get("msg", "Error del servidor")
            return resultado

        html_data = json_resp.get("loadHtml", [])
        if not html_data:
            resultado["error"] = "Sin datos en la respuesta"
            return resultado

        soup = BeautifulSoup(html_data[0].get("data", ""), "html.parser")
        estado_span = soup.find("span", class_="text-important")
        if estado_span:
            resultado["estado"] = estado_span.text.strip().upper()

        for tabla in soup.find_all("table"):
            headers_tabla = [th.text.strip() for th in tabla.find_all("th")]
            filas = tabla.find_all("tr")
            if any("Documento de identificación" in h for h in headers_tabla):
                for fila in filas[1:]:
                    celdas = fila.find_all("td")
                    if len(celdas) >= 3:
                        ced_m = celdas[2].text.strip().replace(" ", "")
                        if ced_m.isdigit() and len(ced_m) >= 5:
                            resultado["miembros"].append({"cedula_miembro": ced_m, "nombre": celdas[3].text.strip() if len(celdas) > 3 else "", "tipo_doc": "CEDULA"})
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
    resultados = []
    delay = config.get("delay", 2)
    reintentos = config.get("reintentos", 2)

    if callback:
        if callback(0, len(cedulas), None, "Iniciando sesión en Mi Casa Ya...") is False:
            return resultados
    try:
        session, token = obtener_token_y_sesion()
    except Exception as e:
        if callback: callback(0, len(cedulas), None, f"Error al conectar: {e}")
        return resultados

    if callback:
        if callback(0, len(cedulas), None, f"Sesión iniciada. Procesando {len(cedulas)} cédulas...") is False:
            return resultados

    for idx, cedula in enumerate(cedulas):
        cedula = str(cedula).strip()
        if not cedula or len(cedula) < 5:
            continue
        if idx > 0 and idx % 20 == 0:
            try:
                session, token = obtener_token_y_sesion()
            except Exception:
                pass
        if callback:
            if callback(idx, len(cedulas), None, f"Consultando cédula {cedula}...") is False:
                break
        resultado = None
        for intento in range(reintentos):
            resultado = consultar_cedula(session, token, cedula)
            if not resultado.get("error"):
                break
            if intento < reintentos - 1:
                time.sleep(2)
                try:
                    session, token = obtener_token_y_sesion()
                except Exception:
                    pass
        resultados.append(resultado)
        if callback:
            if callback(idx + 1, len(cedulas), resultado, "") is False:
                break
        time.sleep(delay)
    return resultados


# ─── FASE 2: Login HTTP + Selenium ───────────────────────────────────────────

def login_transunion_http(usuario, password):
    """Hace login en TransUnion via HTTP y retorna las cookies de sesión."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # 1. Obtener página de login y CSRF token
    login_page_url = f"{TRANSUNION_BASE}/nidp/idff/sso?id=MiPortafolioContract&sid=0&option=credential&sid=0&target=https%3A%2F%2Fmiportafolio.transunion.co%2Fcifin"
    resp = session.get(login_page_url, timeout=30, allow_redirects=True)

    # 2. Obtener XSRF-TOKEN de las cookies
    xsrf_token = session.cookies.get("XSRF-TOKEN", "")

    # 3. POST al endpoint de login
    login_url = f"{TRANSUNION_BASE}/sso-auth-server/login"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": login_page_url,
        "X-XSRF-TOKEN": xsrf_token,
    }
    data = {
        "username": usuario,
        "password": password,
        "_csrf": xsrf_token,
    }
    resp = session.post(login_url, data=data, headers=headers, timeout=30, allow_redirects=True)

    # Verificar si llegamos al welcome
    if "cifin/welcome" in resp.url or "cifin" in resp.url:
        return session.cookies.get_dict()
    return None

def crear_driver_con_cookies(cookies_dict):
    """Crea un driver de Selenium y le inyecta las cookies de sesión."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")

    if os.path.exists("/usr/bin/google-chrome"):
        opts.binary_location = "/usr/bin/google-chrome"
        try:
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=opts)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    # Navegar al dominio primero, luego inyectar cookies
    driver.get(f"{TRANSUNION_BASE}/cifin/welcome")
    for name, value in cookies_dict.items():
        try:
            driver.add_cookie({"name": name, "value": value, "domain": "miportafolio.transunion.co"})
        except Exception:
            pass
    driver.refresh()
    time.sleep(2)
    return driver

def esperar_opciones_select(driver, index, min_opts=2, timeout=15):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    for _ in range(timeout):
        try:
            sels = driver.find_elements(By.TAG_NAME, "select")
            if len(sels) > index and len(Select(sels[index]).options) >= min_opts:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def buscar_proyecto_en_select(select_obj, nombre_proyecto):
    partes = [p.strip() for p in nombre_proyecto.upper().split(" - ") if len(p.strip()) > 3]
    for opcion in select_obj.options:
        texto = opcion.text.upper()
        if len(partes) >= 2 and all(p in texto for p in partes):
            return opcion.text
        elif partes and partes[0] in texto:
            return opcion.text
    return None

def ir_a_realizar_cobro(driver):
    from selenium.webdriver.common.by import By
    driver.get(f"{TRANSUNION_BASE}/cifin/welcome")
    time.sleep(3)
    for texto in ["MI CASA YA", "MI CASA"]:
        try:
            driver.find_element(By.PARTIAL_LINK_TEXT, texto).click()
            time.sleep(2)
            break
        except Exception:
            pass
    for texto in ["Realizar el Cobro", "Realizar"]:
        try:
            driver.find_element(By.PARTIAL_LINK_TEXT, texto).click()
            time.sleep(3)
            break
        except Exception:
            pass

def marcar_cobro(driver, datos):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select

    resultado_cobro = {"cobro_aplicado": False, "mensaje_cobro": "", "error_cobro": ""}
    try:
        ir_a_realizar_cobro(driver)
        depto = datos.get("departamento", "").upper().strip()
        muni = datos.get("municipio", "").upper().strip()
        nombre_proyecto = datos.get("nombre_proyecto", "").upper().strip()

        esperar_opciones_select(driver, 0)
        sels = driver.find_elements(By.TAG_NAME, "select")
        Select(sels[0]).select_by_visible_text(depto)
        time.sleep(1)

        esperar_opciones_select(driver, 1)
        time.sleep(2)
        sels = driver.find_elements(By.TAG_NAME, "select")
        Select(sels[1]).select_by_visible_text(muni)
        time.sleep(1)

        esperar_opciones_select(driver, 2)
        time.sleep(2)
        sels = driver.find_elements(By.TAG_NAME, "select")
        sel_proy = Select(sels[2])
        opcion = buscar_proyecto_en_select(sel_proy, nombre_proyecto)
        if opcion:
            sel_proy.select_by_visible_text(opcion)
        elif len(sel_proy.options) > 1:
            sel_proy.select_by_index(1)
        time.sleep(2)

        miembros = datos.get("miembros", [{"cedula_miembro": datos.get("cedula", ""), "tipo_doc": "CEDULA"}])
        for miembro in miembros:
            ced_m = miembro.get("cedula_miembro", "").strip()
            if not ced_m:
                continue
            for s in driver.find_elements(By.TAG_NAME, "select"):
                try:
                    sel_obj = Select(s)
                    if any("CEDULA" in o.text.upper() for o in sel_obj.options):
                        sel_obj.select_by_index(1)
                        break
                except Exception:
                    pass
            time.sleep(0.5)
            for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text']:not([readonly]):not([disabled])"):
                try:
                    if inp.is_displayed() and inp.is_enabled():
                        val = inp.get_attribute("value") or ""
                        if val == "" or val.isdigit():
                            inp.clear()
                            inp.send_keys(ced_m)
                            break
                except Exception:
                    pass
            time.sleep(0.5)
            try:
                driver.find_element(By.XPATH, "//*[contains(@value,'Adicionar') or contains(text(),'Adicionar')]").click()
            except Exception:
                pass
            time.sleep(2)

        try:
            driver.find_element(By.XPATH, "//*[contains(@value,'MARCAR') or contains(text(),'MARCAR')]").click()
        except Exception:
            pass
        time.sleep(4)

        contenido = driver.page_source
        if "Cobro aplicado" in contenido:
            if "ya fue cobrado" in contenido.lower() or "no se encuentra" in contenido.lower():
                resultado_cobro["mensaje_cobro"] = "Ya cobrado o no aplica"
            else:
                resultado_cobro["cobro_aplicado"] = True
                resultado_cobro["mensaje_cobro"] = "Marcado exitosamente"

        try:
            driver.find_element(By.XPATH, "//*[contains(@value,'Nuevo') or contains(text(),'Nuevo')]").click()
            time.sleep(1)
        except Exception:
            pass

    except Exception as e:
        resultado_cobro["error_cobro"] = str(e)[:200]
    return resultado_cobro

def ejecutar_fase2_desde_sheets(marcadas, config, callback=None):
    resultados = []
    usuario = config.get("usuario") or os.environ.get("TRANSUNION_USUARIO", "")
    password = config.get("password") or os.environ.get("TRANSUNION_PASSWORD", "")
    delay = config.get("delay", 3)

    if not usuario or not password:
        if callback:
            callback(0, len(marcadas), None, "ERROR: No hay credenciales de TransUnion configuradas")
        return resultados

    if callback:
        callback(0, len(marcadas), None, "Iniciando sesión en TransUnion via HTTP...")

    # Login via HTTP para obtener cookies
    cookies = login_transunion_http(usuario, password)
    if not cookies:
        if callback:
            callback(0, len(marcadas), None, "ERROR: No se pudo iniciar sesión en TransUnion")
        return resultados

    if callback:
        callback(0, len(marcadas), None, "Sesión iniciada. Iniciando Chrome con sesión activa...")

    # Crear driver con cookies ya inyectadas
    try:
        driver = crear_driver_con_cookies(cookies)
    except Exception as e:
        if callback:
            callback(0, len(marcadas), None, f"ERROR al iniciar Chrome: {e}")
        return resultados

    try:
        if callback:
            callback(0, len(marcadas), None, f"Chrome listo. Procesando {len(marcadas)} cédulas...")

        for idx, datos in enumerate(marcadas):
            if callback:
                if callback(idx, len(marcadas), None, f"Marcando cobro: {datos['cedula']}...") is False:
                    break
            cobro = marcar_cobro(driver, datos)
            datos.update(cobro)
            datos["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resultados.append(datos)
            if callback:
                if callback(idx + 1, len(marcadas), datos, "") is False:
                    break
            time.sleep(delay)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return resultados
