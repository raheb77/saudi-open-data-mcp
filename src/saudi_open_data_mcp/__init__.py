"""Package for the saudi-open-data-mcp scaffold."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("saudi-open-data-mcp")
except PackageNotFoundError:
    __version__ = "0.2.0a0"

__all__ = ["__version__"]
