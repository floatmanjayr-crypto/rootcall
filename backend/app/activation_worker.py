"""Run with python -m app.activation_worker on a dedicated worker service."""
import logging
import os
import signal
from threading import Event

import stripe

from app.database import SessionLocal, engine
from app.services.activation_jobs import run_once

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The activation worker requires PostgreSQL for cross-process locking.")
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        raise RuntimeError("STRIPE_SECRET_KEY must be configured for activation payment verification.")
    stopping = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    log.info("Activation worker ready; polling saved jobs")
    while not stopping.is_set():
        run_once(SessionLocal, stopping=stopping)
        stopping.wait(5)
    log.info("Activation worker stopped after finishing its current activation")


if __name__ == "__main__":
    main()
