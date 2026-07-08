import uvicorn
import dotenv

dotenv.load_dotenv()


if __name__ == "__main__":
    print("[*] Launching FunnyStreamTools via the root entry point...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)