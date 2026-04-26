"""Package for saudi-open-data-mcp."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("saudi-open-data-mcp")
except PackageNotFoundError:
    __version__ = "0.4.0a1"

__all__ = ["__version__"]
