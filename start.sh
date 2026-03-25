#!/bin/bash
cd "$(dirname "$0")"
export FAL_KEY="1a1eb80d-0514-4bfd-aa09-1dcfe146d824:22e876a815145d09f03f47fdcde8ce17"
export PATH="/home/claude-user/.local/bin:$PATH"
pip3 install -r requirements.txt --break-system-packages -q
cd api
python3 -m uvicorn main:app --host 0.0.0.0 --port 8401 --reload
