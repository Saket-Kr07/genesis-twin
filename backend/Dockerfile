# Build context is the REPO ROOT (see docker-compose.yml), so ml/, simulation/ and
# research/ are inside the image and app/functions.py can import them.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/repo
RUN useradd --create-home --uid 1000 app
WORKDIR /repo/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . /repo
RUN mkdir -p /data/uploads && chown -R app:app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
