# Contoso AI — FastAPI + 정적 프런트엔드 (빌드 도구 없음)
# MCR 이미지를 써서 Docker Hub 요청 제한과 무관하게 ACR 원격 빌드가 동작합니다.
FROM mcr.microsoft.com/azurelinux/base/python:3.12

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PORT=8000
WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY app ./app
COPY static ./static
COPY seed ./seed
COPY seed_en ./seed_en

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
