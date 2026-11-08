FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CUYSEARCH_HOST=0.0.0.0

WORKDIR /app

COPY pyproject.toml README.md LICENSE PROCEDENCIA.md ./
COPY src ./src

RUN pip install --no-cache-dir '.[servicio]'

EXPOSE 8090

CMD ["cuysearch"]
