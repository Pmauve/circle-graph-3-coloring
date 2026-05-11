from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from typing import Iterator

from three_col_circle_code.instances.native import materialize_circle_with_native


@contextmanager
def staged_runtime_instance(instance_path: Path) -> Iterator[Path]:
    """Yield a solver-ready instance path, materializing compact artifacts in local scratch."""
    path = Path(instance_path)
    if path.suffix != ".circle":
        yield path
        return

    scratch_root = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
    with tempfile.TemporaryDirectory(prefix="three-col-instance-", dir=scratch_root) as tmpdir:
        runtime_path = Path(tmpdir) / f"{path.stem}.circle.col"
        materialize_circle_with_native(circle_path=path, output_path=runtime_path)
        yield runtime_path
