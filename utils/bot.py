"""
utils/bot.py
- Fase 1: Consulta Mi Casa Ya usando HTTP requests (sin navegador)
- Fase 2: Marca cobros en TransUnion usando Playwright
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
                            resultado["miembros"].append({
                                "cedula_miembro": ced_m,
                                "nombre": celdas[3].text.strip() if len(celdas) > 3 else "",
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
        if callback(0, len(cedulas), None, "Iniciando sesión en Mi Casa Ya...") is False:
            return resultados
    try:
        session, token = obtener_token_y_sesion()
    except Exception as e:
        if callback:
            callback(0, len(cedulas), None, f"Error al conectar: {e}")
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


# ─── FASE 2: Playwright ───────────────────────────────────────────────────────

def cerrar_sesion_transunion(page, callback=None):
    """Cierra sesión en TransUnion."""
    try:
        page.goto(f"{TRANSUNION_BASE}/AGLogout", timeout=10000)
        time.sleep(2)
        try:
            page.click("button:has-text('Aceptar')", timeout=3000)
            time.sleep(1)
        except Exception:
            pass
        if callback:
            callback(0, 0, None, "Sesión cerrada en TransUnion ✓")
    except Exception:
        try:
            page.goto(f"{TRANSUNION_BASE}/nidp/app/logout", timeout=10000)
            time.sleep(2)
            if callback:
                callback(0, 0, None, "Sesión cerrada en TransUnion ✓")
        except Exception:
            pass


def ejecutar_fase2_desde_sheets(marcadas, config, callback=None):
    from playwright.sync_api import sync_playwright

    resultados = []
    usuario = config.get("usuario") or os.environ.get("TRANSUNION_USUARIO", "")
    password = config.get("password") or os.environ.get("TRANSUNION_PASSWORD", "")
    delay = config.get("delay", 3)

    if not usuario or not password:
        if callback:
            callback(0, len(marcadas), None, "ERROR: No hay credenciales de TransUnion configuradas")
        return resultados

    if callback:
        callback(0, len(marcadas), None, "Iniciando Playwright para TransUnion...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            if callback:
                callback(0, len(marcadas), None, "Iniciando sesión en TransUnion...")

            login_url = (
                f"{TRANSUNION_BASE}/nidp/idff/sso?id=MiPortafolioContract"
                f"&sid=0&option=credential&sid=0"
                f"&target=https%3A%2F%2Fmiportafolio.transunion.co%2Fcifin"
            )
            page.goto(login_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)

            # Extraer CSRF
            csrf_token = ""
            try:
                csrf_token = page.eval_on_selector("input[name='_csrf']", "el => el.value")
            except Exception:
                pass
            if not csrf_token:
                try:
                    csrf_token = page.evaluate(
                        "() => document.querySelector('meta[name=\"_csrf\"]')?.content || ''"
                    )
                except Exception:
                    pass

            if callback:
                callback(0, len(marcadas), None, f"CSRF: {'obtenido' if csrf_token else 'no encontrado'}")

            # Intentar POST directo primero
            login_exitoso = False
            try:
                post_data = f"username={requests.utils.quote(str(usuario))}&password={requests.utils.quote(str(password))}"
                if csrf_token:
                    post_data += f"&_csrf={requests.utils.quote(csrf_token)}"

                page.request.post(
                    f"{TRANSUNION_BASE}/sso-auth-server/login",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": page.url,
                        "Origin": TRANSUNION_BASE,
                    },
                    data=post_data,
                )
                time.sleep(2)
                page.goto(f"{TRANSUNION_BASE}/cifin/welcome", timeout=20000)
                page.wait_for_load_state("networkidle", timeout=10000)
                time.sleep(2)

                url_actual = page.url
                login_exitoso = "welcome" in url_actual and "login" not in url_actual and "nidp" not in url_actual
                if callback:
                    callback(0, len(marcadas), None, f"POST directo → {url_actual}")
            except Exception as e:
                if callback:
                    callback(0, len(marcadas), None, f"POST falló: {str(e)[:60]}, intentando formulario...")

            # Fallback: formulario + Enter
            if not login_exitoso:
                page.goto(login_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)

                for sel in ["input[name='username']", "input[placeholder='Usuario']", "input[type='text']"]:
                    try:
                        page.wait_for_selector(sel, timeout=5000)
                        page.fill(sel, usuario)
                        break
                    except Exception:
                        continue

                time.sleep(0.5)
                for sel in ["input[name='password']", "input[placeholder='Contraseña']", "input[type='password']"]:
                    try:
                        page.fill(sel, password)
                        break
                    except Exception:
                        continue

                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(8)

                url_actual = page.url
                if callback:
                    callback(0, len(marcadas), None, f"Formulario → {url_actual}")

                login_exitoso = (
                    "cifin" in url_actual or "welcome" in url_actual
                ) and "login" not in url_actual and "nidp" not in url_actual

            if not login_exitoso:
                if callback:
                    callback(0, len(marcadas), None, f"ERROR: Login fallido. URL: {page.url}")
                return resultados

            if callback:
                callback(0, len(marcadas), None, f"✓ Sesión iniciada. Procesando {len(marcadas)} cédulas...")

            for idx, datos in enumerate(marcadas):
                if callback:
                    if callback(idx, len(marcadas), None, f"Marcando cobro: {datos['cedula']}...") is False:
                        break

                cobro = marcar_cobro_playwright(page, datos, callback)
                datos.update(cobro)
                datos["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                resultados.append(datos)

                if callback:
                    if callback(idx + 1, len(marcadas), datos, "") is False:
                        break

                time.sleep(delay)

        except Exception as e:
            if callback:
                callback(0, len(marcadas), None, f"ERROR: {str(e)[:150]}")
        finally:
            cerrar_sesion_transunion(page, callback)
            browser.close()

    return resultados


def marcar_cobro_playwright(page, datos, callback=None):
    resultado_cobro = {"cobro_aplicado": False, "mensaje_cobro": "", "error_cobro": ""}
    try:
        depto = datos.get("departamento", "").upper().strip()
        muni = datos.get("municipio", "").upper().strip()
        nombre_proyecto = datos.get("nombre_proyecto", "").upper().strip()
        cedula = datos.get("cedula", "").strip()

        if callback:
            callback(0, 0, None, f"  Navegando al formulario...")

        # Ir a welcome primero, luego al formulario
        page.goto(f"{TRANSUNION_BASE}/cifin/welcome", timeout=20000)
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)

        # Intentar clic en MI CASA YA
        try:
            page.click("text=MI CASA YA", timeout=4000)
            page.wait_for_load_state("networkidle", timeout=8000)
            time.sleep(1)
        except Exception:
            pass

        # Ir al formulario de cobro
        page.goto(
            f"{TRANSUNION_BASE}/cifin/MiCasaYa/solicitarDesembolso/faces/pagos?destino=solicitarDesembolso",
            timeout=20000
        )
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(3)

        if "login" in page.url or "nidp" in page.url:
            resultado_cobro["error_cobro"] = "Sesión expirada"
            return resultado_cobro

        if callback:
            callback(0, 0, None, f"  Depto: {depto} | Muni: {muni}")

        # ── Departamento ──
        try:
            page.wait_for_selector("select", timeout=10000)
            selects = page.query_selector_all("select")
            if selects:
                selects[0].select_option(label=depto)
                time.sleep(2)
        except Exception as e:
            resultado_cobro["error_cobro"] = f"Error depto: {str(e)[:80]}"
            return resultado_cobro

        # ── Municipio ──
        try:
            selects = page.query_selector_all("select")
            if len(selects) > 1:
                selects[1].select_option(label=muni)
                time.sleep(2)
        except Exception as e:
            resultado_cobro["error_cobro"] = f"Error municipio: {str(e)[:80]}"
            return resultado_cobro

        # ── Proyecto ──
        try:
            time.sleep(1)
            selects = page.query_selector_all("select")
            if len(selects) > 2:
                opciones = selects[2].query_selector_all("option")
                opcion_elegida = None
                partes = [p.strip() for p in nombre_proyecto.split(" - ") if len(p.strip()) > 3]
                for op in opciones:
                    texto = op.inner_text().upper().strip()
                    if all(p in texto for p in partes):
                        opcion_elegida = op.get_attribute("value")
                        break
                if not opcion_elegida:
                    for op in opciones:
                        val = op.get_attribute("value") or ""
                        if val and "---" not in val and val.strip():
                            opcion_elegida = val
                            break
                if opcion_elegida:
                    selects[2].select_option(value=opcion_elegida)
                    if callback:
                        callback(0, 0, None, f"  Proyecto seleccionado ✓")
                time.sleep(2)
        except Exception:
            pass

        # ── Tipo Identificación: CEDULA ──
        try:
            selects = page.query_selector_all("select")
            for s in selects:
                opciones_s = s.query_selector_all("option")
                textos = [o.inner_text().upper() for o in opciones_s]
                if any("CEDULA" in t or "CÉDULA" in t for t in textos):
                    for op in opciones_s:
                        if "CEDULA" in op.inner_text().upper() or "CÉDULA" in op.inner_text().upper():
                            s.select_option(value=op.get_attribute("value"))
                            break
                    break
            time.sleep(0.5)
        except Exception:
            pass

        # ── Número de identificación ──
        miembros = datos.get("miembros", [])
        if not miembros:
            miembros = [{"cedula_miembro": cedula, "tipo_doc": "CEDULA"}]

        for miembro in miembros:
            ced_m = miembro.get("cedula_miembro", "").strip()
            if not ced_m:
                continue

            if callback:
                callback(0, 0, None, f"  Ingresando cédula: {ced_m}")

            try:
                inputs = page.query_selector_all("input[type='text']:not([readonly]):not([disabled])")
                for inp in inputs:
                    try:
                        if inp.is_visible() and inp.is_enabled():
                            inp.triple_click()
                            inp.fill(ced_m)
                            break
                    except Exception:
                        continue
                time.sleep(0.5)

                # Clic Adicionar
                try:
                    page.click("text=Adicionar", timeout=5000)
                    time.sleep(2)
                    if callback:
                        callback(0, 0, None, "  Adicionar ✓")
                except Exception:
                    try:
                        page.click("input[value='Adicionar']", timeout=3000)
                        time.sleep(2)
                    except Exception:
                        pass
            except Exception as e:
                if callback:
                    callback(0, 0, None, f"  Error cédula: {str(e)[:60]}")

        # ── MARCAR PARA PAGO ──
        if callback:
            callback(0, 0, None, "  Clic en MARCAR PARA PAGO...")

        marcado = False
        for selector in [
            "text=MARCAR PARA PAGO",
            "input[value='MARCAR PARA PAGO']",
            "button:has-text('MARCAR PARA PAGO')",
            "text=MARCAR",
        ]:
            try:
                page.click(selector, timeout=5000)
                marcado = True
                time.sleep(5)
                break
            except Exception:
                continue

        if not marcado:
            resultado_cobro["error_cobro"] = "No se encontró botón MARCAR PARA PAGO"
            return resultado_cobro

        # ── Verificar resultado ──
        contenido = page.content().upper()

        if "COBRO APLICADO" in contenido or "MARCADO" in contenido or "EXITOSO" in contenido:
            if "YA FUE COBRADO" in contenido or "NO SE ENCUENTRA" in contenido:
                resultado_cobro["mensaje_cobro"] = "Ya cobrado o no aplica"
            else:
                resultado_cobro["cobro_aplicado"] = True
                resultado_cobro["mensaje_cobro"] = "Marcado exitosamente ✓"
                if callback:
                    callback(0, 0, None, f"  ✓ COBRO EXITOSO para {cedula}")
        else:
            resultado_cobro["mensaje_cobro"] = "Resultado incierto - revisar en TransUnion"
            if callback:
                callback(0, 0, None, f"  ⚠ Resultado incierto para {cedula}")

        # Nuevo para siguiente
        try:
            page.click("text=Nuevo", timeout=3000)
            time.sleep(1)
        except Exception:
            pass

    except Exception as e:
        resultado_cobro["error_cobro"] = str(e)[:200]
        if callback:
            callback(0, 0, None, f"  ERROR: {str(e)[:100]}")

    return resultado_cobro
