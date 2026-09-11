import ast
from pathlib import Path

FORBIDDEN_IMPORTS = {
    "fastapi",
    "sqlalchemy",
    "httpx",
    "bcrypt",
    "app.storage.filesystem",
    "app.ai.providers.openai_compatible",
    "app.ai.providers.google_genai",
    "google",
}

KNOWLEDGE_MODULE_ROOT = Path(__file__).resolve().parents[2] / "app" / "modules" / "knowledge"


def _imported_module_names(source_file: Path) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _source_files(subdirectory: str) -> list[Path]:
    directory = KNOWLEDGE_MODULE_ROOT / subdirectory
    return sorted(directory.glob("*.py"))


def test_knowledge_domain_layer_has_no_framework_or_infrastructure_imports():
    for source_file in _source_files("domain"):
        imported = _imported_module_names(source_file)
        violations = {name for name in imported if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)}
        assert not violations, f"{source_file.name} imports forbidden module(s): {violations}"


def test_knowledge_application_layer_has_no_framework_or_concrete_infrastructure_imports():
    for source_file in _source_files("application"):
        imported = _imported_module_names(source_file)
        violations = {name for name in imported if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)}
        assert not violations, f"{source_file.name} imports forbidden module(s): {violations}"
