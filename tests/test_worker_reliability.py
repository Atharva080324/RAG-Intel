from app.workers.tasks import MAX_RETRIES, _is_retryable_error


class ProviderError(Exception):
    def __init__(self, status_code: int):
        self.response = type("Response", (), {"status_code": status_code})()


def test_transient_errors_are_retryable():
    assert _is_retryable_error(TimeoutError())
    assert _is_retryable_error(ProviderError(429))
    assert _is_retryable_error(ProviderError(503))


def test_permanent_provider_errors_are_not_retryable():
    assert not _is_retryable_error(ValueError("invalid PDF"))
    assert not _is_retryable_error(ProviderError(403))
    assert MAX_RETRIES == 3
