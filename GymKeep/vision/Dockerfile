# Pipeline de vision en un contenedor, en CPU (no requiere GPU NVIDIA).
# Prototipo de integracion: ver INTEGRACION.md y docker-compose.vision.yml.
FROM python:3.11-slim

# Sin apt-get: se usa OpenCV "headless" (mas abajo), que no necesita librerias graficas del
# sistema. Asi la imagen se construye aunque la red bloquee los repositorios de Debian.

WORKDIR /app

# torch para CPU primero: el paquete por defecto trae CUDA y pesa ~3 GB.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
# ultralytics trae opencv-python (que pide libGL): se cambia por la version headless.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir "opencv-python-headless>=4.6" \
    && python -c "import cv2; print('OpenCV', cv2.__version__)"

COPY gymkeep_vision ./gymkeep_vision
# Modelo por defecto (yolo26n) dentro de la imagen: no hay que descargarlo aparte.
RUN python -c "from gymkeep_vision.config import ConfigModelo; from ultralytics import YOLO; YOLO(ConfigModelo().ruta_pesos())"

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "gymkeep_vision"]
