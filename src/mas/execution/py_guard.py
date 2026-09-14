"""Python validator (L3) — an AST allowlist for the Coder's generated code.

This is a *correctness/accident* guard, not a security boundary: CPython is not a
sandbox (PEP 551). The isolation boundary is the out-of-process executor
(``py_sandbox``: a separate interpreter, or a no-network read-only container). The walk
rejects non-allowlisted imports, dynamic-exec/IO builtins, access into system modules or
dunder attributes — and randomised estimators without a fixed ``random_state``, because a
clustering run that picks different centroids each time reports different information
(doc 10, S4).
"""
from __future__ import annotations

import ast

_ALLOWED_IMPORTS = {
    "pandas", "numpy", "matplotlib", "scipy", "sklearn", "math", "json",
    "datetime", "collections", "itertools", "statistics",
}
_BANNED_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "exit", "quit", "globals", "locals", "vars"}
_BANNED_MODULES = {"os", "sys", "socket", "subprocess", "shutil", "pathlib", "importlib", "ctypes", "builtins"}

#: sklearn estimators / helpers whose output depends on a random seed.
NEEDS_RANDOM_STATE = {
    "KMeans", "MiniBatchKMeans", "BisectingKMeans", "GaussianMixture", "BayesianGaussianMixture",
    "SpectralClustering", "IsolationForest", "RandomForestRegressor", "RandomForestClassifier",
    "ExtraTreesRegressor", "ExtraTreesClassifier", "GradientBoostingRegressor",
    "GradientBoostingClassifier", "HistGradientBoostingRegressor", "HistGradientBoostingClassifier",
    "MLPRegressor", "MLPClassifier", "SGDRegressor", "SGDClassifier", "TSNE", "NMF", "FastICA",
    "TruncatedSVD", "train_test_split", "KFold", "ShuffleSplit", "StratifiedShuffleSplit",
}


class PyValidationError(ValueError):
    """Raised when generated Python touches disallowed imports, builtins, or modules."""


def validate_python(code: str) -> ast.AST:
    """Return the parsed AST if the code is within the allowlist; raise otherwise."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise PyValidationError(f"syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    raise PyValidationError(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORTS:
                raise PyValidationError(f"import not allowed: from {node.module}")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else \
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            if isinstance(node.func, ast.Name) and name in _BANNED_CALLS:
                raise PyValidationError(f"call not allowed: {name}()")
            if name in NEEDS_RANDOM_STATE:
                has_kwargs = any(k.arg is None for k in node.keywords)
                if not has_kwargs and not any(k.arg == "random_state" for k in node.keywords):
                    raise PyValidationError(
                        f"{name}(...) needs random_state=0 so the result is the same every run")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise PyValidationError(f"dunder attribute not allowed: {node.attr}")
            if isinstance(node.value, ast.Name) and node.value.id in _BANNED_MODULES:
                raise PyValidationError(f"access to module '{node.value.id}' not allowed")
    return tree
