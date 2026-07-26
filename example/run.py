from dotenv import load_dotenv
load_dotenv()
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=False,
        log_level="info",
        server_header=False,
        date_header=False,
    )
