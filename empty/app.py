import json
from pathlib import Path
from flask import Flask, jsonify, render_template
from matcher import get_recommendations

app = Flask(__name__)

# Absolute base directory targeting your root 'si-hackathon' folder
BASE_DIR = Path(__file__).resolve().parent

# Path matching your layout: empty/data/mock_data.json
MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"

def load_mock_data():
    with open(MOCK_DATA_PATH, "r") as file:
        return json.load(file)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/assessment')
def assessment():
    return render_template('assessment.html')

@app.route('/api/opportunities', methods=['GET'])
def get_opportunities_api():
    try:
        data = load_mock_data()
        
        # Extract student dictionary
        student = data.get("student")
        if not student and "students" in data:
            student = data["students"][0]
            
        opportunities = data.get("opportunities", [])

        # Run Shahnawaj's algorithm
        ranked_matches = get_recommendations(student, opportunities)

        return jsonify({
            "status": "success",
            "student_name": student.get("name", "Student") if student else "N/A",
            "total_matches": len(ranked_matches),
            "opportunities": ranked_matches
        }), 200

    except FileNotFoundError:
        return jsonify({
            "status": "error",
            "message": f"Could not find mock_data.json at: {MOCK_DATA_PATH}"
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server Error: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)