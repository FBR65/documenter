# Python Auto-Docstring Generator

This script automatically generates Google-style docstrings (PEP 257) for Python functions, methods, and classes within a specified directory using a Large Language Model (LLM) accessed via an OpenAI-compatible API endpoint.

It recursively scans a starting directory, identifies Python files (`.py`), parses them using Abstract Syntax Trees (AST), detects functions/methods/classes lacking docstrings, generates docstrings using the configured LLM, and modifies the files in place.

## Features

*   Recursively finds `.py` files in a directory.
*   Uses AST to safely analyze and modify Python code structure.
*   Identifies functions, async functions, and classes without docstrings.
*   Connects to any OpenAI-compatible API endpoint.
*   Uses a specified LLM (e.g., `qwen3`, `granite3.3:8b`) to generate docstrings.
*   Generates docstrings in Google style.
*   Adds missing docstrings directly into the source files.
*   Handles basic file encoding issues (UTF-8 with Latin-1 fallback).
*   Validates generated code syntax before saving.
*   Provides verbose logging option.

## Prerequisites

*   **Python:** Version 3.8 or newer (required for `ast.get_source_segment`).
*   **LLM Endpoint:** Access to an OpenAI-compatible API endpoint (e.g., Ollama, vLLM, a cloud provider).
*   **API Key (Optional):** An API key might be required depending on your endpoint's configuration.

## Installation

1.  **Clone or download the script:** Save the code as `main.py`.
2.  **Install dependencies:**
    ```bash
    uv sync
    ```

## Configuration

1.  **API Endpoint & Model:**
    *   You can modify the `DEFAULT_BASE_URL` and `DEFAULT_MODEL` constants directly in the `main.py` script.
    *   Alternatively, use the command-line arguments `--base-url` and `--model` when running the script (see Usage).
2.  **API Key:**
    *   The script will look for the API key in the `OPENAI_API_KEY` environment variable.
        ```bash
        # Linux/macOS
        export OPENAI_API_KEY="your_api_key_here"

        # Windows (Command Prompt)
        set OPENAI_API_KEY="your_api_key_here"

        # Windows (PowerShell)
        $env:OPENAI_API_KEY="your_api_key_here"
        ```
    *   You can also provide the key directly using the `--api-key` command-line argument.
    *   If your endpoint does not require authentication, you can ignore this step (a dummy key will be used).

## Usage

**Important:** **Always back up your code before running this script**, as it modifies files directly!

Run the script from your terminal, providing the path to the directory containing the Python code you want to document.

**Basic Usage (using defaults or environment variables):**

```bash
python main.py /path/to/your/project
```

Specifying Endpoint, Model, and API Key:

```bash
python main.py /path/to/your/project --base-url http://your-llm-endpoint:8000/v1 --model your-model-name:latest --api-key sk-your-key-here
```

Using Verbose Mode for Detailed Logs:

```bash
python main.py /path/to/your/project -v
```

The script will log its progress, indicating which files are being processed, which functions/classes are getting docstrings generated, and any errors encountered. At the end, it will summarize the number of files processed.

## How it Works
* File Discovery: Walks through the specified start_dir.

* AST Parsing: Reads each .py file and parses it into an Abstract Syntax Tree (AST).

* Node Visiting: Uses an ast.NodeTransformer (DocstringAdder) to visit function, async function, and class definition nodes.

* Docstring Check: Checks if a node already has a docstring using ast.get_docstring.

* Code Extraction: If a docstring is missing, extracts the source code snippet for that node using ast.get_source_segment.

* LLM Interaction: Sends the code snippet and a specific prompt to the configured LLM via the openai client, requesting a Google-style docstring.

* Docstring Insertion: If the LLM returns a valid docstring, creates a new AST node for the docstring and inserts it into the node's body.

* Code Regeneration: Uses astor.to_source to convert the modified AST back into Python code.

* Validation & Saving: Parses the generated code to check for syntax errors before overwriting the original file.

## Important Notes

* Backup: Seriously, back up your code first.

* Docstring Quality: The quality of the generated docstrings heavily depends on the capability of the LLM used and the effectiveness of the prompt. You might need to tweak the prompt inside the generate_docstring function for better results.

* Idempotency: The script currently only adds missing docstrings. It does not overwrite existing ones. Running it multiple times on the same codebase should ideally only add docstrings the first time (unless errors occurred).

* Costs & Rate Limits: Be mindful of potential costs and API rate limits associated with your LLM endpoint, especially when running on large codebases.

* Error Handling: Basic error handling for file I/O, API calls, and AST processing is included, but complex or unusual code structures might cause issues. Check the logs for details.

## License

AGPLv3 as written in LICENSE.md 