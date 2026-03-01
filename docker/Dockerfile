FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

ENV UV_SYSTEM_PYTHON=1
ENV UV_NO_CACHE=1
ENV UV_NO_PIP=1

COPY pyproject.toml uv.lock ./

RUN rm -rf /app/.venv

RUN uv sync

COPY . .

CMD ["uv", "run", "src/agents/react_test.py"]
