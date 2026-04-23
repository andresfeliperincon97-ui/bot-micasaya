"""
utils/bot.py
- Fase 1: Consulta Mi Casa Ya usando HTTP requests (sin Selenium)
- Fase 2: Marca cobros en TransUnion usando Selenium + Chrome
"""

import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime

BASE_URL = "https://subsidiosfonvivienda.minvivienda.gov.co/MiCasaYa"

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

        html_data = json_resp.get("loadHtml", [])
        if not html_data:
            resultado["error"] = "Sin datos en la respuesta"
            return resultado

        html_content = html_data[0].get("data", "")
        soup = BeautifulSoup(html_content, "html.parser")

        estado_span = soup.find("span", class_="text-important")
        if estado_span:
            resultado["estado"] = estado_span.text.strip().upper()

        tablas = soup.find_all("table")
        for tabla in tablas:
            headers_tabla = [th.text.strip() for th in tabla.find_all("th")]
            filas = tabla.find_all("tr")

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
        continuar = callback(0, len(cedulas), None, "Iniciando sesión en Mi Casa Ya...")
        if continuar is False:
            return resultados

    try:
        session, token = obtener_token_y_sesion()
    except Exception as e:
        if callback:
            callback(0, len(cedulas), None, f"Error al conectar: {e}")
        return resultados

    if callback:
        continuar = callback(0, len(cedulas), None, f"Sesión iniciada. Procesando {len(cedulas)} cédulas...")
        if continuar is False:
            return resultados

    token_refresh_cada = 20

    for idx, cedula in enumerate(cedulas):
        cedula = str(cedula).strip()
        if not cedula or len(cedula) < 5:
            continue

        if idx > 0 and idx % token_refresh_cada == 0:
            try:
                session, token = obtener_token_y_sesion()
            except Exception:
                pass

        if callback:
            continuar = callback(idx, len(cedulas), None, f"Consultando cédula {cedula}...")
            if continuar is False:
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
            continuar = callback(idx + 1, len(cedulas), resultado, "")
            if continuar is False:
                break

        time.sleep(delay)

    return resultados


# ─── FASE 2: Selenium + Chrome ────────────────────────────────────────────────

def crear_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--disable-extensions")

    # Railway: Chrome instalado en /usr/bin/google-chrome
    if os.path.exists("/usr/bin/google-chrome"):
        opts.binary_location = "/usr/bin/google-chrome"
        try:
            service = Service("/usr/bin/chromedriver")
            return webdriver.Chrome(service=service, options=opts)
        except Exception:
            pass

    # Local: usar webdriver-manager
    from webdriver_manager.chrome import ChromeDriverManager
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def esperar_opciones_select(driver, index, min_opts=2, timeout=15):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    for _ in range(timeout):
        try:
            sels = driver.find_elements(By.TAG_NAME, "select")
            if len(sels) > index and len(Select(sels[index]).options) >= min_opts:
                return True
        except:
            pass
        time.sleep(1)
    return False

def buscar_proyecto_en_select(select_obj, nombre_proyecto):
    partes = [p.strip() for p in nombre_proyecto.upper().split(" - ") if len(p.strip()) > 3]
    for opcion in select_obj.options:
        texto = opcion.text.upper()
        if len(partes) >= 2:
            if all(p in texto for p in partes):
                return opcion.text
        elif partes and partes[0] in texto:
            return opcion.text
    return None

def login_transunion(driver, usuario, password):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        driver.get("https://miportafolio.transunion.co/nidp/idff/sso?id=MiPortafolioContract&sid=0&option=credential&sid=0")
        wait = WebDriverWait(driver, 20)
        campo = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[placeholder='Usuario']")))
        campo.send_keys(usuario)
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(password)
        try:
            driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
        except:
            driver.find_element(By.XPATH, "//button[contains(text(),'Iniciar')]").click()
        time.sleep(4)
        return "credential" not in driver.current_url and "login" not in driver.current_url
    except Exception:
        return False

