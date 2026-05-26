#Flask -- python import statement used to bring Flask class into your script from the flask package
#render-template -- is a built-in function to generate a complete HTML page by processing an external HTML file
#url_for -- url for flask route
#requests--incoming message fromclient ,jsonify -- JSON response Object
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy #SQLALChemy -- integrate the powerful SQLALchemy database toolkit
from werkzeug.utils import secure_filename # import utility function used to sanitizes filename
from datetime import datetime #import date and time
from PyPDF2 import PdfReader #PdfReader is used for the parsing the text
import os #os -- python built-in os module
from dotenv import load_dotenv #load_dotenv -- Used to read the .env files
import spacy #spacy -- library to perform NLP tasks
import requests 
import re # re-- Built in Regular Expression
import uuid #UUIS -- Universal Unique Identifires

app = Flask(__name__)  #Create Instance , which becomes Web Server Gateway Interface (WSGI) application
nlp = spacy.load("en_core_web_sm") # loading a Specific pre-trained model
load_dotenv() # part of the python-dotenv
# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///uploads.db'# Tells databse connect ,///--relative path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # track object modification and setting False because to improve the performance

# Upload config
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 16 * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True) #Creating a directory for uploading files

# Initialize database
db = SQLAlchemy(app)

# Database Model
class Uploadfiles(db.Model): 
    id = db.Column(db.Integer, primary_key=True)# Atleast one Primary key in db.
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    processing_status = db.Column(db.String(20), default='pending')
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# PDF Parsing
def extract_text_from_pdf(pdf_path): #define nameOfFunction(parameter)

    text = ""

    try: #Error Exception
        reader = PdfReader(pdf_path)

        for page in reader.pages:

            extracted = page.extract_text()

            if extracted:
                text += extracted + "\n"

    except Exception as e:
        print("PDF Parsing Error:", e)

    return text

# Text Cleaning
def clean_text(text):

    # Remove extra spaces/newlines
    text = re.sub(r'\s+', ' ', text)

    # Add space between lowercase and uppercase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Remove unwanted symbols
    text = re.sub(r'[^a-zA-Z0-9\s.,:@_-]', '', text)

    # Remove repeated spaces
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip() #strip -- remove extra space in starting or end

def detect_section(text):

    lines = text.split('\n')

    sections = {}   # FIXED

    current_section = "other"

    for line in lines:

        clean_line = line.strip().lower()

        if clean_line == "education":
            current_section = "education"
            sections[current_section] = []

        elif clean_line == "skills":
            current_section = "skills"
            sections[current_section] = []

        elif clean_line == "projects":
            current_section = "projects"
            sections[current_section] = []

        else:
            if current_section not in sections:
                sections[current_section] = []

            sections[current_section].append(line)

    return sections
    
#Skills Extraction . There are two types 1.Rule Based 2.AI Based

SKILLS_DB = [
    "python", "flask", "django",
    "react", "node", "postgresql",
    "sql", "mongodb", "java"
]

def extract_skills(text):

    doc = nlp(text.lower())

    found_skills = []

    for token in doc:

        if token.text in SKILLS_DB:
            found_skills.append(token.text)

    return list(set(found_skills))

# Helper function
def allowed_file(filename):

    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


#Sample Parsing
import json


def parse_llm_output(text):
    try:
        cleaned = re.sub(r"```json|```", "", text).strip()
        return json.loads(cleaned)
    except:
        return {
            "raw": text,
            "error": "Failed to parse JSON"
        }

def get_ats_output(resume_text, job_text):

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  #Define the key of openrouter

    url = "https://openrouter.ai/api/v1/chat/completions" #URL For the open router chat

    #Here it defines Prompt Engineering 
    prompt = f"""
You are an ATS system.

Return ONLY valid JSON (NO markdown, NO ```).

{{
  "ats_score": number,
  "matched_skills": [],
  "missing_skills": [],
  "feedback": ""
}}

Resume:
{resume_text}

Job:
{job_text}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}", #Bearer token -- to send your specific api key
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",  #define model
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(url, headers=headers, json=payload) #response taken

    result = response.json()

    print("OPENROUTER RESPONSE:", result)

    if "choices" not in result:
        return {"error": result}

    content = result["choices"][0]["message"]["content"] #line of code used to extract the text response from an AI model

    try:
        return json.loads(re.sub(r"```json|```", "", content).strip())
    except:
        return {"raw": content}


# Home Route
@app.route("/")
def home():
    return render_template("index.html")

@app.route('/upload_file', methods=["POST"])
def upload_file():

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    #Taking inputs from the client
    file = request.files['file']
    job_description = request.form.get("job_description")

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files allowed"}), 400

    original_filename = secure_filename(file.filename)  #Defining filename

    stored_filename = f"{uuid.uuid4()}-{original_filename}" #Define stored filename

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)

    try:

        # Save file
        file.save(file_path)

        # Extract text
        raw_text = extract_text_from_pdf(file_path)

        # Clean text
        cleaned_text = clean_text(raw_text)

        # FIXED FUNCTION NAME
        sections = detect_section(cleaned_text)

        # Extract skills
        skills = extract_skills(cleaned_text)
        ats_output = get_ats_output(cleaned_text, job_description)

        # Save DB
        new_file = Uploadfiles(
            filename=original_filename,
            stored_name=stored_filename,
            file_path=file_path,
            file_type=file.content_type,
            file_size=os.path.getsize(file_path),
            processing_status="completed"
        )
        #Add and commit the changes
        db.session.add(new_file)
        db.session.commit()

        return jsonify({
            "message": "File uploaded and parsed successfully",
            "skills": skills,
            "sections": sections,
            "cleaned_text": cleaned_text[:1000],
           "ats_output": ats_output
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Main
if __name__ == "__main__": #acts as as gatekeeper that allows code to execute when script is run directly
    #Database creation 
    with app.app_context():
        db.create_all()
    #Typically used to launch a flask web application with specific network and debugging settings
    app.run(host="0.0.0.0", port=10000, debug=True)