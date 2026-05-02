from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, jobs, metrics, logs, k8s

app = FastAPI(title="DGX Cloud Clone", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(logs.router)
app.include_router(k8s.router)


@app.get("/health")
def health():
    return {"status": "ok"}
