#!/bin/bash
exec python3 -m uvicorn backend:app --host 127.0.0.1 --port 4400
