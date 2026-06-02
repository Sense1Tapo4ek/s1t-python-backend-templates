# Re-export BuildInfoVo so driving adapters (controllers) get the type for their
# Dishka injection without importing domain directly (adapters/driving may
# import only ports/driving).
from ...domain import BuildInfoVo

__all__ = ["BuildInfoVo"]
