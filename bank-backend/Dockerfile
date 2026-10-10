FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG PORT=8010
ENV PORT=${PORT}
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
