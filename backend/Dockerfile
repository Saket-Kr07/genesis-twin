# Build context is the REPO ROOT (see docker-compose.yml), so ml/, simulation/ and
# research/ are inside the image and app/functions.py can import them.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/repo
WORKDIR /repo/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /repo
RUN mkdir -p /data/uploads
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
