# Caída Libre Tracker

Un proyecto interactivo de visión por computadora para el análisis cinemático de la caída libre a partir de video. Diseñado para extraer datos experimentales con alta precisión y ajustar modelos físicos mediante el seguimiento de objetos y regresión polinomial.

---

## 👥 Autores
- Isaac David Sánchez Sánchez
- Santiago Andrés Orejuela Cueter
- Maria Valentina Serna Gonzalez
- Luis Mario Diaz Martínez

---

## 📝 Descripción General

**Caída Libre Tracker Pro** es una herramienta educativa y científica que consta de una **API Backend (FastAPI)** y una **Interfaz Web (HTML/CSS/Vanilla JS)**. Permite a los usuarios subir un video de un objeto en caída libre, realizar una calibración espacial para establecer la equivalencia entre píxeles y metros, y aislar el objeto del fondo utilizando un filtro de color HSV con vista previa en vivo (MJPEG Stream). 

Mediante el uso de algoritmos de procesamiento de imágenes (`OpenCV`), el programa rastrea la posición central del objeto a lo largo del tiempo, corta automáticamente los segmentos que no aportan movimiento real, y usa el método de mínimos cuadrados (`SciPy`) para ajustar los datos a la ecuación de la cinemática:

$$ y(t) = y_0 + v_0 t - \frac{g}{2} t^2 $$

Dicho ajuste permite obtener un valor empírico para la aceleración de la gravedad ($g$).

---

## 🚀 Características Principales

1. **Subida de Videos y Vista Previa:** Integración sencilla seleccionando o arrastrando el archivo grabado.
2. **Calibración Espacial Interactiva:** Da clic en dos puntos del primer frame del video para definir una distancia de referencia (Regla, marca en la pared) y calcular los metros por píxel.
3. **Filtro de Color HSV en Tiempo Real:** Ajusta los canales Hue (Matiz), Saturation (Saturación) y Value (Brillo) para segmentar perfectamente el objeto deseado del fondo, observando el stream continuo del resultado antes del procesamiento.
4. **Análisis por Consola y Web (Versatilidad):** 
   - Tracking automático que determina el centroide del objeto midiendo contornos y circularidad por frame.
   - Recorte inteligente (trimming) del inicio y fin de los datos estáticos.
5. **Modelado Físico (`curve_fit`):** Determina estadísticamente $y_0$, $v_0$ y $g$ (gravedad experimental) con su error respectivo ($\sigma$).
6. **Gráficos y Exportación (Chart.js):** Genera visualizaciones modernas e interactivas de Postición vs. Tiempo, y el ajuste cuadrático de los puntos con posibilidad de exportar los resultados tabulares a CSV.

---

## 🛠️ Stack Tecnológico Utilizado

**Backend:**
- `Python` (Lenguaje de programación principal)
- `FastAPI` (Exposición de API, gestión de carga de archivos y ruteo HTTP)
- `OpenCV` (cv2) (Visión artificial, streaming MJPEG, procesamiento de frames, bitwise_and, GaussianBlur)
- `NumPy` & `SciPy` (Transformaciones matemáticas, algebra lineal y ajuste de función no lineal `curve_fit`)
- `Uvicorn` (Servidor ASGI)

**Frontend:**
- `HTML5` y `CSS3` (Diseño limpio, interactivo y con tipografía moderna Google Fonts - *Plus Jakarta Sans*)
- `JavaScript / Fetch API` (Asincronía en comunicación con el Backend)
- `Chart.js` (Renderización de estadísticas temporales y modelo de la curva)

---

## 📂 Estructura del Proyecto

```text
Caida Libre/
│
├── app.py                # Servidor principal FastAPI con las rutas y endpoints del Tracker.
├── tracker.py            # Módulo CLI (Command Line Engine) para calibración y tracking tradicional con OpenCV GUI.
├── uploads/              # Carpeta temporal autogenerada para videos subidos.
│
├── static/               # Activos estáticos correspondientes al Frontend Web
│   ├── index.html        # Estructura visual principal y UI interactiva en pasos.
│   ├── style.css         # Lógica de la hoja de estilos, grids interactivos y diseño adaptativo.
│   └── script.js         # Lógica base que coordina el flujo (subida, calibración con Canvas, streaming de tuning, gráficos y red).
```

---

## ⚙️ Instrucciones de Instalación y Uso Local

Siguiendo estos pasos, podrás ejecutar la herramienta en tu entorno de desarrollo local.

### Prerrequisitos
- Tener instalado `Python 3.8+` y un entorno virtual configurado opcionalmente.

### Instalación de dependencias

Instala los módulos básicos si no cuentas con ellos (ejecutar en terminal en la ruta principal del proyecto):
```bash
pip install fastapi uvicorn opencv-python numpy scipy python-multipart
# Si usas el módulo tracker.py (CLI) también puedes requerir pandas y matplotlib:
pip install pandas matplotlib
```

### Ejecutar la Aplicación Web

Para poner el sitio backend y frontend a la escucha, corre el siguiente comando:
```bash
python app.py
```
*(Opcionalmente, puedes ejecutar `uvicorn app:app --reload`)*. 

Luego de iniciar:
1. Abre tu navegador e ingresa a donde se encuentra el archivo `static/index.html`.
2. Arrastra tu propio video empírico en formato MP4/MOV mostrando la caída de una bola de color contrastante.
3. Sigue los 4 pasos indicados dinámicamente: Subir, Calibrar, Sintonizar HSV, y Procesar.