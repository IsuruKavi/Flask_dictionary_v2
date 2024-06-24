from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_pymongo import PyMongo
import hashlib
import requests
import pycountry
from translate import Translator
from flasgger import Swagger
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)
app.secret_key = "123"  # Required for session management

# Initialize Swagger
swagger = Swagger(app)

# MongoDB Configuration
uri = "mongodb+srv://isurulakshan870:eos3uJaVw4P3gOfn@cluster0.alhstcm.mongodb.net/myDatabase?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client.get_database('myDatabase')
user_collection = db.users
word_collection = db.words
history_collection = db.history
second_language_collection = db.second_language

WORDS_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"

def get_word_data(word):
    # Function to fetch word data from the API
    response = requests.get(f"{WORDS_API_URL}{word}")
    if response.status_code != 200:
        return None
    return response.json()

def get_language_code(language_name):
    # Function to get the language code from the language name
    try:
        language = pycountry.languages.lookup(language_name)
        return language.alpha_2 if hasattr(language, 'alpha_2') else language.alpha_3
    except LookupError:
        return None

def translate_first_definition(definition, language_code):
    # Function to translate the first definition to the specified language
    translator = Translator(to_lang=language_code)
    translated_definition = translator.translate(definition)
    return translated_definition

def get_history():
    username = session['username']
    user_history = history_collection.find({"username": username})
    history_list = []
    for index, entry in enumerate(user_history):
        history_list.append({
            "index": index,
            "entered_words": entry["word"]
        })
    return history_list

@app.route('/')
def index():
    """
    Homepage endpoint.

    ---
    responses:
      302:
        description: Redirect to login page if not logged in
      200:
        description: Homepage for logged-in users
    """
    if 'username' in session:
        username = session['username']
        second_language_doc = second_language_collection.find_one({"username": username})
        if second_language_doc:
            second_language = second_language_doc['second_language']
        else:
            second_language = None
        return render_template('homepage.html', username=username, second_language=second_language)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login endpoint.

    ---
    responses:
      200:
        description: Successfully logged in
      401:
        description: Invalid username or password
    """
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()

        user_data = user_collection.find_one({'username': username, 'password': password})

        if user_data:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password. Please try again.'
            return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration endpoint.

    ---
    responses:
      302:
        description: Redirect to index page upon successful registration
      200:
        description: Register a new user
      409:
        description: Username already exists
    """
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        second_language = request.form['second_language']

        existing_user = user_collection.find_one({'username': username})

        if existing_user:
            return 'Username already exists!'

        user_collection.insert_one({'username': username, 'password': password})
        second_language_collection.insert_one({'username': username, 'second_language': second_language})
        session['username'] = username
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    """
    Logout endpoint.

    ---
    responses:
      302:
        description: Redirect to login page upon successful logout
    """
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/history', methods=['GET'])
def get_user_history():
    """
    Retrieve user history endpoint.

    ---
    responses:
      200:
        description: JSON array of user's search history
    """
    history_list = get_history()
    return jsonify(history_list), 200

@app.route('/translate', methods=['GET'])
def get_meaning_of_word():
    """
    Translate word endpoint.

    ---
    parameters:
      - name: word
        in: query
        type: string
        required: true
        description: The word to translate
      - name: language
        in: query
        type: string
        required: true
        description: The language to translate to (e.g., 'French', 'German')

    responses:
      200:
        description: Translation successful
      400:
        description: Bad request
      404:
        description: No definitions found
    """
    word = request.args.get('word')
    language = request.args.get('language')

    if not (word and language):
        return jsonify({'error': 'Missing required query parameters'}), 400

    word_document = word_collection.find_one({"word": word})

    if word_document:
        english_meanings = word_document['english_meanings']
    else:
        language_code = get_language_code(language)
        if not language_code:
            return jsonify({'error': f'Language "{language}" is not recognized'}), 400

        word_data = get_word_data(word)
        if not word_data:
            return jsonify({
                "title": "No Definitions Found",
                "message": "Sorry, we couldn't find definitions for the word you were looking for.",
                "resolution": "You can try the search again later or head to the web instead."
            }), 404

        try:
            data = word_data[0]['meanings']
            english_meanings = []
            english_similar_words = []
            for meaning in data:
                part_of_speech = meaning['partOfSpeech']
                definitions = [definition['definition'] for definition in meaning['definitions']]
                synonyms = meaning.get('synonyms', [])
                english_meanings.append({'partOfSpeech': part_of_speech, 'definitions': definitions})
                english_similar_words.extend(synonyms)

            english_meanings.append({"similarWords": english_similar_words})

            translated_definition = translate_first_definition(definitions[0], language_code)

            data_to_database = {"word": word, "english_meanings": english_meanings}
            word_collection.insert_one(data_to_database)

            translator = Translator(to_lang=language_code)
            response_data = {
                "word": word,
                "english": english_meanings,
                "secondaryLanguage": {
                    "info": [
                        {'meaning': translator.translate(word)},
                        {'definition': translated_definition}
                    ],
                    "language_iso_code": language_code,
                    "language": language
                }
            }
            entered_words = {"username": session['username'], "word": response_data}
            history_collection.insert_one(entered_words)

        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(response_data), 200

    try:
        if 'english_meanings' in word_document:
            english_meanings = word_document['english_meanings']
        else:
            return jsonify({"error": "English meanings not found for the word"}), 404

        language_code = get_language_code(language)
        if not language_code:
            return jsonify({'error': f'Language "{language}" is not recognized'}), 400

        translated_definition = translate_first_definition(english_meanings[0]['definitions'][0], language_code)

        translator = Translator(to_lang=language_code)
        response_data = {
            "word": word,
            "english": english_meanings,
            "secondaryLanguage": {
                "info": [
                    {'meaning': translator.translate(word)},
                    {'definition': translated_definition}
                ],
                "language_iso_code": language_code,
                "language": language
            }
        }
        entered_words = {"username": session['username'], "word": response_data}
        history_collection.insert_one(entered_words)

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

