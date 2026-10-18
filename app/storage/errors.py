class StorageUnavailable(RuntimeError):
    """Safe to show; provider exception details must never reach HTTP or logs."""
