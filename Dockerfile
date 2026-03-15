FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3-dev \
    g++ \
    cmake \
    pybind11-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

WORKDIR /app/backend/cpp
RUN cmake . && make

WORKDIR /app
CMD ["python3", "backend/main.py"]

