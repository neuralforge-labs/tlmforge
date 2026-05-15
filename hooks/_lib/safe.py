import sys
import functools


def fail_open(fn):
    """Decorator: catch Exception (not SystemExit), warn to stderr, exit 0."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except SystemExit:
            raise
        except Exception as exc:
            print(
                f"[tlmforge] enforcement hook error — gate bypassed. ({type(exc).__name__}: {exc})",
                file=sys.stderr,
            )
        sys.exit(0)
    return wrapper
