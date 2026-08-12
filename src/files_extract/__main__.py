from .runtime import configure_runtime

configure_runtime()

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
