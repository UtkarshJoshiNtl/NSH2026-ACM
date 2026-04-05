FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies as per Astrosis Spec
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    g++ \
    cmake \
    make \
    python3-dev \
    pybind11-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Compile C++ physics engine (backend/cpp/ in our repo)
COPY backend/cpp/ ./backend/cpp/
RUN mkdir -p ./backend/cpp/build && \
    cd ./backend/cpp/build && \
    cmake .. && \
    make -j4

# Copy the compiled .so to root for Python to find easily
RUN cp backend/cpp/build/physics_engine*.so /app/

# Copy all project files
COPY . .

# Expose port 8000
EXPOSE 8000

# Start command as per Spec
CMD ["python3", "backend/main.py"]
