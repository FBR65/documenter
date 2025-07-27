import os
import ast
import logging
from typing import List, Dict, Any, Optional


def extract_info_from_node(
    node: ast.AST, source_code: str, filename: str
) -> Dict[str, Any]:
    """Extrahiert Informationen aus einem AST-Knoten."""
    info = {
        "type": type(node).__name__,
        "name": getattr(node, "name", ""),
        "docstring": ast.get_docstring(node) or "",
        "lineno": getattr(node, "lineno", 0),
        "code": ast.get_source_segment(source_code, node) or "",
        "args": [],
        "returns": None,
        "raises": [],
    }

    # Extrahiere Argumente für Funktionen und Methoden
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        info["args"] = [arg.arg for arg in node.args.args]
        # Einfache Extraktion von Rückgabewerten und Raises aus dem Docstring
        # In einer echten Implementierung wäre eine detailliertere Analyse des Docstrings notwendig
        # oder das Parsen des Funktionskörpers auf `raise`-Statements.
        # Für diese Implementierung konzentrieren wir uns auf den Docstring.
        # Ein vollständigerer Parser für Google-Style Docstrings wäre ein eigener Task.
        # Wir nehmen an, dass der Docstring bereits Google-Style ist.
        # TODO: Implementiere einen Google-Style Docstring Parser.
        # Als Platzhalter könnten wir den Docstring analysieren, um Returns und Raises zu finden.
        # Dies ist eine Vereinfachung.
        docstring = info["docstring"]
        if "Returns:" in docstring:
            # Extrahiere die Zeile nach "Returns:"
            lines = docstring.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("Returns:"):
                    if i + 1 < len(lines):
                        info["returns"] = lines[i + 1].strip()
                    break
        if "Raises:" in docstring:
            # Extrahiere die Zeilen nach "Raises:"
            lines = docstring.split("\n")
            collecting = False
            for line in lines:
                if line.strip().startswith("Raises:"):
                    collecting = True
                    continue
                if collecting:
                    if line.strip() and not line.startswith(" "):
                        # Neuer Abschnitt begonnen
                        break
                    if line.strip():
                        # Füge die Exception hinzu (Annahme: Format ist `ExceptionType: Beschreibung`)
                        # Entferne führende Leerzeichen
                        stripped_line = line.strip()
                        # Extrahiere den Typ (alles vor dem ersten Doppelpunkt)
                        if ":" in stripped_line:
                            exc_type = stripped_line.split(":", 1)[0].strip()
                            info["raises"].append(exc_type)
                        else:
                            # Falls kein Doppelpunkt, nimm die ganze Zeile als Typ
                            info["raises"].append(stripped_line)

    return info


class DocInfoExtractor(ast.NodeVisitor):
    """Ein AST-Visitor, der Informationen über Module, Klassen, Funktionen und Methoden sammelt."""

    def __init__(self, filename: str, source_code: str):
        self.filename = filename
        self.source_code = source_code
        self.info: List[Dict[str, Any]] = []
        # Speichere das Modul-Docstring
        self.module_docstring = ast.get_docstring(ast.parse(source_code)) or ""

    def visit_Module(self, node: ast.Module):
        # Füge Modul-Informationen hinzu
        self.info.append(
            {
                "type": "Module",
                "name": os.path.basename(self.filename),
                "docstring": self.module_docstring,
                "lineno": 1,  # Module hat keine lineno, setzen wir auf 1
                "code": "",  # Modulcode ist schwer zu extrahieren, leer lassen
                "args": [],
                "returns": None,
                "raises": [],
            }
        )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.info.append(extract_info_from_node(node, self.source_code, self.filename))
        self.generic_visit(node)  # Besuche Kindknoten (z.B. verschachtelte Funktionen)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.info.append(extract_info_from_node(node, self.source_code, self.filename))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.info.append(extract_info_from_node(node, self.source_code, self.filename))
        self.generic_visit(node)  # Besuche Kindknoten (Methoden)


def generate_docs_for_file(filepath: str, output_dir: str):
    """Generiert Sphinx/MkDocs-kompatiblen Output für eine einzelne Python-Datei."""
    logging.info(f"Generiere Dokumentation für: {filepath}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source_code = f.read()
    except Exception as e:
        logging.error(f"Fehler beim Lesen von '{filepath}': {e}")
        return

    try:
        # Extrahiere Informationen
        extractor = DocInfoExtractor(filepath, source_code)
        tree = ast.parse(source_code)
        extractor.visit(tree)

        # Generiere Output (z.B. Markdown)
        # Dateiname für die Ausgabe: z.B. mymodule.md
        base_filename = os.path.splitext(os.path.basename(filepath))[0]
        output_filename = f"{base_filename}.md"
        output_path = os.path.join(output_dir, output_filename)

        # Stelle sicher, dass das Ausgabeverzeichnis existiert
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            # Schreibe Modul-Docstring als Titel und Beschreibung
            module_info = next(
                (item for item in extractor.info if item["type"] == "Module"), None
            )
            if module_info:
                f.write(f"# {module_info['name']}\n\n")
                if module_info["docstring"]:
                    f.write(f"{module_info['docstring']}\n\n")

            # Schreibe Informationen für Funktionen, Klassen, Methoden
            # Gruppiere nach Typ für bessere Lesbarkeit
            functions = [
                item
                for item in extractor.info
                if item["type"] in ["FunctionDef", "AsyncFunctionDef"]
            ]
            classes = [item for item in extractor.info if item["type"] == "ClassDef"]

            if functions:
                f.write("## Funktionen\n\n")
                for func in functions:
                    f.write(f"### {func['name']}\n\n")
                    if func["docstring"]:
                        f.write(f"{func['docstring']}\n\n")
                    f.write(f"```python\n{func['code']}\n```\n\n")

            if classes:
                f.write("## Klassen\n\n")
                for cls in classes:
                    f.write(f"### {cls['name']}\n\n")
                    if cls["docstring"]:
                        f.write(f"{cls['docstring']}\n\n")
                    f.write(f"```python\n{cls['code']}\n```\n\n")
                    # TODO: Füge Methoden der Klasse hinzu

        logging.info(
            f"Dokumentation für '{filepath}' gespeichert unter '{output_path}'."
        )

    except SyntaxError as e:
        logging.error(f"Syntaxfehler beim Parsen von '{filepath}': {e}")
    except Exception as e:
        logging.error(f"Fehler beim Generieren der Dokumentation für '{filepath}': {e}")


def generate_docs(start_dir: str, output_dir: str):
    """Generiert Sphinx/MkDocs-kompatiblen Output für ein Verzeichnis."""
    logging.info(
        f"Starte Generierung der Dokumentation in '{output_dir}' für Dateien in '{start_dir}'..."
    )

    # Stelle sicher, dass das Ausgabeverzeichnis existiert
    os.makedirs(output_dir, exist_ok=True)

    file_count = 0
    for root, dirs, files in os.walk(start_dir):
        # Optional: Verzeichnisse ausschließen (z.B. .venv, .git, __pycache__)
        dirs[:] = [
            d for d in dirs if d not in [".venv", ".git", "__pycache__", "venv", "env"]
        ]

        for filename in files:
            if (
                filename.endswith(".py") and filename != "__init__.py"
            ):  # __init__.py oft leer, überspringen
                filepath = os.path.join(root, filename)
                generate_docs_for_file(filepath, output_dir)
                file_count += 1

    logging.info(
        f"Dokumentationsgenerierung abgeschlossen. {file_count} Dateien verarbeitet."
    )
