"""Bound CPU/model work on the free instance without changing retrieval quality."""

import os
from contextlib import contextmanager
from functools import wraps
from threading import BoundedSemaphore

from fastapi import HTTPException

_slot = BoundedSemaphore(1)


@contextmanager
def inference_slot():
    enabled = os.getenv("CCI_LOW_MEMORY") == "true"
    acquired = not enabled or _slot.acquire(timeout=2)
    if not acquired:
        raise HTTPException(
            503,
            "The assistant is busy. Please try again shortly.",
            headers={"Retry-After": "3"},
        )
    try:
        yield
    finally:
        if enabled:
            _slot.release()


def bounded_inference(function):
    @wraps(function)
    def bounded(*args, **kwargs):
        with inference_slot():
            return function(*args, **kwargs)

    return bounded
