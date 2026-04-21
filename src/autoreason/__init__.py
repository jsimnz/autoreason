"""AutoReason — iterative multi-agent refinement loop for subjective work."""

__version__ = "0.1.0"

from autoreason.config import Config
from autoreason.loop import RunResult, run_autoreason_loop
from autoreason.prompts import Prompts

__all__ = ["Config", "Prompts", "RunResult", "run_autoreason_loop", "__version__"]
