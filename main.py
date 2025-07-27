import os
import argparse
import ast
import logging
from openai import OpenAI, OpenAIError

# Importiere das neue Modul für die Dokumentationserstellung
import doc_generator

# Importiere astor oder verwende ast.unparse falls verfügbar (Python 3.9+)
try:
    import astor

    _use_astor = True
except ImportError:
    _use_astor = False
    # Prüfe, ob ast.unparse verfügbar ist (Python 3.9+)
    if not hasattr(ast, "unparse"):
        raise ImportError(
            "Das Modul 'astor' ist nicht installiert und 'ast.unparse' ist nicht verfügbar. "
            "Bitte installiere 'astor' oder verwende Python 3.9 oder höher."
        )

# --- Konfiguration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
# Standard-Modell (kann über CLI überschrieben werden)
DEFAULT_MODEL = (
    "freehuntx/qwen3-coder:8b"  # Passe dies an, falls dein Modell anders heißt
)
# Standard-Endpunkt (kann über CLI überschrieben werden)
# Ersetze dies ggf. durch die tatsächliche URL deines lokalen Endpunkts
DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Beispiel für einen lokalen Endpunkt

# --- Kernlogik ---


def get_llm_client(api_key: str | None, base_url: str) -> OpenAI | None:
    """Initialisiert den OpenAI-Client."""
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logging.warning(
                "Kein OpenAI API Key gefunden (weder als Argument noch in der Umgebungsvariable OPENAI_API_KEY). LLM-Aufrufe werden fehlschlagen, wenn der Endpunkt eine Authentifizierung erfordert."
            )
            # Manche lokale Endpunkte benötigen keinen Key
            api_key = "dummy-key"  # Platzhalter

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        # Teste die Verbindung (optional, aber gut für frühes Feedback)
        # client.models.list() # Kann bei manchen Endpunkten fehlschlagen
        logging.info(f"OpenAI-Client für Basis-URL {base_url} initialisiert.")
        return client
    except Exception as e:
        logging.error(f"Fehler beim Initialisieren des OpenAI-Clients: {e}")
        return None


