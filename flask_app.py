from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import cv2
import numpy as np
from flask import render_template
from flask_cors import CORS

# cors setup


app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "https://lor.pythonanywhere.com"}})

@app.route('/')
def index():
    return render_template('index.html')
# Folder where uploaded images will be stored
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to detect filled circles in the provided region of interest
def detect_filled_circles(image_path, threshold=50):
    # Fixed cropping coordinates
    y_start, y_end, x_start, x_end = 500, 1500, 100, 1000

    image = cv2.imread(image_path)
    if image is None:
        return []

    # Crop the region of interest (questions 1 to 100)
    roi = image[y_start:y_end, x_start:x_end]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    adaptive_thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    blurred = cv2.GaussianBlur(adaptive_thresh, (7, 7), 2)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=15,
        param1=50,
        param2=30,
        minRadius=10,
        maxRadius=20
    )

    filled_circles = []

    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        for (x, y, r) in circles:
            circle_mask = np.zeros_like(gray, dtype="uint8")
            cv2.circle(circle_mask, (x, y), r, 255, -1)  # Create a circular mask

            mean_intensity = cv2.mean(gray, mask=circle_mask)[0]

            if mean_intensity < threshold:
                filled_circles.append((x, y, r))

    return filled_circles

# Upload route to save files and return their paths
@app.route('/upload_files', methods=['POST'])
def upload_files():
    if 'official_answer' not in request.files or 'candidates' not in request.files:
        return jsonify({'error': 'Missing files'}), 400

    official_file = request.files['official_answer']
    candidate_files = request.files.getlist('candidates')

    official_filename = secure_filename(official_file.filename)
    official_path = os.path.join(app.config['UPLOAD_FOLDER'], official_filename)
    official_file.save(official_path)

    candidate_paths = []
    for file in candidate_files:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        candidate_paths.append(path)

    return jsonify({
        'official_answer_path': official_path,
        'candidate_answer_paths': candidate_paths
    })

# Compare route to analyze and score candidate sheets
@app.route('/compare_answers', methods=['POST'])
def compare_answers():
    data = request.get_json()

    official_answer_path = data.get('official_answer_path')
    candidate_answer_paths = data.get('candidate_answer_paths')

    if not official_answer_path or not candidate_answer_paths:
        return jsonify({'error': 'Missing data'}), 400

    official_answers = detect_filled_circles(official_answer_path)
    total_questions = 100
    print(total_questions)

    results = []
    for candidate_path in candidate_answer_paths:
        candidate_answers = detect_filled_circles(candidate_path)

        matched = [False] * len(official_answers)
        correct_count = 0

        for cand_circle in candidate_answers:
            for i, off_circle in enumerate(official_answers):
                if not matched[i] and abs(cand_circle[0] - off_circle[0]) <= 5 and abs(cand_circle[1] - off_circle[1]) <= 5:
                    correct_count += 1
                    matched[i] = True
                    break

        incorrect_count = len(candidate_answers) - correct_count
        unanswered_count = total_questions - correct_count - incorrect_count
        incorrect_count_total = incorrect_count + unanswered_count

        results.append({
            'candidate_path': candidate_path,
            'total_questions': total_questions,
            'correct_answers': correct_count,
            'incorrect_answers': incorrect_count_total,
        })

    return jsonify({'results': results})


# Run the app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
