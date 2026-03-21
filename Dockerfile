FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# System deps
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    g++ \
    cmake \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (includes pybind11 via pip)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Compile C++ physics engine
COPY backend/cpp/ ./backend/cpp/
RUN mkdir -p ./backend/cpp/build && \
    cd ./backend/cpp/build && \
    cmake \
      -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir) \
      -DPython3_EXECUTABLE=$(which python3) \
      .. && \
    make -j4

# Copy everything else
COPY . .

# Make the .so accessible from project root
RUN cp backend/cpp/build/physics_engine*.so /app/

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
