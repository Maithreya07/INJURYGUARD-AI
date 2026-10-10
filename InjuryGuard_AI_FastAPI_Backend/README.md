# InjuryGuard AI — FastAPI Backend

## 1. Open Command Prompt / PowerShell

Move into this folder:

    cd path\to\injuryguard_backend

## 2. Create a virtual environment

Windows:

    py -m venv .venv
    .venv\Scripts\activate

If `py` is not available, try:

    python -m venv .venv
    .venv\Scripts\activate

## 3. Install packages

    python -m pip install --upgrade pip
    pip install -r requirements.txt

## 4. Start the server

    fastapi dev app/main.py

Alternative:

    uvicorn app.main:app --reload

## 5. Open the API

    http://127.0.0.1:8000

Interactive API docs:

    http://127.0.0.1:8000/docs

## 6. What this backend currently does

- Starts a FastAPI server
- Creates a SQLite database (`injuryguard.db`)
- Stores assessment history
- Accepts photo/video uploads
- Calculates a DEMO injury-risk score
- Returns Low / Moderate / High
- Provides APIs to fetch assessment history
- Has CORS configured for local frontend development

## API endpoints

GET `/`
GET `/health`
POST `/api/assessments`
GET `/api/assessments`

## Important

The risk calculator in `app/main.py` is only a demonstration scoring function.
It is NOT a medically validated AI model.

Next development stage:
1. Connect the existing frontend assessment form to POST `/api/assessments`
2. Display real database history
3. Add pose extraction from uploaded video
4. Add trained ML/CNN/LSTM inference
5. Replace demo scoring with the validated model
