from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="GenshinTracker")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app
