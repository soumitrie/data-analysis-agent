import logging

import structlog

_configured = False


def configure_logging(log_level: str = "INFO") -> None:
    global _configured
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    # Ensure structlog is configured before the first (often import-time) logger
    # is created, so module-level loggers emit the JSON format rather than the
    # default console renderer.
    if not _configured:
        configure_logging()
    return structlog.get_logger().bind(logger=name)


# Configure at import so any module-level `get_logger(...)` resolves against the
# JSON config; the app lifespan re-applies the configured log level.
configure_logging()
