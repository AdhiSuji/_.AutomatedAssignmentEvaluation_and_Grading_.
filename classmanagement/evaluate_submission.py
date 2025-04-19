import os
import cv2
import fitz  # PyMuPDF
import logging
import numpy as np
from PIL import Image
from textblob import TextBlob

from django.conf import settings
from django.utils import timezone
from django.core.files import File
from django.db import transaction
from django.utils.timezone import is_naive, make_aware, get_current_timezone

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from classmanagement.models import Submission
import pytesseract

# ------------------- Setup --------------------
logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r'C:\Tesseract-OCR\tesseract.exe'

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

TEXT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
IMG_MODEL = SentenceTransformer('paraphrase-MiniLM-L6-v2')

STUDENT_IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'extracted_student_images')
TEACHER_IMG_DIR = os.path.join(settings.MEDIA_ROOT, 'extracted_teacher_images')
os.makedirs(STUDENT_IMG_DIR, exist_ok=True)
os.makedirs(TEACHER_IMG_DIR, exist_ok=True)


# ------------------- Text Utilities --------------------
def extract_text_from_pdf(path):
    """Extract raw text from all pages of a PDF."""
    return "".join(page.get_text() for page in fitz.open(path))

def preprocess_text(text):
    """Tokenize, remove stopwords, lemmatize, and clean text."""
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()
    tokens = word_tokenize(text.lower())
    return " ".join(lemmatizer.lemmatize(w) for w in tokens if w.isalnum() and w not in stop_words)

def compare_text_similarity(t1, t2):
    """Compute cosine similarity between two texts using Sentence-BERT."""
    emb1, emb2 = TEXT_MODEL.encode([t1]), TEXT_MODEL.encode([t2])
    return round(cosine_similarity(emb1, emb2)[0][0] * 100, 2)


# ------------------- Diagram/Image Utilities --------------------
def extract_images_from_pdf(pdf_path, output_folder, prefix):
    """Extract potential diagram images from a PDF and save filtered ones."""
    doc = fitz.open(pdf_path)
    extracted_imgs, saved_paths = [], []

    for page_no in range(len(doc)):
        for idx, img in enumerate(doc[page_no].get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_data = np.frombuffer(base_image["image"], np.uint8)
            img_cv = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            img_cv = cv2.resize(img_cv, (img_cv.shape[1]*2, img_cv.shape[0]*2))

            # Preprocessing for contour detection
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            sharpened = cv2.filter2D(blurred, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
            thresh = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY_INV, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len([c for c in contours if cv2.contourArea(c) > 500]) > 2:
                filename = f"{prefix}_page{page_no}_img{idx}.png"
                path = os.path.join(output_folder, filename)
                cv2.imwrite(path, img_cv)
                extracted_imgs.append(img_cv)
                saved_paths.append(path)

    return extracted_imgs, saved_paths

def extract_text_from_images(images):
    """Apply OCR on a list of images to extract textual content."""
    return "\n".join(pytesseract.image_to_string(Image.fromarray(img)) for img in images)

def compare_diagram_similarity(t1, t2):
    """Compute cosine similarity between two diagram-extracted texts."""
    emb1, emb2 = IMG_MODEL.encode([t1]), IMG_MODEL.encode([t2])
    return round(cosine_similarity(emb1, emb2)[0][0] * 100, 2)


# ------------------- Grammar & Timeliness --------------------
def calculate_grammar_score(text):
    """Return grammar score out of 10 based on simple word-level corrections."""
    blob = TextBlob(text)
    errors = sum(1 for word in blob.words if word != word.correct())
    return 10 if errors == 0 else 9 if errors <= 5 else 8

def mark_late(submission, due_date):
    """Flag submission as late based on assignment's due date."""
    aware_due = make_aware(due_date, get_current_timezone()) if is_naive(due_date) else due_date
    submission.is_late = timezone.now() > aware_due


# ------------------- Plagiarism --------------------
def calculate_plagiarism_scores(assignment):
    """Update plagiarism score for all submissions of an assignment."""
    submissions = Submission.objects.filter(assignment=assignment)
    texts = [s.preprocessed_content or "" for s in submissions]
    tfidf = TfidfVectorizer().fit_transform(texts)

    with transaction.atomic():
        for i, sub in enumerate(submissions):
            total_sim = sum(cosine_similarity(tfidf[i], tfidf[j])[0][0]
                            for j in range(len(submissions)) if i != j)
            avg_sim = (total_sim / (len(submissions) - 1)) * 100 if len(submissions) > 1 else 0
            sub.plagiarism_score = round(avg_sim, 2)
            sub.save()

# ------------------- Grade & Feedback --------------------
def calculate_total_grade(sub):
    """Calculate total marks and assign grade and feedback."""
    score = (
        sub.text_similarity_score * 0.4 +
        sub.image_similarity_score * 0.3 +
        sub.grammar_score * 1 +
        (100 - sub.plagiarism_score) * 0.2
    )

    for threshold, grade, remark in [
        (91, "A1", "Outstanding performance! Keep up the hard work."),
        (81, "A2", "Great job! A little more effort can take you to the top."),
        (71, "B1", "Impressive work! Keep focusing and improving."),
        (61, "B2", "You're on the right track! Practice more to excel."),
        (51, "C1", "Decent effort, but there's room for improvement."),
        (41, "C2", "Fair work, but strive to be better."),
        (33, "D", "Needs more effort. Try to improve next time."),
        (0,  "E", "Poor performance. Please seek help to understand the material.")
    ]:
        if score >= threshold:
            sub.grade = grade
            sub.feedback = remark
            break

    sub.total_marks = round(score, 2)
    sub.save()


# ------------------- Evaluation Entry Point --------------------
def evaluate_submission(submission_id):
    """Main function to evaluate a submission."""
    try:
        sub = Submission.objects.get(id=submission_id)
        assignment = sub.assignment

        # --- TEXT SIMILARITY ---
        teacher_text = preprocess_text(extract_text_from_pdf(assignment.model_answer_file.path))
        student_text = preprocess_text(extract_text_from_pdf(sub.file.path))
        sub.content = student_text
        sub.preprocessed_content = student_text
        sub.text_similarity_score = compare_text_similarity(teacher_text, student_text)

        # --- DIAGRAM SIMILARITY ---
        teacher_imgs, _ = extract_images_from_pdf(assignment.model_answer_file.path, TEACHER_IMG_DIR, 'teacher')
        student_imgs, student_paths = extract_images_from_pdf(sub.file.path, STUDENT_IMG_DIR, 'student')
        t_text = extract_text_from_images(teacher_imgs)
        s_text = extract_text_from_images(student_imgs)
        sub.image_text = s_text
        sub.image_similarity_score = compare_diagram_similarity(t_text, s_text)

        # Save first student diagram
        if student_paths:
            with open(student_paths[0], 'rb') as img_file:
                sub.extracted_images.save(os.path.basename(student_paths[0]), File(img_file), save=False)

        # --- GRAMMAR + LATE ---
        sub.grammar_score = calculate_grammar_score(student_text)
        mark_late(sub, assignment.due_date)
        sub.save()

        # --- PLAGIARISM + GRADING ---
        calculate_plagiarism_scores(assignment)
        calculate_total_grade(sub)

        logger.info(f"✅ Evaluation complete for submission ID {submission_id}")

    except Exception as e:
        logger.error(f"❌ Error in evaluating submission {submission_id}: {e}")