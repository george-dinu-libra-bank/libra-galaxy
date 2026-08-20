FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# tesseract (cu pachetul de limba romana): OCR-ul buletinului.
# libgl1 + libglib2.0-0: opencv, folosit de DeepFace la detectia fetei.
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

RUN useradd --create-home --uid 10001 appuser
USER appuser

# Greutatile ArcFace se descarca la build, nu la prima cerere. Comanda vine dupa
# USER, ca fisierele sa ajunga in ~/.deepface al lui appuser — de acolo le
# citeste la runtime; descarcate ca root, ar fi ilizibile pentru el.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('ArcFace')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
