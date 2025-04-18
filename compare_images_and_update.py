import os
import fitz  # PyMuPDF
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import nltk

# Check if necessary NLTK resources are already downloaded
nltk_data_path = os.path.join(os.path.expanduser("~"), "nltk_data")
if not os.path.exists(nltk_data_path):
    os.makedirs(nltk_data_path)
    
nltk.data.path.append(nltk_data_path)

# Only download if resources are missing
def download_nltk_resources():
    try:
        stopwords.words('english')
        word_tokenize("test")  # To check if punkt tokenizer is available
        WordNetLemmatizer().lemmatize("test")  # To check if wordnet is available
    except LookupError:
        print("Downloading necessary NLTK resources...")
        nltk.download('punkt', download_dir=nltk_data_path)
        nltk.download('stopwords', download_dir=nltk_data_path)
        nltk.download('wordnet', download_dir=nltk_data_path)

# Download resources if needed
download_nltk_resources()

# Load sentence transformer model once globally
model = SentenceTransformer('all-MiniLM-L6-v2')

# Preprocessing function
def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()

    tokens = word_tokenize(text.lower())
    filtered_tokens = [lemmatizer.lemmatize(word) for word in tokens if word.isalnum() and word not in stop_words]
    return " ".join(filtered_tokens)

# Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

# Main comparison function
def compare_submission_with_model(submission):
    assignment = submission.assignment  # assumes ForeignKey relation

    # Extract raw texts
    teacher_raw = extract_text_from_pdf(assignment.model_answer_file.path)
    student_raw = extract_text_from_pdf(submission.file.path)

    # Preprocess texts
    teacher_cleaned = preprocess_text(teacher_raw)
    student_cleaned = preprocess_text(student_raw)

    # Convert to embeddings
    teacher_embedding = model.encode(teacher_cleaned, convert_to_tensor=True)
    student_embedding = model.encode(student_cleaned, convert_to_tensor=True)

    # Cosine similarity
    similarity_score = cosine_similarity([teacher_embedding], [student_embedding])[0][0] * 100  # Convert to %

    # Save all data to the DB
    assignment.extracted_content = teacher_raw
    assignment.processed_content = teacher_cleaned
    assignment.save()

    submission.content = student_raw
    submission.preprocessed_content = student_cleaned
    submission.text_similarity_score = round(similarity_score, 2)
    submission.save()

    print(f"Cosine Similarity Score: {similarity_score:.2f}%")

#-------------------------------------------------------------------------------------------

import os
import django
from django.conf import settings
# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AssSubmission.settings")  # Make sure this matches your Django settings path
django.setup()

import cv2
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import pytesseract
from django.core.files import File
from classmanagement.models import Submission

# Import necessary libraries for TF-IDF, cosine similarity, and Sentence-BERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Tesseract-OCR\tesseract.exe'

# Directories to save extracted images
STUDENT_IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'extracted_student_images')
TEACHER_IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'extracted_teacher_images')
os.makedirs(STUDENT_IMG_DIR, exist_ok=True)
os.makedirs(TEACHER_IMG_DIR, exist_ok=True)

# Initialize the Sentence-BERT model for text similarity
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

# -------------------- Utility Functions --------------------

def extract_images_from_pdf(pdf_path, output_folder, prefix):
    doc = fitz.open(pdf_path)
    diagram_images = []
    image_paths = []

    for page_number in range(len(doc)):
        page = doc.load_page(page_number)
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            np_img = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

            # Resize image for better OCR results
            img = cv2.resize(img, (img.shape[1] * 2, img.shape[0] * 2))

            # Apply grayscale and sharpening to improve contour detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)  # Reduce noise

            sharpen_kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
            img_sharpened = cv2.filter2D(blurred, -1, sharpen_kernel)

            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(img_sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY_INV, 11, 2)

            # Find contours and filter based on size
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 500]  # Area threshold for filtering small contours

            if len(valid_contours) > 2:  # Check if we have significant contours
                diagram_images.append(img)

                # Save image if valid contours found
                img_name = f"{prefix}_page{page_number}_img{img_index}.png"
                save_path = os.path.join(output_folder, img_name)
                cv2.imwrite(save_path, img)
                image_paths.append(save_path)

    return diagram_images, image_paths


def extract_text_from_images(images):
    all_text = []
    for img in images:
        text = pytesseract.image_to_string(Image.fromarray(img))
        all_text.append(text)
    return "\n".join(all_text)

def compare_text_similarity(text1, text2):
    # Use Sentence-BERT for better semantic similarity calculation
    embeddings1 = model.encode([text1])
    embeddings2 = model.encode([text2])
    similarity = cosine_similarity(embeddings1, embeddings2)[0][0]
    return round(similarity * 100, 2)

# -------------------- Main Comparison Function --------------------

