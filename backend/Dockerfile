FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# tesseract: OCR-ul care citeste CNP-ul de pe buletin (ron = limba romana).
# libgl1 + libglib2.0-0: cerute de opencv, pe care il foloseste DeepFace.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-ron \
      libgl1 \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Greutatile ArcFace se descarca la build, nu la prima cerere: altfel primul
# utilizator care se inregistreaza asteapta cateva zeci de secunde degeaba.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('ArcFace')"

RUN useradd --create-home --uid 10001 appuser
# Modelul descarcat mai sus sta in /root/.deepface; il mutam la utilizatorul
# fara drepturi, altfel DeepFace nu-l gaseste si il descarca din nou la runtime.
RUN mv /root/.deepface /home/appuser/.deepface 2>/dev/null || true; \
    chown -R appuser:appuser /home/appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
