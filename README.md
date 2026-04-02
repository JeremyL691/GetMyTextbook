# Website Textbook Extraction Tool

This project exports online textbooks and course notes into a single offline PDF.

It is designed for documentation-style textbook websites rather than arbitrary web pages. The current implementation supports:

- MyST-based textbook sites
- GitBook-based textbook sites

`Data C100` and `CS 61B` are included as built-in presets, but the main goal of the tool is broader textbook extraction from other supported websites.

## What it does

- Detects whether a custom textbook URL is powered by MyST or GitBook
- Discovers the book structure from the live website
- Fetches the latest chapter HTML for custom URL runs
- Downloads and compresses images for PDF output
- Merges the full book into one PDF file
- Optionally saves a debug HTML file before PDF rendering

## Current support

Built-in presets:

- `Data C100`
- `CS 61B`

Custom URL mode:

- Supported: MyST textbook websites
- Supported: GitBook textbook websites
- Not supported: arbitrary websites outside those two documentation systems

## Requirements

- Python 3.11+
- A working WeasyPrint environment
- The Python packages listed in `requirements.txt`

On macOS, WeasyPrint may require Homebrew libraries such as `pango`, `glib`, and related dependencies.

## Installation

```bash
git clone https://github.com/JeremyL691/GetMyTextbook.git
cd GetMyTextbook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Interactive mode:

```bash
python3 app.py
```

The menu offers:

- `1. Data C100`
- `2. CS 61B`
- `3. Custom URL (MyST or GitBook)`

Direct preset commands:

```bash
python3 app.py ds100
python3 app.py cs61b
```

Custom URL mode:

```bash
python3 app.py custom --url https://example.com/book/
```

## Useful options

```bash
python3 app.py custom --url https://example.com/book/ --output output/book.pdf
python3 app.py custom --url https://example.com/book/ --debug-html
python3 app.py custom --url https://example.com/book/ --image-profile balanced
python3 app.py ds100 --validate
```

Available flags:

- `--output` to choose the output PDF path
- `--debug-html` to save the merged HTML before PDF rendering
- `--image-profile` with `fast`, `balanced`, or `high`
- `--skip-frontmatter` to omit frontmatter pages when supported
- `--refresh` to force refresh on preset exports
- `--validate` for the built-in `ds100` preset

## Freshness behavior

- Built-in presets use cache by default for faster repeat runs
- Custom URL mode always refreshes chapter HTML so it pulls the latest live content
- Image cache can still be reused to keep exports practical

## Notes on custom websites

- For MyST books, provide the book root or home URL
- For GitBook books, provide the main textbook URL
- If the site is not detected as MyST or GitBook, the tool will stop with a clear error

## Output

Generated files are written to the `output/` directory by default.

Typical outputs include:

- the final PDF
- an optional `_debug.html` file when `--debug-html` is enabled

## Project focus

This repository is focused on reliable extraction of structured online textbooks. The built-in presets are useful examples, but the intended direction of the tool is reusable textbook export for other MyST and GitBook websites.