def compare_teacher_student_diagrams(teacher_pdf, student_pdf, submission_id):
    teacher_images, _ = extract_images_from_pdf(teacher_pdf, TEACHER_IMG_DIR, "teacher")
    student_images, student_paths = extract_images_from_pdf(student_pdf, STUDENT_IMG_DIR, "student")

    teacher_text = extract_text_from_images(teacher_images)
    student_text = extract_text_from_images(student_images)

    similarity = compare_text_similarity(teacher_text, student_text)
    print(f"Diagram Text Similarity: {similarity}%")

    try:
        submission = Submission.objects.get(id=submission_id)

        # Save the first extracted image (ImageField expects only one)
        if student_paths:
            with open(student_paths[0], 'rb') as img_file:
                submission.extracted_images.save(os.path.basename(student_paths[0]), File(img_file), save=False)

        submission.image_text = student_text
        submission.image_similarity_score = similarity
        submission.save()

        print("✅ Submission updated successfully.")

    except Submission.DoesNotExist:
        print("❌ Submission not found.")

    return similarity

# -------------------- Example Usage --------------------

if __name__ == "__main__":
    teacher_pdf = "media/model_answers/Cloud_Computing.pdf"  # Path to teacher PDF
    student_pdf = "media/submissions/Nowadays.pdf"           # Path to student PDF
    submission_id = 20                                       # Change to actual submission ID
    compare_teacher_student_diagrams(teacher_pdf, student_pdf, submission_id)

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from classmanagement.models import Submission

def calculate_plagiarism_scores(assignment):
    """Compares all student submissions for the same assignment."""
    submissions = Submission.objects.filter(assignment=assignment)
    contents = [sub.preprocessed_content or "" for sub in submissions]

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(contents)

    # Compare each submission to all others
    for i, sub in enumerate(submissions):
        total_score = 0
        comparisons = 0
        for j, other_sub in enumerate(submissions):
            if i != j:
                similarity = cosine_similarity(tfidf_matrix[i], tfidf_matrix[j])[0][0]
                total_score += similarity
                comparisons += 1
        
        average_score = (total_score / comparisons) * 100 if comparisons > 0 else 0
        sub.plagiarism_score = round(average_score, 2)
        sub.save()

from textblob import TextBlob

def calculate_grammar_score(text):
    """Evaluates grammar and spelling mistakes using TextBlob."""
    blob = TextBlob(text)
    
    # Count number of grammar or spelling errors
    num_errors = sum(1 for word in blob.words if word != word.correct())
    
    # Calculate score out of 10
    if num_errors == 0:
        return 10  # Perfect
    elif num_errors <= 5:
        return 9   # Minor error
    else:
        return 8  # Very poor


def process_submission(submission):
    # Ensure content exists
    if submission.content:
        score = calculate_grammar_score(submission.content)
        submission.grammar_score = score  # ✅ Save grammar score
        submission.save()
    
from datetime import datetime

def handle_submission(student_submission, assignment):
    submission_time = datetime.now()
    due_time = assignment.due_date  # Assuming you have a field like this

    # ✅ Check if submission is late
    student_submission.is_late = submission_time > due_time
    student_submission.save()
def calculate_total_marks_with_penalty(submission_id):
    grade_mapping = [
        (91, "A1", "Outstanding performance! Keep up the hard work."),
        (81, "A2", "Great job! A little more effort can take you to the top."),
        (71, "B1", "Impressive work! Keep focusing and improving."),
        (61, "B2", "You're on the right track! Practice more to excel."),
        (51, "C1", "Decent effort, but there's room for improvement."),
        (41, "C2", "You're making progress, but consistent practice is key."),
        (33, "D",  "You need to put in more effort. Study hard."),
        (0,  "E",  "Serious attention needed! Seek help and study harder."),
    ]

    try:
        submission = Submission.objects.get(id=submission_id)

        # Extract individual component scores
        text_score = submission.text_similarity_score or 0
        image_score = submission.image_similarity_score or 0
        grammar_score = submission.grammar_score or 0

        # Weightage (Adjust as needed)
        total_score = (
            0.5 * text_score +       # 50% Text similarity
            0.3 * image_score +      # 30% Diagram comparison
            0.2 * (grammar_score * 10)  # 20% Grammar score scaled to 100
        )

        # Apply penalty for late submission (example: 10% penalty)
        if submission.is_late:
            total_score *= 0.9  # 10% penalty for late submissions

        # Round the total score to 2 decimal places
        submission.total_marks = round(total_score, 2)

        # Assign grade and feedback based on total marks
        for threshold, grade, feedback in grade_mapping:
            if total_score >= threshold:
                submission.grade = grade
                submission.teacher_feedback = feedback
                break

        submission.save()
        print(f"✅ Total Marks: {submission.total_marks}, Grade: {submission.grade}, Feedback Saved.")

    except Submission.DoesNotExist:
        print("❌ Submission not found.")
