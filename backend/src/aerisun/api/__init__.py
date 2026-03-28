__all__ = ["api_router"]


def __getattr__(name: str):
    if name == "api_router":
        from .router import api_router

        return api_router
    raise AttributeError(name)
