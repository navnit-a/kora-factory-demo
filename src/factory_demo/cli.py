import sys
from collections.abc import Callable

from factory_demo.kora_api import KoraAuthError

SIGN_IN_HINT = "no kora token found: run 'make auth' in the kora checkout"


def run_cli(main: Callable[[], int]) -> int:
    try:
        return main()
    except KoraAuthError as error:
        return _fail(str(error))
    except FileNotFoundError as error:
        return _fail(f"{SIGN_IN_HINT} ({error.filename})")
    except PermissionError as error:
        return _fail(str(error))


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2
