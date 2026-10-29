# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
RUN groupadd --gid 10001 gijunsil && useradd --uid 10001 --gid gijunsil --no-create-home gijunsil \
    && mkdir /data && chown gijunsil:gijunsil /data
COPY --chown=10001:10001 app.py seed.py wsgi.py ./
COPY --chown=10001:10001 templates ./templates
COPY --chown=10001:10001 static ./static
ENV ESTIMATE_DATABASE=/data/estimate.sqlite3 COOKIE_SECURE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
