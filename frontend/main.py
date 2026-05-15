from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.physics.accelerator import propagate_batch

app = FastAPI()

# In a real app, we'd have a constellation database
# For this demo, we generate 500 random LEO states and propagate them live

INITIAL_SATS = []
RE = 6371.0
for i in range(500):
    r = RE + 400 + (i % 10) * 50
    inc = (i % 18) * 10
    v = (7.5 + (i % 5) * 0.1)
    INITIAL_SATS.append([r, 0, 0, 0, v * 0.5, v * 0.866]) # simplified

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("frontend/index.html") as f:
        return f.read()

@app.get("/api/constellation")
async def get_constellation():
    # Propagate 1 minute forward
    # states = propagate_batch(INITIAL_SATS, dt_seconds=60, steps=1)
    # return [{"id": i, "pos": s[:3]} for i, s in enumerate(states)]
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
