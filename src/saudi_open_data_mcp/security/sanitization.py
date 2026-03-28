"""Input sanitization helpers."""


def sanitize_dataset_id(dataset_id: str) -> str:
    """Return a trimmed dataset identifier."""

    return dataset_id.strip()
