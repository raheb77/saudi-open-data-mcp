"""Rate limit policy placeholders."""

from pydantic import BaseModel


class RateLimitPolicy(BaseModel):
    """Placeholder rate limit policy."""

    requests: int = 60
    window_seconds: int = 60
