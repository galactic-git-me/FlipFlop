FROM python:3.11-slim as backend

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 4311

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:4311/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4311"]

FROM backend as gemradar

EXPOSE 18000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:18000/api/gem-radar/health || exit 1

CMD ["python", "-m", "uvicorn", "app.gem_radar_standalone:app", "--host", "0.0.0.0", "--port", "18000"]
