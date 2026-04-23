# 🏠 Bot Mi Casa Ya — Constructora Bolívar

Automatización del proceso de consulta de estado y marcación para pago del subsidio Mi Casa Ya.

---

## ¿Qué hace?

**Fase 1 — Consulta de Estado**
- Lee cada cédula de tu archivo Excel
- Consulta en `subsidiosfonvivienda.minvivienda.gov.co` el estado del hogar
- Extrae: estado, miembros del hogar, datos del proyecto (departamento, municipio, nombre)
- Si el estado es **MARCADO PARA PAGO** → activa Fase 2 automáticamente

**Fase 2 — Marcar para Pago**
- Entra a `miportafolio.transunion.co` con las credenciales del área
- Navega a Mi Casa Ya → Realizar Cobro del Subsidio
- Selecciona Departamento → Municipio → Proyecto
- Agrega cada cédula del hogar (puede ser 1 o 2 miembros)
- Hace clic en MARCAR PARA PAGO
- Registra el resultado (exitoso o error)

---

## Instalación (una sola vez)

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Instalar el navegador de Playwright (Chrome)
playwright install chromium
```

---

## Cómo usar

```bash
# Iniciar la aplicación
streamlit run app.py
```

Se abrirá automáticamente en tu navegador en `http://localhost:8501`

### Pasos dentro de la app:

1. **⚙️ Configuración** → Ingresa las credenciales de TransUnion del área
2. **⚙️ Configuración → Cargar Cédulas** → Sube tu archivo Excel con la columna `cedula`
3. **▶️ Ejecutar Bot** → Presiona "Iniciar Bot" y observa el progreso en tiempo real
4. **📊 Historial** → Consulta y descarga los resultados de ejecuciones anteriores

---

## Formato del archivo Excel de entrada

| cedula     | nombre (opcional)        |
|------------|--------------------------|
| 30670883   | ESMERALDA DURANGO        |
| 44004556   | SULLY BUILES LOPERA      |
| 5833435    | HUGO ERNESTO VASQUEZ     |

La columna de cédula puede llamarse: `cedula`, `cédula`, `documento`, `cc`, `identificacion`

---

## Resultados generados

El bot genera un Excel con las siguientes columnas:

| Columna             | Descripción                                      |
|---------------------|--------------------------------------------------|
| cedula              | Cédula consultada                                |
| estado              | Estado encontrado en Mi Casa Ya                  |
| miembros            | Cédulas de todos los miembros del hogar          |
| departamento        | Departamento del proyecto                        |
| municipio           | Municipio del proyecto                           |
| nombre_proyecto     | Nombre del proyecto de vivienda                  |
| cobro_aplicado      | True/False — resultado de la marcación           |
| mensaje_cobro       | Mensaje de respuesta de la plataforma            |
| error               | Error si algo falló                              |
| timestamp           | Fecha y hora del proceso                         |

---

## Notas importantes

- El bot corre en **modo silencioso** (sin abrir ventana del navegador) por defecto.
  Puedes activar "Mostrar navegador" en ⚙️ Configuración → Opciones si quieres verlo.
- Las credenciales se guardan localmente en `config.json` en tu equipo.
- Si la plataforma de TransUnion presenta captcha, deberás resolverlo manualmente
  la primera vez activando el modo "Mostrar navegador".
- El bot espera 2 segundos entre cédulas por defecto para no saturar las plataformas.

---

## Estructura del proyecto

```
micasaya_bot/
├── app.py                  # Aplicación principal Streamlit
├── requirements.txt        # Dependencias
├── config.json             # Configuración local (generado al guardar)
├── resultados.json         # Historial de resultados
├── pages/
│   ├── inicio.py           # Página de bienvenida
│   ├── configuracion.py    # Configuración y carga de cédulas
│   ├── ejecutar.py         # Ejecución del bot con progreso
│   └── historial.py        # Historial de ejecuciones
└── utils/
    └── bot.py              # Motor de automatización con Playwright
```
