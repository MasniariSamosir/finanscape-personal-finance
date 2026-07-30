SimpleBudget - A lightweight Flask web app for personal budgeting

Features:
- User register/login (hashed passwords)
- Add income & expense records with categories
- Simple savings calculator (target per month)
- Overspending warning when monthly spending exceeds budget
- Dashboard with summary and charts (Chart.js)
- Export transactions to CSV

Run locally:
1. python -m venv venv
2. (Windows) venv\Scripts\activate  OR (Mac/Linux) source venv/bin/activate
3. pip install -r requirements.txt
4. set FLASK_APP=app.py    (Windows PowerShell: $env:FLASK_APP='app.py')
   export FLASK_APP=app.py (Mac/Linux)
5. flask run
OR
python app.py

The app uses a local SQLite database (data.db) created automatically on first run.
