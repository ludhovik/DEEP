"""Opt-in, content-checked reuse of converter calculations and complete bundles.

Arrays are stored losslessly as NPY (never pickle), before viewer downsampling.
The cache is disposable and lives outside public/. Output publication continues
to use viewer_bundle's validated staging and backup mechanism.
"""
from __future__ import annotations

import ast
from contextvars import ContextVar
import functools
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import textwrap
import types

import numpy as np

# The command-line scripts and package imports must share the same context.
sys.modules.setdefault("conversion_cache", sys.modules[__name__])
sys.modules.setdefault("tools.conversion_cache", sys.modules[__name__])

try:
    from viewer_bundle import bundle_path, staged_bundle_output, validate_bundle
except ImportError:
    from tools.viewer_bundle import bundle_path, staged_bundle_output, validate_bundle


MANIFEST = "conversion_manifest.json"
CACHE_SCHEMA = 1
_active_cache = ContextVar("deepscope_conversion_cache", default=None)


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _identity(value, tokens=None):
    """Hash actual array contents, including dtype/shape; never trust object IDs."""
    if tokens and id(value) in tokens and tokens[id(value)][0] is value:
        return {"registered": _identity(tokens[id(value)][1])}
    if isinstance(value, np.ndarray):
        arr = np.ascontiguousarray(value)
        if arr.dtype.hasobject:
            raise TypeError("Object arrays cannot be cached")
        return {"array": hashlib.sha256(memoryview(arr).cast("B")).hexdigest(),
                "dtype": arr.dtype.str, "shape": arr.shape}
    if isinstance(value, np.generic):
        return _identity(value.item(), tokens)
    if isinstance(value, complex):
        return {"complex": [_identity(value.real), _identity(value.imag)]}
    if isinstance(value, float) and not np.isfinite(value):
        return {"float": repr(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return {"path": str(value.resolve())}
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [_identity(v, tokens) for v in value]]
    if isinstance(value, dict):
        return {"dict": [[_identity(k, tokens), _identity(v, tokens)] for k, v in sorted(value.items(), key=lambda item: repr(item[0]))]}
    if isinstance(value, types.ModuleType):
        path = getattr(value, "__file__", None)
        return {"module": value.__name__, "file": file_digest(path) if path else None}
    raise TypeError(f"Unsupported cache argument: {type(value).__name__}")


def calculation_identity(function, seen=None):
    """Include transitive Python helpers and constants, not unrelated new fields."""
    function = inspect.unwrap(function)
    seen = set() if seen is None else seen
    name = function.__module__.split(".")[-1] + "." + function.__qualname__
    if id(function) in seen:
        return name
    seen.add(id(function))
    try:
        syntax = ast.parse(textwrap.dedent(inspect.getsource(function)))
        syntax.body[0].decorator_list = []
        source = ast.dump(syntax, include_attributes=False)
    except (OSError, TypeError, IndentationError, SyntaxError):
        source = repr(function.__code__.co_code)
    dependencies = {}
    for key in function.__code__.co_names:
        value = function.__globals__.get(key)
        if inspect.isfunction(value):
            dependencies[key] = calculation_identity(value, seen)
        elif inspect.isclass(value) and value.__module__ == function.__module__:
            if id(value) not in seen:
                seen.add(id(value))
                dependencies[key] = {member: calculation_identity(method, seen)
                                     for member, method in vars(value).items() if inspect.isfunction(method)}
        elif isinstance(value, (str, int, float, bool, tuple, list, dict, np.ndarray)):
            try:
                dependencies[key] = _identity(value)
            except TypeError:
                pass
    return {"name": name, "source": source, "dependencies": dependencies}


def cached_calculation(function=None, *, mutates=(), attributes=()):
    """Memoize selected expensive operations; preserve declared tracing metadata."""
    if function is None:
        return lambda fn: cached_calculation(fn, mutates=mutates, attributes=attributes)
    signature = inspect.signature(function)

    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        cache = _active_cache.get()
        if cache is None:
            return function(*args, **kwargs)
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()

        def compute():
            result = function(*args, **kwargs)
            return {"result": result,
                    "mutated": {key: bound.arguments[key] for key in mutates},
                    "attributes": {key: getattr(wrapped, key, getattr(function, key, None)) for key in attributes}}

        data = cache.call(function.__name__, compute, bound.arguments, calculation_identity(function))
        for key, value in data["mutated"].items():
            target = bound.arguments[key]
            if isinstance(target, list):
                target[:] = value
            else:
                target.clear()
                target.update(value)
        for key, value in data["attributes"].items():
            setattr(wrapped, key, value)
            setattr(function, key, value)
        return data["result"]
    return wrapped


class CalculationCache:
    def __init__(self, root, namespace, force=False):
        self.root = Path(root)
        self.namespace = namespace
        self.force = force
        self.tokens = {}
        self.hits = self.misses = 0

    def register(self, obj, signature):
        self.tokens[id(obj)] = (obj, signature)

    def call(self, label, compute, inputs, revision):
        try:
            key = _digest([CACHE_SCHEMA, self.namespace, label, revision, _identity(inputs, self.tokens)])
        except TypeError:
            # Unrecognised objects are calculated normally rather than reused
            # with a guessed signature (e.g. a third-party transform instance).
            return compute()
        directory = self.root / key[:2] / key
        if not self.force:
            try:
                manifest = json.loads((directory / "entry.json").read_text())
                if manifest["key"] != key or _digest(manifest["value"]) != manifest["sha256"]:
                    raise ValueError("Wrong cache key")
                result = self._read(manifest["value"], directory)
                self.hits += 1
                print(f"  Reuse calculation: {label}", flush=True)
                return result
            except (OSError, ValueError, KeyError, TypeError):
                pass
        result = compute()
        self.misses += 1
        directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".writing-", dir=directory.parent) as tmp:
            stage = Path(tmp) / "entry"
            stage.mkdir()
            value = self._write(result, stage, [0])
            (stage / "entry.json").write_text(json.dumps({"key": key, "value": value, "sha256": _digest(value)}, allow_nan=False))
            # A cache failure never changes an already published viewer bundle.
            # Entries are disposable; an interrupted replacement is a cache miss.
            if directory.exists():
                shutil.rmtree(directory)
            os.replace(stage, directory)
        return result

    def _write(self, value, root, counter):
        if isinstance(value, np.ndarray):
            if value.dtype.hasobject:
                raise TypeError("Object arrays cannot be cached")
            filename = f"array-{counter[0]}.npy"
            counter[0] += 1
            np.save(root / filename, value, allow_pickle=False)
            return {"kind": "array", "file": filename, "sha256": file_digest(root / filename)}
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, (dict, list, tuple)):
            items = list(value.items()) if isinstance(value, dict) else value
            return {"kind": type(value).__name__, "items": [self._write(v, root, counter) for v in items]}
        if isinstance(value, complex):
            return {"kind": "complex", "real": value.real, "imag": value.imag}
        if isinstance(value, float) and not np.isfinite(value):
            return {"kind": "float", "value": repr(value)}
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise TypeError(f"Unsupported cache result: {type(value).__name__}")
        return {"kind": "scalar", "value": value}

    def _read(self, node, root):
        kind = node["kind"]
        if kind == "array":
            path = bundle_path(root, node["file"])
            if path.is_symlink() or file_digest(path) != node["sha256"]:
                raise ValueError("Damaged cached array")
            # Copy-on-write mapping permits the converters' in-place operations
            # without changing the stored native-precision values.
            return np.load(path, mmap_mode="c", allow_pickle=False)
        if kind in ("dict", "list", "tuple"):
            values = [self._read(v, root) for v in node["items"]]
            return dict(values) if kind == "dict" else tuple(values) if kind == "tuple" else values
        if kind == "complex":
            return complex(node["real"], node["imag"])
        if kind == "float":
            return float(node["value"])
        if kind != "scalar":
            raise ValueError("Unknown cache encoding")
        return node["value"]


