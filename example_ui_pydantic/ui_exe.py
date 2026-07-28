from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    from uvicorn import run

    run("agent:app", host="localhost", port=5000)