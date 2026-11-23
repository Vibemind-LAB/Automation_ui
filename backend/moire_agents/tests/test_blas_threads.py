"""The tool servers must not reserve one BLAS buffer per CPU core.

Measured on 2026-11-23 on a 32-core machine: importing ``mcp_server_handoff`` committed
1.74 GB and started 53 threads, because every OpenBLAS copy (numpy, scipy) allocates a
buffer per core at import time. With OPENBLAS_NUM_THREADS=1 it is 0.29 GB and 7 threads.
Seven such servers were running; none of them does heavy linear algebra.
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STDLIB_ONLY = {"asyncio", "json", "logging", "os", "signal", "sys", "datetime", "typing"}


def _module():
    with open(os.path.join(HERE, "mcp_server_handoff.py"), encoding="utf-8") as handle:
        return ast.parse(handle.read())


def _sets_default(node, name):
    """True for ``os.environ.setdefault("<name>", "1")`` as a statement."""
    call = getattr(node, "value", None)
    return (
        isinstance(node, ast.Expr)
        and isinstance(call, ast.Call)
        and ast.unparse(call.func) == "os.environ.setdefault"
        and [ast.literal_eval(arg) for arg in call.args] == [name, "1"]
    )


def test_blas_threads_are_limited_before_anything_can_load_numpy():
    body = _module().body
    limit = next((i for i, node in enumerate(body) if _sets_default(node, "OPENBLAS_NUM_THREADS")), None)
    assert limit is not None, "mcp_server_handoff must default OPENBLAS_NUM_THREADS to 1"

    for node in body[:limit]:
        if isinstance(node, ast.Import):
            names = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {(node.module or "").split(".")[0]}
        else:
            continue
        assert names <= STDLIB_ONLY, f"{sorted(names - STDLIB_ONLY)} is imported before the limit is set"


def test_the_limit_is_a_default_an_operator_can_override():
    source = ast.unparse(_module())
    assert "os.environ['OPENBLAS_NUM_THREADS']" not in source, "use setdefault, not assignment"
