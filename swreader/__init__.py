"""swreader - read SolidWorks documents (.SLDPRT, .SLDASM, .SLDDRW) without SolidWorks."""
from .container import FormatError, SwFile, open_file, unwrap

__version__ = "0.1.0"
__all__ = ["FormatError", "SwFile", "open_file", "unwrap", "__version__"]
