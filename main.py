import uvicorn
import dotenv
import sys

from app.main import app

dotenv.load_dotenv()

if __name__ == "__main__":
    if "--generate-sdk" in sys.argv:
        if getattr(sys, 'frozen', False):
            print("[✗] Error: SDK generation is only available from source code.")
            print("[*] Tip: The pre-generated SDK is already included in the release folder!")
            sys.exit(1)

        from app.sdk import generate_sdk_auto
        generate_sdk_auto()
        sys.exit(0)

    elif any(arg.startswith("--") for arg in sys.argv):
        invalid_flag = next(arg for arg in sys.argv if arg.startswith("--"))
        print(f"[✗] Error: Unknown argument '{invalid_flag}'")
        print("[*] Usage: Use `--generate-sdk` to generate stubs, or run without flags to launch the app.")
        sys.exit(1)


    print("[*] Launching FunnyStreamTools via the root entry point...")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)