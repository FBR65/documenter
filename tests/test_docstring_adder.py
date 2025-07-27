import unittest
import tempfile
import os
import sys

# Füge das Verzeichnis mit dem Hauptskript zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import DocstringAdder, get_llm_client, generate_docstring


# Mock für den OpenAI-Client
class MockClient:
    def __init__(self):
        pass


# Mock für die LLM-Antwort
class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]


class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)


class MockMessage:
    def __init__(self, content):
        self.content = content


# Mock für OpenAIError
class MockOpenAIError(Exception):
    pass


# Patchen der Module
import main

main.OpenAI = MockClient
main.OpenAIError = MockOpenAIError


def mock_get_llm_client(api_key, base_url):
    return MockClient()


def mock_generate_docstring(client, code_snippet, model, filename, node_name):
    # Einfache Simulation eines Docstrings basierend auf dem Namen
    if "test_func" in node_name:
        return "Test function docstring."
    elif "TestClass" in node_name:
        return "Test class docstring."
    elif "test_method" in node_name:
        return "Test method docstring."
    else:
        return "Default docstring."


# Überschreibe die Funktionen mit den Mocks
main.get_llm_client = mock_get_llm_client
main.generate_docstring = mock_generate_docstring


class TestDocstringAdder(unittest.TestCase):
    def setUp(self):
        self.client = MockClient()
        self.model = "test-model"
        self.filename = "test_file.py"

    def test_add_docstring_to_function(self):
        source_code = "def test_func():\n    pass\n"
        adder = DocstringAdder(self.client, self.model, self.filename)
        new_code = adder.add_docstrings(source_code)

        expected = 'def test_func():\n    """Test function docstring."""\n    pass\n'
        self.assertEqual(new_code, expected)

    def test_add_docstring_to_class(self):
        source_code = "class TestClass:\n    def method(self):\n        pass\n"
        adder = DocstringAdder(self.client, self.model, self.filename)
        new_code = adder.add_docstrings(source_code)

        # Der DocstringAdder fügt auch Docstrings zu Methoden innerhalb der Klasse hinzu
        expected = 'class TestClass:\n    """Test class docstring."""\n\n    def method(self):\n        """Default docstring."""\n        pass\n'
        self.assertEqual(new_code, expected)

    def test_add_docstring_to_method(self):
        source_code = "class TestClass:\n    def test_method(self):\n        pass\n"
        adder = DocstringAdder(self.client, self.model, self.filename)
        new_code = adder.add_docstrings(source_code)

        expected = 'class TestClass:\n    """Test class docstring."""\n\n    def test_method(self):\n        """Test method docstring."""\n        pass\n'
        self.assertEqual(new_code, expected)

    def test_do_not_overwrite_existing_docstring(self):
        source_code = 'def test_func():\n    """Existing docstring."""\n    pass\n'
        adder = DocstringAdder(self.client, self.model, self.filename)
        new_code = adder.add_docstrings(source_code)

        # Der Code sollte unverändert bleiben
        self.assertIsNone(new_code)

    def test_syntax_validity(self):
        source_code = "def test_func():\n    pass\n"
        adder = DocstringAdder(self.client, self.model, self.filename)
        new_code = adder.add_docstrings(source_code)

        # Versuche, den generierten Code zu parsen
        import ast

        try:
            ast.parse(new_code)
        except SyntaxError:
            self.fail("Der generierte Code ist nicht syntaktisch korrekt.")


if __name__ == "__main__":
    unittest.main()
