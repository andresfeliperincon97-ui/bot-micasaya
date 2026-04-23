from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import json, os, time
from datetime import datetime

CONFIG_FILE = "config.json"

def crear_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def esperar_opciones_select(driver, index, min_opts=2, timeout=15):
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

def consultar_estado_hogar(driver, cedula):
    resultado = {
        "cedula": cedula, "estado": "", "miembros": [],
        "departamento": "", "municipio": "", "nombre_proyecto": "",
        "tipo_vivienda": "", "constructor": "", "cobro_aplicado": None,
        "mensaje_cobro": "", "error": "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        driver.get("https://subsidiosfonvivienda.minvivienda.gov.co/micasaya/")
        wait = WebDriverWait(driver, 20)
        time.sleep(2)
        campo = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='number'], input[type='text']")))
        campo.clear()
        campo.send_keys(cedula)
        driver.find_element(By.XPATH, "//button[contains(text(),'Consultar')]").click()
        time.sleep(3)
        contenido = driver.page_source
        for estado in ["MARCADO PARA PAGO", "PAGADO", "ASIGNADO", "POSTULADO", "RECHAZADO", "NO ELEGIBLE"]:
            if estado in contenido:
                resultado["estado"] = estado
                break
        for tabla in driver.find_elements(By.TAG_NAME, "table"):
            try:
                texto = tabla.text
                if "Documento de identificaci" in texto or "Nombres y apellidos" in texto:
                    for fila in tabla.find_elements(By.CSS_SELECTOR, "tbody tr"):
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) >= 4:
                            ced_m = celdas[2].text.strip()
                            if ced_m.replace(" ","").isdigit() and len(ced_m) >= 5:
                                resultado["miembros"].append({"cedula_miembro": ced_m, "nombre": celdas[3].text.strip(), "tipo_doc": "CEDULA"})
                if "Municipio" in texto or "Departamento" in texto or "Depatamento" in texto:
                    filas_p = tabla.find_elements(By.CSS_SELECTOR, "tbody tr")
                    if filas_p:
                        cp = filas_p[0].find_elements(By.TAG_NAME, "td")
                        if len(cp) >= 1: resultado["departamento"] = cp[0].text.strip()
                        if len(cp) >= 2: resultado["municipio"] = cp[1].text.strip()
                        if len(cp) >= 3: resultado["constructor"] = cp[2].text.strip()
                        if len(cp) >= 4: resultado["nombre_proyecto"] = cp[3].text.strip()
                        if len(cp) >= 6: resultado["tipo_vivienda"] = cp[5].text.strip()
            except:
                continue
        if not resultado["miembros"]:
            resultado["miembros"] = [{"cedula_miembro": cedula, "tipo_doc": "CEDULA"}]
    except Exception as e:
        resultado["error"] = str(e)[:200]
    return resultado

def login_transunion(driver, usuario, password):
    try:
        driver.get("https://miportafolio.transunion.co/nidp/idff/sso?id=MiPortafolioContract&sid=0&option=credential&sid=0&target=https%3A%2F%2Fmiportafolio.transunion.co%2Fsso-auth-server%2Flogin")
        wait = WebDriverWait(driver, 20)
        campo = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[placeholder='Usuario']")))
        campo.send_keys(usuario)
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(password)
        try:
            driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
        except:
            driver.find_element(By.XPATH, "//button[contains(text(),'Iniciar')]").click()
        time.sleep(4)
        if "credential" in driver.current_url or "login" in driver.current_url:
            try:
                c = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[placeholder='Usuario']")
                c.clear()
                c.send_keys(usuario)
                driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(password)
                try:
                    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                except:
                    driver.find_element(By.XPATH, "//button[contains(text(),'Iniciar')]").click()
                time.sleep(4)
            except:
                pass
        return "cifin" in driver.current_url or "welcome" in driver.current_url or "MiCasaYa" in driver.current_url
    except:
        return False

def ir_a_realizar_cobro(driver):
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
    resultado_cobro = {"cobro_aplicado": False, "mensaje_cobro": "", "error_cobro": ""}
    try:
        ir_a_realizar_cobro(driver)
        depto = datos.get("departamento","").upper().strip()
        muni = datos.get("municipio","").upper().strip()
        nombre_proyecto = datos.get("nombre_proyecto","").upper().strip()

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

        miembros = datos.get("miembros", [{"cedula_miembro": datos.get("cedula",""), "tipo_doc": "CEDULA"}])
        for miembro in miembros:
            ced_m = miembro.get("cedula_miembro","").strip()
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

def ejecutar_bot_sync(cedulas, config, callback=None):
    resultados = []
    headless = not config.get("mostrar_navegador", False)
    solo_fase1 = config.get("solo_fase1", True)
    delay = config.get("delay", 3)
    reintentos = config.get("reintentos", 2)
    usuario = config.get("usuario","")
    password = config.get("password","")
    driver = crear_driver(headless=headless)
    driver2 = None
    sesion_ok = False
    try:
        for idx, cedula in enumerate(cedulas):
            cedula = str(cedula).strip()
            if not cedula or len(cedula) < 5:
                continue
            if callback:
                callback(idx, len(cedulas), None, f"Consultando cedula {cedula}...")
            resultado = None
            for _ in range(reintentos):
                resultado = consultar_estado_hogar(driver, cedula)
                if not resultado.get("error"):
                    break
                time.sleep(2)
            if not solo_fase1 and resultado.get("estado","").upper() == "MARCADO PARA PAGO":
                if callback:
                    callback(idx, len(cedulas), None, f"Marcando para pago: {cedula}")
                if driver2 is None:
                    driver2 = crear_driver(headless=headless)
                if not sesion_ok:
                    sesion_ok = login_transunion(driver2, usuario, password)
                if sesion_ok:
                    cobro = marcar_cobro(driver2, resultado)
                    resultado.update(cobro)
                else:
                    resultado["error_cobro"] = "No se pudo iniciar sesion"
            resultados.append(resultado)
            if callback:
                callback(idx + 1, len(cedulas), resultado, "")
            time.sleep(delay)
    finally:
        driver.quit()
        if driver2:
            driver2.quit()
    return resultados

def ejecutar_fase2_desde_sheets(marcadas, config, callback=None):
    resultados = []
    headless = not config.get("mostrar_navegador", False)
    usuario = config.get("usuario","")
    password = config.get("password","")
    delay = config.get("delay", 3)
    driver = crear_driver(headless=headless)
    sesion_ok = False
    try:
        sesion_ok = login_transunion(driver, usuario, password)
        if not sesion_ok:
            if callback:
                callback(0, len(marcadas), None, "ERROR: No se pudo iniciar sesion en TransUnion")
            return resultados
        for idx, datos in enumerate(marcadas):
            if callback:
                callback(idx, len(marcadas), None, f"Marcando cobro: {datos['cedula']}...")
            cobro = marcar_cobro(driver, datos)
            datos.update(cobro)
            datos["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resultados.append(datos)
            if callback:
                callback(idx + 1, len(marcadas), datos, "")
            time.sleep(delay)
    finally:
        driver.quit()
    return resultados
