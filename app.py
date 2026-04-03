from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from functools import wraps
import os
from datetime import datetime, timedelta
import re
from collections import Counter

from models import (
    create_user, verify_user_password, get_user_documents,
    get_document_by_id, save_document_analysis, delete_document,
    get_user_statistics, format_file_size, test_connection, initialize_database
)

app = Flask(__name__)
app.secret_key = 'DocAnalyzer-Secret-Key-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

print("\n" + "="*70)
print("DOCUMENT ANALYZER APPLICATION - STARTING...")
print("="*70)
initialize_database()
if test_connection():
    print("✓ Database connected successfully!")
else:
    print("✗ Database connection failed!")
print("="*70 + "\n")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def extract_text_from_txt(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except:
        return "Error reading file"


def extract_text_from_pdf(filepath):
    try:
        import PyPDF2
        text = ""
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except:
        return "Error reading PDF"


def extract_text_from_docx(filepath):
    try:
        from docx import Document
        doc = Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    except:
        return "Error reading DOCX"


def analyze_document_text(text):
    total_characters = len(text)
    total_words = len(text.split())
    sentences = re.split(r'[.!?]+', text)
    total_sentences = len([s for s in sentences if s.strip()])
    paragraphs = text.split('\n\n')
    total_paragraphs = len([p for p in paragraphs if p.strip()])
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    word_freq = Counter(words)
    top_keywords = word_freq.most_common(10)
    keyword_count = len(word_freq)
    avg_words_per_sentence = total_words / total_sentences if total_sentences > 0 else 0
    top_keywords_str = ", ".join([f"{word}({count})" for word, count in top_keywords[:5]])
    analysis_summary = f"Document has {total_words} words, {total_sentences} sentences and {total_paragraphs} paragraphs. Top keywords: {top_keywords_str}."
    
    return {
        'total_words': total_words,
        'total_characters': total_characters,
        'total_sentences': total_sentences,
        'total_paragraphs': total_paragraphs,
        'keyword_count': keyword_count,
        'top_keywords': top_keywords,
        'analysis_summary': analysis_summary,
        'avg_words_per_sentence': avg_words_per_sentence
    }


def process_uploaded_file(file, user_id):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{user_id}_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        file_type = filename.rsplit('.', 1)[1].lower()
        
        if file_type == 'pdf':
            extracted_text = extract_text_from_pdf(filepath)
        elif file_type == 'docx':
            extracted_text = extract_text_from_docx(filepath)
        else:
            extracted_text = extract_text_from_txt(filepath)
        
        analysis = analyze_document_text(extracted_text)
        
        # Advanced analysis (spell check, readability)
        try:
            from models import analyze_text_advanced
            advanced_analysis = analyze_text_advanced(extracted_text)
            analysis.update(advanced_analysis)
        except Exception as e:
            print(f"Advanced analysis skipped: {e}")
        
        doc_id = save_document_analysis(
            user_id, filename, filepath, file_type, file_size,
            analysis['total_words'], analysis['total_characters'],
            analysis['total_sentences'], analysis['total_paragraphs'],
            analysis['keyword_count'], extracted_text, analysis['analysis_summary']
        )
        return doc_id
    return None


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        if not all([username, email, password, full_name]):
            flash('All fields are required!', 'warning')
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'warning')
            return redirect(url_for('register'))
        
        user_id = create_user(username, email, password, full_name)
        if user_id:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists. Please try different credentials.', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password', 'warning')
            return redirect(url_for('login'))
        
        user_id = verify_user_password(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            flash('Login successful! Welcome back.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    username = session.get('username')
    documents = get_user_documents(user_id)
    stats = get_user_statistics(user_id)
    for doc in documents:
        doc['file_size_formatted'] = format_file_size(doc['file_size'])
    stats['total_storage_formatted'] = format_file_size(stats.get('total_storage', 0))
    return render_template('dashboard.html', documents=documents, username=username, stats=stats)


@app.route('/upload', methods=['POST'])
@login_required
def upload_document():
    if 'document' not in request.files:
        flash('No file selected!', 'danger')
        return redirect(url_for('dashboard'))
    file = request.files['document']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('dashboard'))
    if not allowed_file(file.filename):
        flash('Invalid file type!', 'danger')
        return redirect(url_for('dashboard'))
    user_id = session.get('user_id')
    doc_id = process_uploaded_file(file, user_id)
    if doc_id: 
        flash('Document uploaded successfully!', 'success')
        return redirect(url_for('view_results', doc_id=doc_id))
    flash('Error processing document!', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/results/<int:doc_id>')
@login_required
def view_results(doc_id):
    user_id = session.get('user_id')
    document = get_document_by_id(doc_id)
    if not document or document['user_id'] != user_id:
        flash('Document not found!', 'danger')
        return redirect(url_for('dashboard'))
    
    document['file_size_formatted'] = format_file_size(document['file_size'])
    
    # Get extracted text
    extracted_text = document.get('extracted_text', '')
    
    if extracted_text:
        # Perform detailed analysis
        from models import analyze_text_advanced, auto_correct_text
        
        detailed_analysis = analyze_text_advanced(extracted_text)
        
        # Auto-correct text with format preservation
        corrected_text = auto_correct_text(extracted_text, detailed_analysis.get('misspelled_words', []))
        
        # Add to document
        document['detailed_analysis'] = detailed_analysis
        document['corrected_text'] = corrected_text
    else:
        document['detailed_analysis'] = {}
        document['corrected_text'] = ''
    
    return render_template('results.html', document=document)

@app.route('/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete_document_route(doc_id):
    user_id = session.get('user_id')
    document = get_document_by_id(doc_id)
    if document and document['user_id'] == user_id:
        try:
            if os.path.exists(document['file_path']):
                os.remove(document['file_path'])
        except:
            pass
        if delete_document(doc_id, user_id):
            flash('Document deleted!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/translate/<int:doc_id>', methods=['POST'])
@login_required
def translate_document(doc_id):
    try:
        user_id = session.get('user_id')
        document = get_document_by_id(doc_id)
        
        if not document or document['user_id'] != user_id:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        
        target_lang = request.form.get('language', 'hi')
        source_text = document.get('corrected_text') or document.get('extracted_text', '')
        
        if not source_text:
            return jsonify({'success': False, 'error': 'No text'}), 400
        
        from models import translate_text
        translated = translate_text(source_text, target_lang)
        
        return jsonify({
            'success': True,
            'translated_text': translated,
            'language': target_lang
        })
    
    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("SERVER STARTING...")
    print("Open: http://127.0.0.1:5000")
    print("Login: admin / admin123")
    print("="*70 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)