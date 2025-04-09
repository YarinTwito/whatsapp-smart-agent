# Build stage
FROM --platform=linux/amd64 python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.2

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure poetry and install only production dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-cache

# Final stage
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install only graphviz without extra packages
RUN apt-get update && apt-get install -y \
    graphviz \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy only necessary files from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only necessary application files
COPY app app/
COPY run.py .
COPY pyproject.toml .

# Create uploads directory
RUN mkdir -p uploads

# Install PyPDF2
RUN pip install PyPDF2==3.0.1

EXPOSE 8000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]