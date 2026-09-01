from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_FILES = [
    ROOT / "src/dublocal/__init__.py",
    ROOT / "src/dublocal/launcher_runtime.py",
    ROOT / "src/dublocal/production_ui.py",
    ROOT / "src/dublocal/production_pipeline.py",
    ROOT / "src/dublocal/production_queue.py",
    ROOT / "src/dublocal/production_course.py",
    ROOT / "src/dublocal/voice_engine.py",
    ROOT / "src/dublocal/voice_selection.py",
    ROOT / "src/dublocal/voice_timing.py",
]

LEGACY_OVERLAY_IMPORTS = {
    "product_ui",
    "detailed_ui",
    "commercial_ui",
    "cancellation_ui",
    "course_import_ui",
    "output_profiles_ui",
    "storage_cleanup_ui",
    "translation_performance",
    "native_tts_timing",
    "hungarian_tts_integration",
    "language_extensions",
    "transcription_v053",
    "v060_refinements",
}


def _root_name(node: ast.expr) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def test_package_import_is_metadata_only() -> None:
    tree = ast.parse((ROOT / "src/dublocal/__init__.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert calls == []
    assert imports == []


def test_production_composition_does_not_import_legacy_overlay_installers() -> None:
    for path in PRODUCTION_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        assert imported.isdisjoint(LEGACY_OVERLAY_IMPORTS), (path.name, imported & LEGACY_OVERLAY_IMPORTS)


def test_production_path_never_assigns_into_imported_modules_or_gradio() -> None:
    """Reject the old ``module.function = wrapper`` / ``gr.Component = factory`` pattern."""

    for path in PRODUCTION_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_names: set[str] = {"gr"}
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_names.update(alias.asname or alias.name for alias in node.names)

        offenders: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                if isinstance(node, ast.Assign):
                    targets.extend(node.targets)
                else:
                    targets.append(node.target)
            for target in targets:
                if isinstance(target, ast.Attribute) and _root_name(target) in imported_names:
                    offenders.append((node.lineno, ast.unparse(target)))
        assert offenders == [], (path.name, offenders)


def test_launcher_has_one_explicit_ui_composition_root() -> None:
    source = (ROOT / "src/dublocal/launcher_runtime.py").read_text(encoding="utf-8")
    assert "from .production_ui import MATRIX_CSS, build_app" in source
    assert "install_translation_performance_refinement" not in source
    assert "install_output_profile_runtime" not in source
    assert "install_commercial_ui" not in source
    assert "install_cancellation_ui" not in source
    assert "install_course_import_ui" not in source
