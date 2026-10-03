# Pipeline de vision en un contenedor, en CPU (no requiere GPU NVIDIA).
# Prototipo de integracion: ver INTEGRACION.md y docker-compose.vision.yml.
FROM python:3.11-slim

# OpenCV necesita estas librerias del sistema.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# torch para CPU primero: el paquete por defecto trae CUDA y pesa ~3 GB.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gymkeep_vision ./gymkeep_vision
# Modelo por defecto (yolo26n) dentro de la imagen: no hay que descargarlo aparte.
RUN python -c "from gymkeep_vision.config import ConfigModelo; from ultralytics import YOLO; YOLO(ConfigModelo().ruta_pesos())"

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "gymkeep_vision"]
