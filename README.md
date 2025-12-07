# JustWatch Search Python Script & Web Demo

A Python script that allows you to search for movies and TV shows across various streaming platforms using the JustWatch API right in your terminal.
The script can be run in a [web browser demo](https://anton2026gamca.github.io/justwatch-search/) using Pyodide, enabling a command-line interface experience directly in the browser.

## Features

- Search for movies and TV shows
- Filter results by streaming platform, subscription type, audio language, subtitles, etc.

## Usage

1. Clone the repository:
  ```bash
  git clone https://github.com/anton2026gamca/justwatch-search.git
  cd justwatch-search
  ```
2. Create a virtual environment and install dependencies:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
3. Run the script:
  ```bash
  python3 just_watch_search.py -h
  ```