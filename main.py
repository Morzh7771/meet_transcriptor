"""Run the Meet Transcript API (extension backend)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.backend.api.fast_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
