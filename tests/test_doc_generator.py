import unittest
import tempfile
import os
import sys

# Füge das Verzeichnis mit dem Hauptskript zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import doc_generator


class TestDocGenerator(unittest.TestCase):
    def setUp(self):
        # Erstelle ein temporäres Verzeichnis für Tests
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "docs")

        # Erstelle eine Beispiel-Python-Datei
        self.sample_file = os.path.join(self.test_dir, "sample.py")
        with open(self.sample_file, "w") as f:
            f.write('''
"""Modul Docstring"""

def sample_function(arg1, arg2):
    """Funktion Docstring."""
    return arg1 + arg2

class SampleClass:
    """Klassen Docstring."""
    
    def sample_method(self, arg):
        """Methode Docstring."""
        return arg
''')

    def tearDown(self):
        # Entferne das temporäre Verzeichnis nach dem Test
        import shutil

        shutil.rmtree(self.test_dir)

    def test_generate_docs(self):
        # Teste die Dokumentationserstellung
        doc_generator.generate_docs(self.test_dir, self.output_dir)

        # Überprüfe, ob die Ausgabedatei erstellt wurde
        output_file = os.path.join(self.output_dir, "sample.md")
        self.assertTrue(os.path.exists(output_file))

        # Überprüfe den Inhalt der Ausgabedatei
        with open(output_file, "r") as f:
            content = f.read()

        # Überprüfe, ob der Modulname im Titel steht
        self.assertIn("# sample.py", content)
        # Überprüfe, ob das Modul-Docstring vorhanden ist
        self.assertIn("Modul Docstring", content)
        # Überprüfe, ob die Funktion dokumentiert ist
        self.assertIn("## Funktionen", content)
        self.assertIn("### sample_function", content)
        self.assertIn("Funktion Docstring.", content)
        # Überprüfe, ob die Klasse dokumentiert ist
        self.assertIn("## Klassen", content)
        self.assertIn("### SampleClass", content)
        self.assertIn("Klassen Docstring.", content)


if __name__ == "__main__":
    unittest.main()
