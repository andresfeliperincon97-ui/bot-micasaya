import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]

def conectar_sheets(ruta_credenciales, sheet_id):
    creds = Credentials.from_service_account_file(ruta_credenciales, scopes=SCOPES)
    cliente = gspread.authorize(creds)
    return cliente.open_by_key(sheet_id)

def leer_cedulas(workbook):
    hoja = workbook.worksheet("Entrada")
    datos = hoja.get_all_values()
    cedulas = []
    for fila in datos[4:]:
        if fila and len(fila) > 1 and fila[1].strip().isdigit() and len(fila[1].strip()) >= 7:
            cedulas.append({"cedula": fila[1].strip(), "nombre": fila[2].strip() if len(fila) > 2 else ""})
    return cedulas

def leer_marcadas_para_pago(workbook):
    hoja = workbook.worksheet("Resultados")
    datos = hoja.get_all_values()
    marcadas = []
    for i, fila in enumerate(datos[4:], 5):
        if len(fila) >= 3 and "MARCADO PARA PAGO" in fila[2].upper():
            cobro = fila[7].strip().upper() if len(fila) > 7 else ""
            if cobro != "SI":
                marcadas.append({
                    "fila_sheets": i,
                    "cedula": fila[0].strip(),
                    "nombre": fila[1].strip(),
                    "estado": fila[2].strip(),
                    "departamento": fila[3].strip(),
                    "municipio": fila[4].strip(),
                    "nombre_proyecto": fila[5].strip(),
                    "tipo_vivienda": fila[6].strip(),
                    "miembros": [{"cedula_miembro": fila[0].strip(), "tipo_doc": "CEDULA"}],
                })
    return marcadas

def escribir_resultado(workbook, idx, resultado):
    hoja = workbook.worksheet("Resultados")
    fila = idx + 5
    cobro = resultado.get("cobro_aplicado", None)
    cobro_str = "SI" if cobro is True else ("NO" if cobro is False else "N/A")
    valores = [
        resultado.get("cedula",""),
        resultado.get("nombre",""),
        resultado.get("estado",""),
        resultado.get("departamento",""),
        resultado.get("municipio",""),
        resultado.get("nombre_proyecto",""),
        resultado.get("tipo_vivienda",""),
        cobro_str,
        resultado.get("timestamp",""),
        resultado.get("error",""),
    ]
    hoja.update(f"A{fila}:J{fila}", [valores])

def actualizar_cobro_fila(workbook, fila_sheets, cobro_exitoso, mensaje, timestamp):
    hoja = workbook.worksheet("Resultados")
    cobro_str = "SI" if cobro_exitoso else "NO"
    hoja.update(f"H{fila_sheets}:J{fila_sheets}", [[cobro_str, timestamp, mensaje]])
