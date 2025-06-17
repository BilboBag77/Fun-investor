#!/bin/bash
pip install -r requirements.txt
pip install flake8 openai

flake8 . --max-line-length=120 || exit 1
python .codex/review.py || exit 1
