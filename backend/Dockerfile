FROM python:3.11-slim

ARG USE_MIRROR=false

WORKDIR /app

RUN if [ "$USE_MIRROR" = "true" ]; then \
    sed -i 's/deb.debian.org/mirrors.bfsu.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.bfsu.edu.cn/g' /etc/apt/sources.list.d/debian.sources; \
    fi

# Install system dependencies (fonts for PDF generation, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN if [ "$USE_MIRROR" = "true" ]; then \
    pip install --no-cache-dir -i https://mirrors.bfsu.edu.cn/pypi/web/simple -r requirements.txt; \
    else \
    pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

# Create directories
RUN mkdir -p /app/tmp /app/data /app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
