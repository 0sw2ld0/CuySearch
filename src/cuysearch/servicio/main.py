"""Arranque del servicio: un único proceso con límites conservadores."""

from cuysearch.servicio.api import create_app
from cuysearch.servicio.config import get_settings


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.cuysearch_host,
        port=settings.cuysearch_port,
        log_level=settings.cuysearch_log_level,
        workers=1,
        access_log=False,
        timeout_keep_alive=5,
        limit_concurrency=max(10, settings.cuysearch_max_concurrent_extractions * 4),
    )


if __name__ == "__main__":
    run()
