from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, FileResponse
from pydantic import BaseModel
import cv2
import numpy as np
import os
import shutil
from typing import List, Tuple, Optional
import math
from tracker import BallTracker # Importar tu lógica original

app = FastAPI(title="Caída Libre Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins including file://
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/site", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/upload")
async def upload_video(video: UploadFile = File(...)):
    """Sube el video y devuelve la ruta y un frame de referencia."""
    file_path = os.path.join(UPLOAD_DIR, video.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    
    # Extraer el primer frame
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=400, detail="No se pudo leer el video")

    frame_path = f"{file_path}_frame0.jpg"
    cv2.imwrite(frame_path, frame)
    
    return {"video_path": file_path, "frame_url": f"http://localhost:8000/api/frame?path={frame_path}"}

@app.get("/api/frame")
def get_frame(path: str):
    """Retorna la imagen guardada."""
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Frame not found")

@app.get("/api/video")
def get_video(path: str):
    """Sirve el archivo de video para reproducción en el navegador."""
    if os.path.exists(path):
        return FileResponse(path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")

class TunerRequest(BaseModel):
    video_path: str
    l_h: int
    u_h: int
    l_s: int
    u_s: int
    l_v: int
    u_v: int

@app.post("/api/tune")
def tune_hsv(req: TunerRequest):
    """Toma un cuadro, aplica el filtro HSV configurado y devuelve el preview."""
    cap = cv2.VideoCapture(req.video_path)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=400, detail="Cannot read video")
        
    blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    
    lower = np.array([req.l_h, req.l_s, req.l_v])
    upper = np.array([req.u_h, req.u_s, req.u_v])
    
    mask = cv2.inRange(hsv, lower, upper)
    
    # Lógica de hsv_tuner.py
    result = cv2.bitwise_and(frame, frame, mask=mask)
    
    # Resize opcional si es muy grande
    h, w = result.shape[:2]
    if w > 800:
        ratio = 800.0 / w
        result = cv2.resize(result, (800, int(h * ratio)))
        
    _, buffer = cv2.imencode('.jpg', result)
    return Response(content=buffer.tobytes(), media_type="image/jpeg")

import time as _time
from fastapi.responses import StreamingResponse

@app.get("/api/tune-stream")
def tune_stream(video_path: str, l_h: int, u_h: int, l_s: int, u_s: int, l_v: int, u_v: int):
    """Streaming MJPEG del video filtrado con OpenCV - idéntico a hsv_tuner.py."""
    def generate():
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        delay = 1.0 / fps
        
        lower = np.array([l_h, l_s, l_v])
        upper = np.array([u_h, u_s, u_v])
        
        while True:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop
                continue
            
            frame = cv2.resize(frame, (640, 480))
            blurred = cv2.GaussianBlur(frame, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower, upper)
            result = cv2.bitwise_and(frame, frame, mask=mask)
            
            _, buffer = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            _time.sleep(delay)
        
        cap.release()
    
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

class ProcessRequest(BaseModel):
    video_path: str
    l_h: int
    u_h: int
    l_s: int
    u_s: int
    l_v: int
    u_v: int
    pt1_x: int
    pt1_y: int
    pt2_x: int
    pt2_y: int
    real_distance: float
    original_w: int  # Ancho original en el cliente para reescalar
    original_h: int  # Alto original en el cliente para reescalar

@app.post("/api/process")
def process_video(req: ProcessRequest):
    cap = cv2.VideoCapture(req.video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Cannot open video")

    fps = cap.get(cv2.CAP_PROP_FPS)
    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Ajustar coordenadas de la interfaz al tamaño original del video
    scale_x = video_w / req.original_w
    scale_y = video_h / req.original_h
    
    p1 = np.array([req.pt1_x * scale_x, req.pt1_y * scale_y])
    p2 = np.array([req.pt2_x * scale_x, req.pt2_y * scale_y])
    
    pixel_distance = np.linalg.norm(p1 - p2)
    if pixel_distance == 0:
         raise HTTPException(status_code=400, detail="La distancia en pixeles es 0")
         
    px_per_m = pixel_distance / req.real_distance
    
    lower = np.array([req.l_h, req.l_s, req.l_v])
    upper = np.array([req.u_h, req.u_s, req.u_v])
    
    tracker = BallTracker(lower, upper)
    
    data = []
    y_origin = None
    t_origin = None
    
    NO_DETECT_LIMIT = 10     # frames consecutivos sin detección -> parar
    no_detect_count = 0
    started_tracking = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        center, mask = tracker.detect(frame)
        
        if center:
            no_detect_count = 0
            x, y = center
            if y_origin is None: 
                y_origin = y
                t_origin = frame_idx / fps
                started_tracking = True
                
            pos_y = (y - y_origin) / px_per_m
            time = (frame_idx / fps) - t_origin
            
            data.append({
                "frame": frame_idx,
                "time": time,
                "position": pos_y
            })
        else:
            if started_tracking:
                no_detect_count += 1
                if no_detect_count >= NO_DETECT_LIMIT:
                    break
            
    cap.release()
    
    # Post-procesamiento: recortar datos estancados al final y al inicio
    STALE_TOLERANCE = 0.002  # metros
    if len(data) > 3:
        # 1. Recortar del final hacia atrás
        last_pos = data[-1]["position"]
        trim_end_idx = len(data)
        for i in range(len(data) - 2, -1, -1):
            if abs(data[i]["position"] - last_pos) < STALE_TOLERANCE:
                trim_end_idx = i
            else:
                break
        # Mantener al menos el primer punto estancado del final
        if trim_end_idx < len(data) - 1:
            data = data[:trim_end_idx + 1]
            
        # 2. Recortar del inicio hacia adelante
        if len(data) > 3:
            first_pos = data[0]["position"]
            trim_start_idx = 0
            for i in range(1, len(data)):
                if abs(data[i]["position"] - first_pos) < STALE_TOLERANCE:
                    trim_start_idx = i
                else:
                    break
            
            # Dejar el último punto estancado como t=0 para que inicie desde reposo (v0=0 aprox)
            if trim_start_idx > 0:
                data = data[trim_start_idx:]
                
            # 3. Reajustar tiempo y posición para que empiecen en 0
            if len(data) > 0:
                new_t_origin = data[0]["time"]
                new_y_origin = data[0]["position"]
                for row in data:
                    row["time"] -= new_t_origin
                    row["position"] -= new_y_origin
                    
    return JSONResponse(content={"data": data})

class FitRequest(BaseModel):
    times: List[float]
    positions: List[float]

@app.post("/api/fit")
def fit_curve(req: FitRequest):
    """Ajusta los datos a y(t) = y0 + v0*t - (g/2)*t² usando curve_fit."""
    from scipy.optimize import curve_fit

    t = np.array(req.times)
    y = np.array(req.positions)

    if len(t) < 3:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 3 puntos para el ajuste")

    def func(x, y0, v0, g):
        return y0 + v0 * x - (g / 2) * x**2

    try:
        popt, pcov = curve_fit(func, t, y, p0=[0, 0, 9])
        perr = np.sqrt(np.diag(pcov))

        # Generar curva suave para la gráfica
        t_smooth = np.linspace(t.min(), t.max(), 200).tolist()
        y_fit = func(np.array(t_smooth), *popt).tolist()

        return {
            "y0": float(popt[0]),
            "v0": float(popt[1]),
            "g": float(popt[2]),
            "sigma_y0": float(perr[0]),
            "sigma_v0": float(perr[1]),
            "sigma_g": float(perr[2]),
            "fit_t": t_smooth,
            "fit_y": y_fit
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en el ajuste: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
