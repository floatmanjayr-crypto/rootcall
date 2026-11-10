"""Run with python -m app.activation_worker on a dedicated worker service.

The web service also runs the same polling loop in a background thread (see start_embedded) so
paid customers are activated even when no dedicated worker is deployed. PostgreSQL advisory locks
make concurrent runners safe: one account is never activated by two processes at once.
"""
import logging
import os
import signal
from threading import Event, Thread

import stripe

from app.database import SessionLocal, engine
from app.services.activation_jobs import run_once

log = logging.getLogger(__name__)
POLL_SECONDS = 5


def poll(stopping: Event, session_factory=SessionLocal, interval=POLL_SECONDS):
    last_failure = None
    while not stopping.is_set():
        try:
            run_once(session_factory, stopping=stopping)
            last_failure = None
        except Exception as error:
            # A failed pass must never end the loop; saved jobs are retried on the next pass.
            failure = f"{type(error).__name__}: {error}"
            if failure != last_failure:
                log.exception("Activation polling pass failed; retrying every %s seconds", interval)
                last_failure = failure
        stopping.wait(interval)


def embedded_enabled(environ=os.environ):
    return environ.get("ACTIVATION_EMBEDDED_WORKER", "true").strip().lower() not in {"0", "false", "no", "off"}


def start_embedded(stopping: Event, session_factory=SessionLocal, interval=POLL_SECONDS):
    thread = Thread(target=poll, args=(stopping, session_factory, interval), name="activation-embedded", daemon=True)
    thread.start()
    log.info("Embedded activation runner started; set ACTIVATION_EMBEDDED_WORKER=false to disable it")
    return thread


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
    poll(stopping)
    log.info("Activation worker stopped after finishing its current activation")


if __name__ == "__main__":
    main()
