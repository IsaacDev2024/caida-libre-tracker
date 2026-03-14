import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import sys
from typing import Optional, Tuple, List

# =================================================================================================
# CONSTANTES POR DEFECTO
# =================================================================================================
DEFAULT_HSV_LOWER = np.array([25, 100, 100])
DEFAULT_HSV_UPPER = np.array([50, 255, 255])

class Calibration:
    """
    Maneja la calibración manual de píxeles a metros.
    """
    def __init__(self):
        self.points: List[Tuple[int, int]] = []
        self.window_name = "1. Calibracion Espacial"

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.points) < 2:
                self.points.append((x, y))
                print(f"Punto {len(self.points)} seleccionado: ({x}, {y})")

    def calibrate(self, frame: np.ndarray) -> float:
        print("\n--- PASO 1: CALIBRACIÓN ESPACIAL ---")
        print("Haga clic en dos puntos de la regla/referencia.")
        print("Cuando termine, presione cualquier tecla.")
        
        display_frame = frame.copy()
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        while True:
            temp_frame = display_frame.copy()
            for i, p in enumerate(self.points):
                cv2.circle(temp_frame, p, 5, (0, 0, 255), -1)
                if i > 0:
                    cv2.line(temp_frame, self.points[i-1], p, (0, 255, 0), 2)

            cv2.putText(temp_frame, "Seleccione 2 puntos de referencia", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow(self.window_name, temp_frame)
            
            key = cv2.waitKey(20) & 0xFF
            if len(self.points) == 2:
                cv2.imshow(self.window_name, temp_frame)
                cv2.waitKey(500)
                break
            if key == 27: # ESC
                sys.exit(0)

        cv2.destroyWindow(self.window_name)

        if len(self.points) < 2:
            print("Error: Puntos insuficientes.")
            sys.exit(1)

        try:
            real_distance = float(input("\nIngrese la distancia real (metros) entre los puntos: "))
        except ValueError:
            print("Error: Valor no numérico.")
            sys.exit(1)

        p1, p2 = np.array(self.points[0]), np.array(self.points[1])
        pixel_distance = np.linalg.norm(p1 - p2)
        
        if pixel_distance == 0: sys.exit(1)
        
        return pixel_distance / real_distance

class ColorTuner:
    """
    Permite al usuario ajustar los valores HSV interactivamente antes de iniciar.
    """
    def __init__(self):
        self.window_name = "2. Ajuste de Color (Deteccion)"
        self.lower = DEFAULT_HSV_LOWER
        self.upper = DEFAULT_HSV_UPPER

    def nothing(self, x):
        pass

    def tune(self, capture: cv2.VideoCapture) -> Tuple[np.ndarray, np.ndarray]:
        print("\n--- PASO 2: AJUSTE DE COLOR ---")
        print("Ajuste los sliders para que la pelota se vea BLANCA y el fondo NEGRO.")
        print("Trate de que la regla u otros objetos queden negros.")
        print("Presione 'Espacio' o 'Enter' para confirmar y continuar.")

        cv2.namedWindow(self.window_name)
        cv2.createTrackbar('Low H', self.window_name, 0, 179, self.nothing)
        cv2.createTrackbar('High H', self.window_name, 179, 179, self.nothing)
        cv2.createTrackbar('Low S', self.window_name, 0, 255, self.nothing)
        cv2.createTrackbar('High S', self.window_name, 255, 255, self.nothing)
        cv2.createTrackbar('Low V', self.window_name, 0, 255, self.nothing)
        cv2.createTrackbar('High V', self.window_name, 255, 255, self.nothing)

        # Configurar valores iniciales razonables
        cv2.setTrackbarPos('High H', self.window_name, 179)
        cv2.setTrackbarPos('High S', self.window_name, 255)
        cv2.setTrackbarPos('High V', self.window_name, 255)

        # REINICIAR VIDEO AL PRINCIPIO
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

        while True:
            ret, frame = capture.read()
            if not ret:
                # Loop video
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame = cv2.resize(frame, (640, 480)) # Resize visual para comodidad

            # Leer sliders
            l_h = cv2.getTrackbarPos('Low H', self.window_name)
            u_h = cv2.getTrackbarPos('High H', self.window_name)
            l_s = cv2.getTrackbarPos('Low S', self.window_name)
            u_s = cv2.getTrackbarPos('High S', self.window_name)
            l_v = cv2.getTrackbarPos('Low V', self.window_name)
            u_v = cv2.getTrackbarPos('High V', self.window_name)

            lower = np.array([l_h, l_s, l_v])
            upper = np.array([u_h, u_s, u_v])

            # Procesar
            blurred = cv2.GaussianBlur(frame, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower, upper)
            
            # Mostrar resultado combinado
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            combined = np.hstack([frame, mask_bgr])
            
            cv2.imshow(self.window_name, combined)

            # Reducir espera a 10ms para loop más fluido
            key = cv2.waitKey(10) & 0xFF
            if key == 13 or key == 32: # Enter o Espacio
                self.lower = lower
                self.upper = upper
                break
            if key == 27: sys.exit(0)

        cv2.destroyWindow(self.window_name)
        print(f"Rango HSV confirmado: \nLower={self.lower}\nUpper={self.upper}")
        return self.lower, self.upper

class BallTracker:
    def __init__(self, hsv_lower, hsv_upper):
        self.hsv_lower = hsv_lower
        self.hsv_upper = hsv_upper
        self.prev_center = None

    def detect(self, frame: np.ndarray) -> Tuple[Optional[Tuple[int, int]], Optional[np.ndarray]]:
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_center = None
        best_circularity = 0 

        for c in contours:
            area = cv2.contourArea(c)
            if area < 100: continue # Ignorar ruido muy pequeño

            perimeter = cv2.arcLength(c, True)
            if perimeter == 0: continue
            
            # Calcular circularidad: 1.0 es un círculo perfecto
            # Objetos alargados como reglas tendrán circularidad baja
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            
            if M["m00"] > 0:
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
                
                # Criterios de Selección:
                # 1. Preferir objetos circulares (> 0.6)
                # 2. Si hay múltiples, preferir el más cercano a la última posición conocida
                
                is_circular = circularity > 0.5 # Umbral flexible
                
                if is_circular:
                     # Si es el primer frame o es circular, es candidato
                    if best_center is None:
                        best_center = center
                        best_circularity = circularity
                    else:
                        # Si ya tenemos uno, nos quedamos con el más circular o más grande
                        if circularity > best_circularity:
                            best_center = center
                            best_circularity = circularity
        
        self.prev_center = best_center
        return best_center, mask

class VideoProcessor:
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.capture = cv2.VideoCapture(video_path)
        if not self.capture.isOpened():
            print(f"Error: No video {video_path}")
            sys.exit(1)
        
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.calibration = Calibration()
        self.tuner = ColorTuner()
        
    def run(self):
        # 1. Calibración
        ret, frame = self.capture.read()
        if not ret: return
        px_per_m = self.calibration.calibrate(frame)
        
        # 2. Ajuste de Color
        hsv_lower, hsv_upper = self.tuner.tune(self.capture)
        tracker = BallTracker(hsv_lower, hsv_upper)

        # 3. Análisis
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        data = []
        y_origin = None
        
        print("\n--- PASO 3: INICIO DE ANÁLISIS AUTOMÁTICO ---")
        while True:
            ret, frame = self.capture.read()
            if not ret: break

            frame_idx = int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
            center, mask = tracker.detect(frame)

            if center:
                x, y = center
                if y_origin is None: y_origin = y
                
                pos_y = (y - y_origin) / px_per_m
                time = frame_idx / self.fps
                
                data.append({"Frame": frame_idx, "Tiempo": time, "Posicion": pos_y})
                
                cv2.circle(frame, center, 5, (0, 255, 0), -1)
                cv2.putText(frame, f"{pos_y:.2f}m", (x+10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

            cv2.imshow("Analisis", frame)
            # cv2.imshow("Mascara", mask) # Debug

            if cv2.waitKey(1) & 0xFF == ord('q'): break

        self.capture.release()
        cv2.destroyAllWindows()
        self.export(data)

    def export(self, data):
        if not data:
            print("No se recolectaron datos.")
            return
        
        df = pd.DataFrame(data)
        df.to_csv("resultados.csv", index=False)
        print("Datos guardados en resultados.csv")
        
        plt.figure()
        plt.plot(df["Tiempo"], df["Posicion"], 'o-')
        plt.xlabel("Tiempo (s)")
        plt.ylabel("Posición (m)")
        plt.title("Caída Libre")
        plt.grid(True)
        plt.savefig("grafica.png")
        plt.show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tracker.py <video>")
        sys.exit(1)
    
    VideoProcessor(sys.argv[1]).run()
