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

WRITING_MODULE_ROOT = Path(__file__).resolve().parents[2] / "app" / "modules" / "writing"


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
    directory = WRITING_MODULE_ROOT / subdirectory
    return sorted(directory.glob("*.py"))


def test_writing_domain_layer_has_no_framework_or_infrastructure_imports():
    for source_file in _source_files("domain"):
        imported = _imported_module_names(source_file)
        violations = {name for name in imported if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)}
        assert not violations, f"{source_file.name} imports forbidden module(s): {violations}"


def test_writing_application_layer_has_no_framework_or_concrete_infrastructure_imports():
    for source_file in _source_files("application"):
        imported = _imported_module_names(source_file)
        violations = {name for name in imported if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)}
        assert not violations, f"{source_file.name} imports forbidden module(s): {violations}"


def test_writing_domain_layer_does_not_import_other_modules_domain_entities():
    """Writing references Knowledge/Document/Agent only by integer id (chunk_id, document_id,
    agent_id) at the domain layer, never by importing their domain entities - keeps the
    module boundary real, not just a directory convention (ADR-003).
    """
    forbidden_prefixes = (
        "app.modules.knowledge",
        "app.modules.document",
        "app.modules.agent",
        "app.modules.project",
    )
    for source_file in _source_files("domain"):
        imported = _imported_module_names(source_file)
        violations = {name for name in imported if name.startswith(forbidden_prefixes)}
        assert not violations, f"{source_file.name} imports other modules' domain code: {violations}"
