import sys

import dotenv
import uvicorn

import logging

from app.main import app

dotenv.load_dotenv()

LOG_LEVELS = {
    logging.getLevelName(lvl): lvl
    for lvl in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR)
}

if __name__ == "__main__":
    if "--generate-sdk" in sys.argv:
        if getattr(sys, 'frozen', False):
            print("[✗] Error: SDK generation is only available from source code.")
            print("[*] Tip: The pre-generated SDK is already included in the release folder!")
            sys.exit(1)

        from app.sdk import generate_sdk_auto
        generate_sdk_auto()
        sys.exit(0)

    elif "--level" in sys.argv:
        logger_level_id = sys.argv.index("--level") + 1
        if logger_level_id >= len(sys.argv):
            print("[✗] Error: `--level` requires an argument.")
            sys.exit(1)

        logger_level_arg = sys.argv[logger_level_id].upper()
        if logger_level_arg not in LOG_LEVELS:
            print(f"[✗] Error: Invalid level `{logger_level_arg}`. Choose from: {', '.join(LOG_LEVELS)}")
            sys.exit(1)

        logger_level = LOG_LEVELS[logger_level_arg]
        logging.basicConfig(level=logger_level)

    elif any(arg.startswith("--") for arg in sys.argv):
        invalid_flag = next(arg for arg in sys.argv if arg.startswith("--"))
        print(f"[✗] Error: Unknown argument '{invalid_flag}'")
        
        print("[*] Usage: Use `--generate-sdk` to generate stubs.")

        print(f"[*] Usage: Use `--level` to set logger level `{', '.join(LOG_LEVELS)}`")

        print("[*] Or run without flags to launch the app.")
        sys.exit(1)


    print("[*] Launching FunnyStreamTools via the root entry point...")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)