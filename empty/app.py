
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/assess", methods = ["POST"])
def assess():
    data = request.get_json()
    print("Recieved data ", data)
    return jsonify({"status": "success", "message": "Recieved"})

if __name__ == "__main__":
    app.run(debug = True, port = 5000)