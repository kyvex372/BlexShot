"""Export only distributable source files; preserve the working directory."""
import ast
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = (
    ".editorconfig", ".gitattributes", ".gitignore", "README.md",
    "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md", "requirements.txt",
    "requirements-lock.txt", "main.py", "BlexShot.spec", "build.bat", "run.bat",
)
DIRECTORIES = {
    "snapforge": {".py"}, "tests": {".py"}, "tools": {".py"},
    "resources": {".png", ".ico", ".svg", ".manifest"},
    "docs": {".md", ".png"}, ".github": {".yml", ".yaml", ".md"},
}


def source_files():
    files = [ROOT / name for name in ROOT_FILES]
    for optional in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (ROOT / optional).is_file():
            files.append(ROOT / optional)
    for directory, suffixes in DIRECTORIES.items():
        for path in (ROOT / directory).rglob("*"):
            if (path.is_file() and path.suffix.lower() in suffixes
                    and "__pycache__" not in path.parts
                    and path.resolve().is_relative_to(ROOT)):
                files.append(path)
    return sorted(set(files))


def main():
    module = ast.parse((ROOT / "snapforge/__init__.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(node.value) for node in module.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(name, ast.Name) and name.id == "__version__"
                           for name in node.targets))
    output = ROOT / "exports" / f"BlexShot-source-v{version}.zip"
    output.parent.mkdir(exist_ok=True)
    files = source_files()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path("BlexShot") / path.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Source archive integrity check failed")
    print(f"Prepared {len(files)} files, {output.stat().st_size / 1024:.0f} KB")
    print(output)


if __name__ == "__main__":
    main()
