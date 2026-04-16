__all__ = [
    "generate_instance",
    "generate_many",
    "write_instance",
]


def __getattr__(name):
    """Lazily expose generation helpers without importing the CLI module eagerly."""
    if name in __all__:
        from three_col_circle_code.generation.random_instances import (
            generate_instance,
            generate_many,
            write_instance,
        )

        exports = {
            "generate_instance": generate_instance,
            "generate_many": generate_many,
            "write_instance": write_instance,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
