import uvicorn
import dotenv

dotenv.load_dotenv()

# import sys
# import asyncio

# if sys.platform == 'win32':
#     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy()) # type: ignore

if __name__ == "__main__":
    print("[*] Launching FunnyStreamTools via the root entry point...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)