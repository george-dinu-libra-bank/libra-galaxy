# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# tesseract (cu pachetul de limba romana): OCR-ul buletinului.
# libgl1 + libglib2.0-0: opencv, folosit de DeepFace la detectia fetei.
# fonts-dejavu-core: singurul font din imagine cu diacritice romanesti complete
# (s si t cu virgula). Fara el, rapoartele PDF ies cu patrate in locul lor.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-ron \
      libgl1 \
      libglib2.0-0 \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependintele se instaleaza inaintea codului, ca sa ramana intr-un strat pe
# care Docker il refoloseste. Codul se schimba de zeci de ori pe zi; lista de
# dependinte, rar — iar in ea intra TensorFlow (prin DeepFace), sute de MB.
# Cu ordinea inversa, fiecare modificare de o linie reinstala tot.
#
# Pachetul are nevoie de directorul app ca sa poata fi rezolvat, dar aici ne
# intereseaza numai dependintele lui, asa ca punem un ciot si il stergem.
COPY pyproject.toml ./
# Cache-ul de descarcare al pip persista intre build-uri (BuildKit), separat de
# stratul imaginii — pachetele mari (tensorflow, prin deepface) nu ajung in
# imagine (la fel ca inainte, cu PIP_NO_CACHE_DIR), dar nici nu se mai
# redescarca de pe internet cand acest strat trebuie refacut.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p app && touch app/__init__.py \
    && pip install --upgrade pip \
    && pip install . \
    && rm -rf app

# Greutatile ArcFace se descarca la build, nu la prima cerere: altfel primul
# utilizator care se inregistreaza asteapta cateva zeci de secunde degeaba.
# Sta si el inaintea codului, ca sa nu se redescarce la fiecare modificare.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('ArcFace')"

RUN useradd --create-home --uid 10001 appuser
# Modelul descarcat mai sus sta in /root/.deepface; il mutam la utilizatorul
# fara drepturi, altfel DeepFace nu-l gaseste si il descarca din nou la runtime.
RUN mv /root/.deepface /home/appuser/.deepface 2>/dev/null || true; \
    chown -R appuser:appuser /home/appuser

# Codul, la final: o modificare aici reface doar acest strat.
# PYTHONPATH=/app il face sa aiba prioritate fata de ciotul din site-packages.
COPY app ./app

USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
