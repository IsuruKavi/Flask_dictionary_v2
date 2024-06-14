from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_pymongo import PyMongo
import hashlib
import requests
import pycountry
from translate import Translator
import json

app = Flask(__name__)
app.secret_key = "123"  # Required for session management

# MongoDB Configuration
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
uri = "mongodb+srv://isurulakshan870:eos3uJaVw4P3gOfn@cluster0.alhstcm.mongodb.net/myDatabase?retryWrites=true&w=majority&appName=Cluster0"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client.get_database('myDatabase')  
user_collection = db.users  # MongoDB collection for storing user data
word_collection = db.words  # MongoDB collection for storing words
history_collection=db.history # MongoDB colleciton for storing the hisrory of user


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

@app.route('/')
def index():
    if 'username' in session:
        return render_template('homepage.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()  # Hash the password

        # Query MongoDB for user
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
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()  # Hash the password

        # Check if username already exists
        existing_user = user_collection.find_one({'username': username})

        if existing_user:
            return 'Username already exists!'

        # Insert new user into MongoDB
        user_collection.insert_one({'username': username, 'password': password})
        session['username'] = username
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/translate', methods=['GET'])
def get_meaning_of_word():
    # Endpoint to get the meaning of a word in a specified language
    word = request.args.get('word')
    language = request.args.get('language')
    
    if not (word and language):
        return jsonify({'error': 'Missing required query parameters'}), 400
    
    entered_word_and_languag={"username":session['username'],"word":word,"language":language}
    history_collection.insert_one(entered_word_and_languag)
    # Check if he word is already in the database
    word_document = word_collection.find_one({"word": word})
    if word_document:
        print("Found in database")
        english_meanings = word_document['english_meanings']
    else:
        print("Not found in database")
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
            
            # Translate the first definition
            translated_definition = translate_first_definition(definitions[0], language_code)
            
            # Insert data into MongoDB
            data_to_database = {"word": word, "english_meanings": english_meanings}
            word_collection.insert_one(data_to_database)
            
             # Update search history for the user
            user_collection.update_one(
                {"username": session['username']},
                {"$push": {"search_history": {"word": word,"searched_language": language}}}
            )
            # translate the input word
            translator= Translator(to_lang=language_code)
            response_data = {
                "word": word,
                "english": english_meanings,
                "secondaryLanguage": {
                    "info": [
                        {'meaning':translator.translate(word) },{'definition': translated_definition}
                    ],
                    "LanguageIsoCode": language_code,
                    "language": language
                }
            }
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        if word.isalpha():
            return json.dumps(response_data,ensure_ascii=False), 200
        else:
            return jsonify({"error": "Enter a valid word"}), 400

    # If the word is found in the database, translate its meanings
    try:
        if 'english_meanings' in word_document:
            english_meanings = word_document['english_meanings']
        else:
            return jsonify({"error": "English meanings not found for the word"}), 404
        
        language_code = get_language_code(language)
        if not language_code:
            return jsonify({'error': f'Language "{language}" is not recognized'}), 400
        
        # Update search history for the user
        user_collection.update_one(
            {"username": session['username']},
            {"$push": {"search_history": {"word": word,"searched_language": language}}}
            )
        
        # Translate the first definition
        translated_definition = translate_first_definition(english_meanings[0]['definitions'][0], language_code)
        translator= Translator(to_lang=language_code)
        response_data = {
            "word": word,
            "english": english_meanings,
            "secondaryLanguage": {
                "info": [
                    {'meaning':translator.translate(word)},  # Translator.translate(word) removed as it translates the word itself, not its meaning
                    {'definition': translated_definition}
                ],
                "LanguageIsoCode": language_code,
                "language": language
            }
        }
        return  json.dumps(response_data,ensure_ascii=False), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