def ir_a_realizar_cobro(driver):
    from selenium.webdriver.common.by import By
    driver.get("https://miportafolio.transunion.co/cifin/welcome")
    time.sleep(3)
    try:
        driver.find_element(By.LINK_TEXT, "MI CASA YA").click()
        time.sleep(2)
    except:
        try:
            driver.find_element(By.PARTIAL_LINK_TEXT, "MI CASA").click()
            time.sleep(2)
        except:
            pass
    try:
        driver.find_element(By.PARTIAL_LINK_TEXT, "Realizar el Cobro").click()
        time.sleep(3)
    except:
        try:
            driver.find_element(By.PARTIAL_LINK_TEXT, "Realizar").click()
            time.sleep(3)
        except:
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
            sels = driver.find_elements(By.TAG_NAME, "select")
            for s in sels:
                try:
                    sel_obj = Select(s)
                    textos = [o.text.upper() for o in sel_obj.options]
                    if any("CEDULA" in t for t in textos):
                        sel_obj.select_by_index(1)
                        break
                except:
                    continue
            time.sleep(0.5)
            for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text']:not([readonly]):not([disabled])"):
                try:
                    if inp.is_displayed() and inp.is_enabled():
                        val = inp.get_attribute("value") or ""
                        if val == "" or val.isdigit():
                            inp.clear()
                            inp.send_keys(ced_m)
                            break
                except:
                    continue
            time.sleep(0.5)
            try:
                driver.find_element(By.XPATH, "//input[@value='Adicionar'] | //button[contains(text(),'Adicionar')]").click()
            except:
                try:
                    driver.find_element(By.XPATH, "//*[contains(@value,'Adicionar') or contains(text(),'Adicionar')]").click()
                except:
                    pass
            time.sleep(2)

        try:
            driver.find_element(By.XPATH, "//input[@value='MARCAR PARA PAGO'] | //button[contains(text(),'MARCAR PARA PAGO')]").click()
        except:
            driver.find_element(By.XPATH, "//*[contains(@value,'MARCAR') or contains(text(),'MARCAR')]").click()
        time.sleep(4)

        contenido = driver.page_source
        if "Cobro aplicado" in contenido:
            if "ya fue cobrado" in contenido.lower() or "no se encuentra" in contenido.lower():
                resultado_cobro["mensaje_cobro"] = "Ya cobrado o no aplica"
            else:
                resultado_cobro["cobro_aplicado"] = True
                resultado_cobro["mensaje_cobro"] = "Marcado exitosamente"

        try:
            driver.find_element(By.XPATH, "//input[@value='Nuevo'] | //button[contains(text(),'Nuevo')]").click()
            time.sleep(1)
        except:
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
        callback(0, len(marcadas), None, "Iniciando Chrome para TransUnion...")

    try:
        driver = crear_driver()
    except Exception as e:
        if callback:
            callback(0, len(marcadas), None, f"ERROR al iniciar Chrome: {e}")
        return resultados

    try:
        if callback:
            callback(0, len(marcadas), None, "Iniciando sesión en TransUnion...")
        sesion_ok = login_transunion(driver, usuario, password)
        if not sesion_ok:
            if callback:
                callback(0, len(marcadas), None, "ERROR: No se pudo iniciar sesión en TransUnion")
            return resultados

        if callback:
            callback(0, len(marcadas), None, f"Sesión iniciada. Procesando {len(marcadas)} cédulas...")

        for idx, datos in enumerate(marcadas):
            if callback:
                continuar = callback(idx, len(marcadas), None, f"Marcando cobro: {datos['cedula']}...")
                if continuar is False:
                    break

            cobro = marcar_cobro(driver, datos)
            datos.update(cobro)
            datos["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resultados.append(datos)

            if callback:
                continuar = callback(idx + 1, len(marcadas), datos, "")
                if continuar is False:
                    break

            time.sleep(delay)

    finally:
        try:
            driver.quit()
        except:
            pass

    return resultados
