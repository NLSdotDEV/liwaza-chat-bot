# Contexte de build = racine du repo (nécessaire pour accéder à la fois à
# backend/ et frontend/) :
#   docker build -f backend/Dockerfile -t ci-dashboard .

FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /build/dist ./static

# $PORT est injecté par la plupart des PaaS (Render, Railway, Fly.io) ; 8000
# en repli pour un lancement local sans variable d'environnement.
#
# --proxy-headers --forwarded-allow-ips='*' : derrière le proxy TLS de Render,
# la connexion TCP vue par uvicorn vient de leur load balancer interne, pas du
# visiteur — sans ça, request.client.host (utilisé pour le rate limiting dans
# main.py) renvoie l'IP du proxy pour tout le monde, et la limite de 15
# req/h devient globale au lieu de par-visiteur. '*' est sûr ici : le seul
# chemin réseau vers ce conteneur est le proxy de la plateforme.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