def generate_docstring(
    client: OpenAI | None,
    code_snippet: str,
    model: str,
    filename: str,
    node_name: str,
) -> str | None:
    """Generiert einen Docstring für einen Code-Schnipsel mittels LLM."""
    if not client:
        logging.error(
            "OpenAI-Client ist nicht initialisiert. Überspringe Docstring-Generierung."
        )
        return None

    prompt = f"""
Generiere einen prägnanten und informativen Google-Style Docstring (gemäß PEP 257) für die folgende Python-Funktion/Methode/Klasse aus der Datei '{filename}'.
Der Docstring sollte die Funktionalität, Argumente (Args:), Rückgabewerte (Returns:) und ausgelöste Ausnahmen (Raises:) beschreiben, falls zutreffend.
Gib NUR den Docstring selbst zurück, ohne zusätzliche Erklärungen oder Code-Backticks.

Code:
```python
{code_snippet}

Docstring: 
"""

    try:
        logging.info(
            f"Generiere Docstring für '{node_name}' in '{filename}' mit Modell '{model}'..."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein Assistent, der Google-Style Python-Docstrings generiert.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
        docstring = response.choices[0].message.content.strip()

        # Bereinigung: Manchmal fügen LLMs trotzdem Backticks oder Einleitungen hinzu
        if docstring.startswith('"""') and docstring.endswith('"""'):
            docstring = docstring[3:-3].strip()
        elif docstring.startswith("'''") and docstring.endswith("'''"):
            docstring = docstring[3:-3].strip()
        if docstring.lower().startswith("docstring:"):
            docstring = docstring[len("docstring:") :].strip()

        # Stelle sicher, dass ein leerer String nicht als gültiger Docstring zurückgegeben wird
        if not docstring:
            logging.warning(
                f"LLM hat einen leeren Docstring für '{node_name}' zurückgegeben."
            )
            # Hier war der Fehler: return None sollte nur hier stehen, wenn der String leer IST.
            return None
        # Wenn der Docstring nicht leer ist, logge Erfolg und gib ihn zurück.
        logging.info(f"Docstring für '{node_name}' erfolgreich generiert.")
        return docstring  # Nur den Inhalt zurückgeben

    except OpenAIError as e:
        logging.error(
            f"OpenAI API Fehler beim Generieren des Docstrings für '{node_name}': {e}"
        )
    except Exception as e:
        logging.error(
            f"Unerwarteter Fehler beim Generieren des Docstrings für '{node_name}': {e}"
        )

    # Wird nur erreicht, wenn eine Exception im try-Block aufgetreten ist
    return None


class DocstringAdder(ast.NodeTransformer):
    """Ein AST-Transformer, der fehlende Docstrings zu Funktionen, Klassen und Methoden hinzufügt."""

    # Korrekter Konstruktor-Name: __init__
    def __init__(self, client: OpenAI | None, model: str, filename: str):
        super().__init__()  # Gute Praxis: Initializer der Basisklasse aufrufen
        self.client = client
        self.model = model
        self.filename = filename
        self.modified = False  # Flag, um zu verfolgen, ob Änderungen vorgenommen wurden
        self.original_source = ""  # Initialisieren, wird in add_docstrings gesetzt

    def _add_docstring_if_missing(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ):
        """Hilfsfunktion zum Hinzufügen von Docstrings."""
        # Stelle sicher, dass original_source gesetzt ist
        if not self.original_source:
            logging.error(
                f"Interner Fehler: original_source nicht gesetzt für Datei {self.filename}"
            )
            return node  # Keine Änderung möglich

        node_name = getattr(node, "name", "unbekannt")
        if not ast.get_docstring(node, clean=False):
            logging.info(
                f"Fehlender Docstring für '{node_name}' in '{self.filename}' entdeckt."
            )
            try:
                source_snippet = ast.get_source_segment(self.original_source, node)
                if not source_snippet:
                    logging.warning(
                        f"Konnte Quellcode-Segment für '{node_name}' nicht extrahieren."
                    )
                    # Wichtig: Trotzdem generic_visit aufrufen, um Kindknoten zu bearbeiten!
                    return self.generic_visit(node)

                # Bestimme, ob es sich um eine Klasse handelt, für den node_name im Log
                display_node_name = (
                    f"Klasse {node_name}"
                    if isinstance(node, ast.ClassDef)
                    else node_name
                )

                generated_docstring_content = generate_docstring(
                    self.client,
                    source_snippet,
                    self.model,
                    self.filename,
                    display_node_name,
                )

                if generated_docstring_content:
                    # Keine Notwendigkeit, hier Anführungszeichen zu entfernen,
                    # da generate_docstring nur den Inhalt zurückgibt.
                    docstring_value = generated_docstring_content  # Bereits bereinigt

                    docstring_node = ast.Expr(value=ast.Constant(value=docstring_value))
                    node.body.insert(0, docstring_node)
                    self.modified = True
                    logging.info(f"Docstring für '{display_node_name}' hinzugefügt.")
                else:
                    logging.warning(
                        f"Konnte keinen Docstring für '{display_node_name}' generieren oder LLM gab leeren String zurück."
                    )

            except Exception as e:
                logging.error(
                    f"Fehler beim Verarbeiten von '{node_name}' in '{self.filename}': {e}"
                )
        else:
            logging.debug(
                f"Docstring für '{node_name}' in '{self.filename}' bereits vorhanden."
            )

        # Wichtig: Immer generic_visit aufrufen, um Kindknoten (z.B. Methoden in Klassen) zu besuchen
        return self.generic_visit(node)

    # --- Korrekt eingerückte Methoden ---
    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Ruft _add_docstring_if_missing auf, welches generic_visit am Ende aufruft
        return self._add_docstring_if_missing(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Ruft _add_docstring_if_missing auf, welches generic_visit am Ende aufruft
        return self._add_docstring_if_missing(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Ruft _add_docstring_if_missing auf.
        # _add_docstring_if_missing fügt zuerst den Klassen-Docstring hinzu (falls fehlend)
        # und ruft dann generic_visit auf, um die Methoden *innerhalb* der Klasse zu besuchen.
        return self._add_docstring_if_missing(node)

    def add_docstrings(self, source_code: str) -> str | None:
        """Parst den Code, fügt Docstrings hinzu und gibt den modifizierten Code zurück."""
        self.original_source = source_code  # Speichern für get_source_segment
        self.modified = False  # Reset modified flag for each file
        try:
            tree = ast.parse(source_code)
            modified_tree = self.visit(tree)  # Startet den Besuchsprozess
            if self.modified:
                ast.fix_missing_locations(modified_tree)
                # Verwende ast.unparse (Python 3.9+) oder astor, je nach Verfügbarkeit
                if _use_astor:
                    return astor.to_source(modified_tree)
                else:
                    return ast.unparse(modified_tree)
            else:
                logging.debug(
                    f"Keine Änderungen am AST für '{self.filename}' vorgenommen."
                )
                return None
        except SyntaxError as e:
            logging.error(f"Syntaxfehler beim Parsen von '{self.filename}': {e}")
            return None
        except Exception as e:
            logging.error(f"Fehler beim Verarbeiten der AST für '{self.filename}': {e}")
            return None


def process_file(
    filepath: str, client: OpenAI | None, model: str, overwrite: bool = False
):
    """Liest eine Datei, fügt Docstrings hinzu und schreibt sie zurück."""
    logging.info(f"Verarbeite Datei: {filepath}")
    original_content = None
    encoding_to_use = "utf-8"  # Standard-Kodierung

    # --- Datei lesen mit Fallback ---
    try:
        with open(filepath, "r", encoding=encoding_to_use) as f:
            original_content = f.read()
    except UnicodeDecodeError:
        logging.warning(
            f"Konnte '{filepath}' nicht als UTF-8 lesen, versuche 'latin-1'."
        )
        encoding_to_use = "latin-1"  # Wechsle zur Fallback-Kodierung
        try:
            with open(filepath, "r", encoding=encoding_to_use) as f:
                original_content = f.read()
        except Exception as e:
            logging.error(
                f"Fehler beim Lesen von '{filepath}' auch mit '{encoding_to_use}': {e}"
            )
            return  # Datei kann nicht verarbeitet werden
    except FileNotFoundError:
        logging.error(f"Datei nicht gefunden: {filepath}")
        return
    except IOError as e:
        logging.error(f"E/A-Fehler beim Lesen von '{filepath}': {e}")
        return
    except Exception as e:
        # Fängt andere unerwartete Fehler beim Lesen ab
        logging.error(f"Unerwarteter Fehler beim Lesen von '{filepath}': {e}")
        return

    # Wenn das Lesen fehlschlug (z.B. FileNotFoundError), ist original_content None
    if original_content is None:
        # Fehler wurde bereits geloggt, hier nur zur Sicherheit
        logging.debug(
            f"Überspringe Verarbeitung von '{filepath}', da Inhalt nicht gelesen werden konnte."
        )
        return

    # --- Docstrings hinzufügen und Datei schreiben ---
    try:
        # Stelle sicher, dass der Client übergeben wird, auch wenn er None ist
        adder = DocstringAdder(client, model, filepath)
        new_content = adder.add_docstrings(original_content)

        if new_content:
            # Sicherheitsprüfung: Stelle sicher, dass der neue Inhalt gültiger Python-Code ist
            try:
                ast.parse(new_content)
                logging.info(
                    f"Änderungen in '{filepath}' vorgenommen. Schreibe Datei neu mit Kodierung '{encoding_to_use}'."
                )
                # Schreibe mit der Kodierung zurück, die beim Lesen funktioniert hat
                with open(filepath, "w", encoding=encoding_to_use) as f:
                    f.write(new_content)
            except SyntaxError as e:
                logging.error(
                    f"FEHLER: Generierter Code für '{filepath}' enthält Syntaxfehler und wird NICHT geschrieben: {e}"
                )
                logging.error("--- Generierter Code (Auszug) ---")
                logging.error(new_content[:1000] + "...")
                logging.error("--- Ende Auszug ---")
            except Exception as e:
                logging.error(
                    f"Unerwarteter Fehler beim Schreiben oder Validieren von '{filepath}': {e}"
                )

        else:
            # Unterscheide, ob keine Änderungen nötig waren oder ob Fehler auftraten
            if adder.modified is False:
                logging.info(
                    f"Keine fehlenden Docstrings gefunden oder keine Änderungen in '{filepath}'."
                )
            # Andere Fehler (z.B. LLM-Fehler) wurden bereits im Adder geloggt

    except Exception as e:
        # Fängt unerwartete Fehler während der AST-Verarbeitung oder LLM-Aufrufen ab
        logging.error(
            f"Unerwarteter Fehler bei der Verarbeitung von '{filepath}' (AST/LLM): {e}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Fügt automatisch Google-Style Docstrings zu Python-Dateien hinzu.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,  # Zeigt Standardwerte in --help
    )  # <- Schließende Klammer für ArgumentParser hier
    parser.add_argument(
        "start_dir",
        help="Das Startverzeichnis, ab dem rekursiv nach .py-Dateien gesucht wird.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Name des LLM-Modells")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Basis-URL des OpenAI-kompatiblen Endpunkts",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API Key (optional, liest sonst OPENAI_API_KEY Umgebungsvariable)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Ausführlichere Log-Ausgaben (DEBUG Level)",
    )
    parser.add_argument(
        "--doc-output-dir",
        default=None,
        help="Verzeichnis für die generierte Sphinx/MkDocs-kompatible Dokumentation (optional).",
    )
    # parser.add_argument("--overwrite", action="store_true", help="Überschreibt auch vorhandene Docstrings (Standard: nur fehlende hinzufügen)") # Zukünftige Option

    args = parser.parse_args()

    # Logging-Level anpassen, falls -v gesetzt ist
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose-Modus aktiviert.")

    if not os.path.isdir(args.start_dir):
        logging.error(
            f"Fehler: Das angegebene Startverzeichnis '{args.start_dir}' existiert nicht oder ist kein Verzeichnis."
        )
        return  # Beende die Funktion hier, da das Verzeichnis ungültig ist

    # Initialisiere den LLM-Client einmal
    client = get_llm_client(args.api_key, args.base_url)
    # Wir brechen nicht mehr ab, wenn der Client nicht initialisiert werden kann,
    # da generate_docstring dies prüft und Fehler loggt. Das Skript kann dann
    # zumindest die Dateistruktur durchlaufen.

    logging.info(
        f"Starte Suche nach .py-Dateien in '{os.path.abspath(args.start_dir)}'..."
    )
    file_count = 0
    processed_count = 0
    for root, dirs, files in os.walk(args.start_dir):
        # Optional: Verzeichnisse ausschließen (z.B. .venv, .git, __pycache__)
        dirs[:] = [
            d for d in dirs if d not in [".venv", ".git", "__pycache__", "venv", "env"]
        ]

        for filename in files:
            if filename.endswith(".py"):
                filepath = os.path.join(root, filename)
                # Stelle sicher, dass der Client übergeben wird, auch wenn er None ist
                process_file(filepath, client, args.model)  # , args.overwrite)
                processed_count += 1  # Zähle jede versuchte Verarbeitung
        # Korrekte Einrückung für die Zählung der gefundenen Dateien
        file_count += len(
            [f for f in files if f.endswith(".py")]
        )  # Zähle gefundene .py Dateien

    logging.info(
        f"Verarbeitung abgeschlossen. {processed_count} .py-Dateien verarbeitet (von {file_count} gefundenen)."
    )

    # Generiere Sphinx/MkDocs-kompatible Dokumentation, falls ein Ausgabeverzeichnis angegeben wurde
    if args.doc_output_dir:
        logging.info(
            f"Starte Generierung der Sphinx/MkDocs-Dokumentation in '{args.doc_output_dir}'..."
        )
        try:
            doc_generator.generate_docs(args.start_dir, args.doc_output_dir)
            logging.info("Sphinx/MkDocs-Dokumentation erfolgreich generiert.")
        except Exception as e:
            logging.error(
                f"Fehler bei der Generierung der Sphinx/MkDocs-Dokumentation: {e}"
            )


# Korrekte Einrückung für den if __name__ == "__main__": Block
if __name__ == "__main__":
    # Setze den CWD auf das Verzeichnis des Skripts, um relative Pfade robuster zu machen (optional)
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    # os.chdir(script_dir)
    main()
