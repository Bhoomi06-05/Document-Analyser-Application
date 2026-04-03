import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_FILE = 'document_analyzer.db'

def get_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_analysis (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_words INTEGER DEFAULT 0,
            total_characters INTEGER DEFAULT 0,
            total_sentences INTEGER DEFAULT 0,
            total_paragraphs INTEGER DEFAULT 0,
            keyword_count INTEGER DEFAULT 0,
            extracted_text TEXT,
            analysis_summary TEXT,
            status TEXT DEFAULT 'Completed',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'admin'")
    if cursor.fetchone()['count'] == 0:
        admin_hash = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@docanalyzer.com', admin_hash, 'System Administrator'))
        
        demo_hash = generate_password_hash('demo123')
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', ('demo', 'demo@docanalyzer.com', demo_hash, 'Demo User'))
    
    conn.commit()
    conn.close()
    print("✓ Database initialized successfully!")

def create_user(username, email, password, full_name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, full_name))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except:
        return None

def verify_user_password(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, password_hash FROM users WHERE username = ? AND is_active = 1', (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            update_last_login(user['user_id'])
            return user['user_id']
        return None
    except:
        return None

def update_last_login(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def save_document_analysis(user_id, filename, file_path, file_type, file_size,
                          total_words, total_characters, total_sentences,
                          total_paragraphs, keyword_count, extracted_text, analysis_summary):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO document_analysis 
            (user_id, filename, file_path, file_type, file_size, total_words,
             total_characters, total_sentences, total_paragraphs, keyword_count,
             extracted_text, analysis_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, filename, file_path, file_type, file_size, total_words,
              total_characters, total_sentences, total_paragraphs, keyword_count,
              extracted_text, analysis_summary))
        conn.commit()
        doc_id = cursor.lastrowid
        conn.close()
        return doc_id
    except:
        return None

def get_user_documents(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM document_analysis 
            WHERE user_id = ? 
            ORDER BY upload_date DESC
        ''', (user_id,))
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return documents
    except:
        return []

def get_document_by_id(doc_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM document_analysis WHERE doc_id = ?', (doc_id,))
        document = cursor.fetchone()
        conn.close()
        return dict(document) if document else None
    except:
        return None

def delete_document(doc_id, user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM document_analysis WHERE doc_id = ? AND user_id = ?', (doc_id, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except:
        return False

def get_user_statistics(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total_documents,
                COALESCE(SUM(file_size), 0) as total_storage,
                COALESCE(SUM(total_words), 0) as total_words,
                MAX(upload_date) as last_upload_date
            FROM document_analysis 
            WHERE user_id = ?
        ''', (user_id,))
        stats = dict(cursor.fetchone())
        conn.close()
        return stats
    except:
        return {'total_documents': 0, 'total_storage': 0, 'total_words': 0, 'last_upload_date': None}

def format_file_size(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    elif size_in_bytes < 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"

def test_connection():
    try:
        conn = get_connection()
        conn.close()
        return True
    except:
        return False

def analyze_text_advanced(text):
    """Advanced text analysis with spell check, grammar, and readability"""
    try:
        from spellchecker import SpellChecker
        import textstat
        
        results = {}
        
        # Spell Check with Proper Noun Protection
        spell = SpellChecker()
        
        # Extract words
        words = text.split()
        misspelled = []
        
        for word in words:
            # Clean word
            clean_word = ''.join(c for c in word if c.isalpha())
            if len(clean_word) <= 2:
                continue
            
            # Skip if:
            # 1. Starts with capital (likely proper noun)
            # 2. All uppercase (acronym)
            # 3. Contains numbers
            if clean_word[0].isupper() or clean_word.isupper() or any(c.isdigit() for c in word):
                continue
            
            # Check spelling for lowercase words only
            if clean_word.lower() in spell.unknown([clean_word.lower()]):
                misspelled.append(clean_word.lower())
        
        # Remove duplicates
        misspelled = list(set(misspelled))
        
        results['misspelled_count'] = len(misspelled)
        results['misspelled_words'] = misspelled[:20]
        
        # Readability Scores
        if len(text) > 50:
            results['flesch_reading_ease'] = textstat.flesch_reading_ease(text)
            results['reading_level'] = textstat.text_standard(text, float_output=False)
        else:
            results['flesch_reading_ease'] = 0
            results['reading_level'] = "N/A"
        
        # Grammar Check
        grammar_results = check_grammar(text)
        results.update(grammar_results)
        
        return results
    except Exception as e:
        print(f"Advanced analysis error: {e}")
        return {
            'misspelled_count': 0,
            'misspelled_words': [],
            'flesch_reading_ease': 0,
            'reading_level': 'N/A',
            'grammar_error_count': 0,
            'grammar_errors': []
        }
def check_grammar(text):
    """Grammar check disabled - requires Java 17+ and stable internet"""
    return {
        'grammar_error_count': 0,
        'grammar_errors': []
    }

def apply_grammar_corrections(text, grammar_errors):
    """Apply grammar corrections to text"""
    corrected_text = text
    try:
        for error in reversed(grammar_errors):
            if error.get('suggestions') and len(error['suggestions']) > 0:
                suggestion = error['suggestions'][0]
                context = error.get('context', '')
                if context in corrected_text:
                    pass
        return corrected_text
    except:
        return text

def auto_correct_text(text, misspelled_words):
    """
    Auto-correct spelling errors while preserving:
    - Proper nouns (capitalized words)
    - Acronyms (all caps)
    - Line breaks
    - Numbering
    - Indentation
    """
    if not text or not misspelled_words:
        return text
    
    from spellchecker import SpellChecker
    spell = SpellChecker()
    
    misspelled_set = set(word.lower() for word in misspelled_words)
    lines = text.split('\n')
    corrected_lines = []
    
    for line in lines:
        if not line.strip():
            corrected_lines.append(line)
            continue
        
        leading_spaces = len(line) - len(line.lstrip())
        leading_whitespace = line[:leading_spaces]
        line_content = line[leading_spaces:]
        
        tokens = []
        current_word = ""
        
        for char in line_content:
            if char.isalpha() or char == "'":
                current_word += char
            else:
                if current_word:
                    tokens.append(('word', current_word))
                    current_word = ""
                tokens.append(('char', char))
        
        if current_word:
            tokens.append(('word', current_word))
        
        corrected_tokens = []
        for token_type, token_value in tokens:
            if token_type == 'word':
                # Skip correction if:
                # 1. First letter is capital (proper noun)
                # 2. All uppercase (acronym)
                if token_value[0].isupper() or token_value.isupper():
                    corrected_tokens.append(token_value)
                    continue
                
                clean_word = token_value.lower().strip("'")
                
                if clean_word in misspelled_set:
                    correction = spell.correction(clean_word)
                    
                    if correction and correction != clean_word:
                        corrected_tokens.append(correction)
                    else:
                        corrected_tokens.append(token_value)
                else:
                    corrected_tokens.append(token_value)
            else:
                corrected_tokens.append(token_value)
        
        corrected_line = leading_whitespace + ''.join(corrected_tokens)
        corrected_lines.append(corrected_line)
    
    return '\n'.join(corrected_lines)
def professional_format_text(text):
    """
    Apply professional formatting to any text:
    - Clean spacing
    - Proper capitalization
    - Organized structure
    - Professional presentation
    """
    if not text:
        return text
    
    lines = text.split('\n')
    formatted_lines = []
    prev_was_empty = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip excessive blank lines (max 1 consecutive)
        if not stripped:
            if not prev_was_empty:
                formatted_lines.append('')
                prev_was_empty = True
            continue
        
        prev_was_empty = False
        
        # Check if line is a heading (short, ends with :, or all caps)
        is_heading = (
            len(stripped) < 50 and 
            (stripped.endswith(':') or stripped.isupper() or 
             any(stripped.startswith(marker) for marker in ['●', '•', '-', '▪']))
        )
        
        if is_heading:
            # Headings: Ensure proper spacing
            if formatted_lines and formatted_lines[-1] != '':
                formatted_lines.append('')  # Add blank line before heading
            formatted_lines.append(stripped)
            formatted_lines.append('')  # Add blank line after heading
        else:
            # Regular text: Clean and format
            # Ensure sentence starts with capital
            if stripped and stripped[0].islower() and not any(stripped.startswith(p) for p in ['e.g.', 'i.e.', 'etc.']):
                stripped = stripped[0].upper() + stripped[1:]
            
            formatted_lines.append(stripped)
    
    # Remove trailing empty lines
    while formatted_lines and formatted_lines[-1] == '':
        formatted_lines.pop()
    
    return '\n'.join(formatted_lines)
def translate_text(text, target_language='hi'):
    """
    Translate with PROFESSIONAL FORMATTING preserved
    - Headings remain bold-style (uppercase/markers)
    - Bullets/numbers maintained
    - Spacing preserved
    - Professional structure intact
    """
    try:
        from deep_translator import GoogleTranslator
        import re
        
        print(f"\n=== Professional Translation Started ===")
        print(f"Target: {target_language}, Length: {len(text)}")
        
        translator = GoogleTranslator(source='auto', target=target_language)
        
        # Split by paragraphs (double newline)
        paragraphs = text.split('\n\n')
        translated_paragraphs = []
        
        for para_idx, paragraph in enumerate(paragraphs, 1):
            if not paragraph.strip():
                translated_paragraphs.append('')
                continue
            
            lines = paragraph.split('\n')
            translated_lines = []
            
            for line_idx, line in enumerate(lines, 1):
                if not line.strip():
                    translated_lines.append('')
                    continue
                
                # Preserve indentation
                leading_spaces = len(line) - len(line.lstrip())
                indent = ' ' * leading_spaces
                clean_line = line.strip()
                
                # Detect formatting markers
                is_heading = False
                is_bullet = False
                is_number = False
                prefix = ''
                
                # Check for heading indicators
                if clean_line.isupper() or clean_line.endswith(':'):
                    is_heading = True
                
                # Check for bullets
                bullet_patterns = ['•', '-', '○', '◦', '*']
                for bullet in bullet_patterns:
                    if clean_line.startswith(bullet):
                        is_bullet = True
                        prefix = bullet + ' '
                        clean_line = clean_line[len(bullet):].strip()
                        break
                
                # Check for numbering
                number_match = re.match(r'^(\d+[\.\)])\s+', clean_line)
                if number_match:
                    is_number = True
                    prefix = number_match.group(1) + ' '
                    clean_line = clean_line[len(prefix):].strip()
                
                # Check for special markers (like arrows, colons)
                if clean_line.startswith('→'):
                    prefix = '→ '
                    clean_line = clean_line[1:].strip()
                
                try:
                    # Translate content
                    if len(clean_line) > 4500:
                        chunks = [clean_line[j:j+4500] for j in range(0, len(clean_line), 4500)]
                        translated = ' '.join([translator.translate(chunk) for chunk in chunks])
                    else:
                        translated = translator.translate(clean_line) if clean_line else ''
                    
                    # Reconstruct with formatting
                    final_line = indent + prefix + translated
                    
                    # For headings, keep uppercase/colon format
                    if is_heading and clean_line.isupper():
                        final_line = indent + prefix + translated.upper()
                    
                    translated_lines.append(final_line)
                    print(f"✓ Para {para_idx}, Line {line_idx}")
                    
                except Exception as e:
                    print(f"✗ Para {para_idx}, Line {line_idx}: {e}")
                    translated_lines.append(line)
            
            translated_paragraphs.append('\n'.join(translated_lines))
        
        result = '\n\n'.join(translated_paragraphs)
        print(f"=== Translation Complete! Output: {len(result)} chars ===\n")
        return result
    
    except Exception as e:
        print(f"Translation ERROR: {e}")
        import traceback
        traceback.print_exc()
        return text
if __name__ == '__main__':
    print("\n" + "="*60)
    print("DATABASE INITIALIZATION")
    print("="*60)
    initialize_database()
    if test_connection():
        print("✓ Database connection successful!")
    else:
        print("✗ Database connection failed!")
    print("="*60 + "\n")