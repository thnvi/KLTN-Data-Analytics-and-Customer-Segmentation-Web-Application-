#!/usr/bin/env bash
set -e

echo "[1/2] Start backend"
cd backend
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ../frontend

echo "[2/2] Start frontend"
npm run dev

trap "kill $BACKEND_PID" EXIT