def cached_native(label, compute, inputs, revision):
    cache = _active_cache.get()
    return compute() if cache is None else cache.call(label, compute, inputs, revision)


def register_cache_object(obj, signature):
    cache = _active_cache.get()
    if cache is not None:
        cache.register(obj, signature)


def add_incremental_arguments(parser):
    parser.add_argument("--incremental", action="store_true", help="Reuse checked outputs and native-precision calculation caches; compute missing or changed results.")
    parser.add_argument("--cache-dir", help="Calculation cache directory outside public/. Default: .deepscope-cache at the project root.")
    parser.add_argument("--force", action="store_true", help="Recompute even with --incremental, refreshing its cache.")


def cache_directory(output, requested=None):
    output = Path(output).expanduser().resolve()
    if requested:
        root = Path(requested).expanduser().resolve()
    else:
        project = next((p for p in output.parents if (p / ".git").exists()), output.parent)
        root = project / ".deepscope-cache"
    if root == output or root.is_relative_to(output) or any(p.name == "public" for p in (root, *root.parents)):
        raise ValueError("--cache-dir must be outside the output bundle and public/.")
    return root


def _backend_identity(extra_files=()):
    versions = {}
    for name in ("numpy", "scipy", "shtns", "pyxshells", "h5py", "netCDF4", "magic"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    files = {str(Path(p).resolve()): file_digest(p) for p in extra_files if p and Path(p).is_file()}
    for name in ("shtns", "_shtns", "pyxshells", "magic.graph", "magic.libmagic", "magic.npfile", "magic.setup"):
        path = getattr(sys.modules.get(name), "__file__", None)
        if path and Path(path).is_file():
            files[str(Path(path).resolve())] = file_digest(path)
    return {"versions": versions, "files": files, "python": platform.python_version(),
            "machine": platform.machine(), "byteorder": sys.byteorder}


def run_conversion(args, kind, inputs, convert, *, backend_files=()):
    """Run one complete conversion or sequence, using its real (not staged) path."""
    output = Path(args.out).expanduser().resolve()
    sources = {str(Path(p).expanduser().resolve()): file_digest(p) for p in inputs if p is not None}
    backend = _backend_identity(backend_files)
    options = {k: v for k, v in vars(args).items() if k not in ("out", "incremental", "cache_dir", "force", "sequence_clear") and not k.startswith("_")}
    tools_root = Path(__file__).resolve().parent
    code = {p.name: file_digest(p) for p in sorted(tools_root.glob("*.py"))}
    request = _digest(_identity({"schema": CACHE_SCHEMA, "kind": kind, "sources": sources,
                                 "options": options, "backend": backend, "code": code}))
    incremental = bool(getattr(args, "incremental", False))
    force = bool(getattr(args, "force", False))
    if incremental and not force:
        try:
            saved = json.loads((output / MANIFEST).read_text())
            if saved["request"] == request and saved["files"] and all(
                file_digest(bundle_path(output, name)) == digest for name, digest in saved["files"].items()
            ):
                print(f"Unchanged validated conversion: {output}; skipped.", flush=True)
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
    root = cache_directory(output, getattr(args, "cache_dir", None)) if incremental else None
    cache = CalculationCache(root, {"kind": kind, "sources": sources, "backend": backend}, force) if incremental else None
    token = _active_cache.set(cache)
    original_output = args.out
    # Sequence children use stable cache paths, even while output is staged.
    args._incremental_source_root = str(output)
    if root is not None:
        args.cache_dir = str(root)
    try:
        with staged_bundle_output(output) as stage:
            args.out = str(stage)
            convert(args)
            validate_bundle(stage)
            # Never bless results if a source was overwritten during conversion.
            if any(file_digest(path) != digest for path, digest in sources.items()):
                raise ValueError("A simulation input changed during conversion; output was not replaced.")
            files = {str(p.relative_to(stage)): file_digest(p) for p in sorted(stage.rglob("*"))
                     if p.is_file() and p.name not in (MANIFEST, "view.DTV2")}
            (stage / MANIFEST).write_text(json.dumps({"version": CACHE_SCHEMA, "request": request,
                "source_sha256": sources, "files": files}, indent=2, allow_nan=False) + "\n")
    finally:
        args.out = original_output
        _active_cache.reset(token)
        if cache is not None:
            print(f"Calculation cache: {cache.hits} reused, {cache.misses} computed. {root}", flush=True)
