import json
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from matcher import get_recommendations

app = Flask(__name__)

# Dynamically locate the directory where app.py lives
BASE_DIR = Path(__file__).resolve().parent
MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"

# Helper function to load mock data
def load_mock_data():
    with open(MOCK_DATA_PATH, "r") as file:
        return json.load(file)

# Page Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/assessment')
def assessment():
    return render_template('assessment.html')

# API Endpoints
@app.route('/api/opportunities', methods=['GET'])
def get_opportunities_api():
    try:
        data = load_mock_data()
        student = data.get("student", {})
        opportunities = data.get("opportunities", [])

        # Process matching algorithm
        ranked_matches = get_recommendations(student, opportunities)

        return jsonify({
            "status": "success",
            "student_name": student.get("name"),
            "total_matches": len(ranked_matches),
            "opportunities": ranked_matches
        }), 200

    except FileNotFoundError:
        return jsonify({
            "status": "error",
            "message": "mock_data.json not found in data/ directory."
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)