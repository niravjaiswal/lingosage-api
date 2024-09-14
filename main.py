from gtts import gTTS
from flask import Flask, render_template, request, send_file, send_from_directory, make_response
import requests
from pytube import YouTube
import assemblyai as aai
import youtube_dl
import os
from pydub import AudioSegment
import speech_recognition as sr
import json
from flask_cors import CORS, cross_origin
from translate import Translator
from dotenv import load_dotenv
from moviepy.editor import *
from moviepy.video.io.VideoFileClip import VideoFileClip
import subprocess
from deep_translator import GoogleTranslator
import os
import gdown
import convertapi
import logging
from logging import Formatter
import time
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable, VideoUnavailable


logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=os.environ.get('LOGLEVEL', 'INFO'))
logging.Formatter.converter = time.localtime
app = Flask(__name__)
CORS(app)
load_dotenv()  # This loads the variables from .env

LANGUAGE_CODE_MAPPING = {
   "English": "en",
   "Chinese":"ch",
   "Spanish": "es",
   "Hindi": "hi",
   "French": "fr",
   "Russian": "ru",
   "Portuguese": "pt",
   "German": "de",
   "Japanese": "ja",
   "Italian": "it",
   "Dutch":"nl",
   "Finnish":"fi",
   "Korean":"ko",
   "Turkish":"tr",
   "Ukrainian":"uk",
   "Vietnamese":"vi"
   # Add other languages and their codes as necessary
}
LANGUAGE_MAPPING1 = {
   "English": "en",
   "Chinese": "zh-CN",
   "Spanish": "es",
   "Hindi": "hi",
   "French": "fr",
   "Russian": "ru",
   "Portuguese": "pt",
   "German": "de",
   "Japanese": "ja",
   "Italian": "it",
   "Dutch": "nl",
   "Finnish": "fi",
   "Korean": "ko",
   "Turkish": "tr",
   "Ukrainian": "uk",
   "Vietnamese": "vi",
   # Add other languages as necessary
}

GTTSLanguageCodeMapping = {
   "English": "en",
   "Chinese": "zh-Hans",  # Assuming Simplified Chinese
   "Spanish": "es",
   "Hindi": "hi",
   "French": "fr",
   "Russian": "ru",
   "Portuguese": "pt",
   "German": "de",
   "Japanese": "ja",
   "Italian": "it",
   "Dutch": "nl",
   "Finnish": "fi",
   "Korean": "ko",
   "Turkish": "tr",
   "Ukrainian": "uk",
   "Vietnamese": "vi",
}

global_translated_text = ""
global_output_language = ""

def time_to_ms(time):
    return ((time.hour * 60 + time.minute) * 60 + time.second) * 1000 + time.microsecond / 1000


def generate_audio(mytext, language, uid):
    # Convert full language name to gTTS language code
    gtts_lang_code = GTTSLanguageCodeMapping.get(language)
    if not gtts_lang_code:
        raise ValueError(f"Unsupported language for gTTS: {language}")

    # Generate the audio file using gTTS
    output_dir = os.path.join("outputs")  # Path relative to the script location
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, f"{uid}.mp3")
    myobj = gTTS(text=mytext, lang=gtts_lang_code, slow=False)
    myobj.save(output_path)
    return output_path

# Function to download a YouTube video and return the audio filename


def download_audio(url, uid):
    yt = YouTube(url)
    stream = yt.streams.filter(only_audio=True).first()
    audio_filename = f"{uid}.mp3"  # Specify the desired file name
    audio_output_path = os.path.join("temp", audio_filename)

    # Create the temp directory if it doesn't exist
    if not os.path.exists("temp"):
        os.makedirs("temp")

    stream.download(output_path="temp", filename=audio_filename)
    return audio_output_path

def is_video_long(youtube_url):
    try:
        youtube = YouTube(youtube_url)
        duration_seconds = youtube.length
        return duration_seconds > 1800
    except Exception as e:
        app.logger.error(f"Error fetching video duration: {e}")
        return False

def download_video(url,uid):
    youtube = YouTube(url)
    video = youtube.streams.get_highest_resolution()
    video_filename = f"{uid}.mp4"  # Specify the desired file name
    video_output_path = os.path.join("temp", video_filename)

    # Create the temp directory if it doesn't exist
    if not os.path.exists("temp"):
        os.makedirs("temp")

    video.download(output_path="temp", filename=video_filename)
    return video_output_path

def download_video_again(url, uid):
    youtube = YouTube(url)
    video = youtube.streams.get_highest_resolution()
    video_filename = f"{uid}.mp4"  # Specify the desired file name
    
    video_output_path = os.path.join("outputs", video_filename)

    if not os.path.exists(os.path.join("outputs")):
        os.makedirs("outputs")

    video.download(output_path="outputs", filename=video_filename)
    return video_output_path



# Function to transcribe the audio file and return the transcript
def transcribe(audio_path, lang2):
    aai.settings.api_key = os.getenv('ASSEMBLY_AI_API_KEY')
    gtts_lang_code = LANGUAGE_CODE_MAPPING.get(lang2)
    config = aai.TranscriptionConfig(language_code=gtts_lang_code)

    transcriber = aai.Transcriber(config=config)

    # Transcribe the audio file
    transcript = transcriber.transcribe(audio_path)
    return transcript.text

def fetch_youtube_transcript(youtube_url):
    # Extract video ID from the YouTube URL using regex
    video_id_match = re.match(r'^.*(?:youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=)([^#\&\?]*).*', youtube_url)
    if video_id_match:
        video_id = video_id_match.group(1)
    else:
        print("Invalid YouTube URL.")
        return None

    try:
        # Get available transcripts for the video
        transcripts = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcripts])
        return transcript_text

    except (TranscriptsDisabled, NoTranscriptAvailable, VideoUnavailable) as e:
        print("No transcript available or transcripts are disabled for this video.")
        return None
    except Exception as e:
        print("Error:", e)
        return None


def calculate_speed_factor(uid):
    video_file = f"temp/{uid}.mp4"
    audio_file = f"outputs/{uid}.mp3"

    if not (os.path.exists(video_file) and os.path.exists(audio_file)):
        app.logger.debug(f'Video file {video_file} or audio file {audio_file} not found.')
        return

    video = VideoFileClip(video_file)
    audio = AudioFileClip(audio_file)
    return audio.duration/video.duration

def speed_up_audio(uid):
    input_file = f"outputs/{uid}.mp3"
    output_file = f"temp/{uid}.mp3"
    speed_factor = calculate_speed_factor(uid)

    ffmpeg_command = [
        "ffmpeg",
        "-i", input_file,
        "-filter:a", f"atempo={speed_factor}",
        output_file
    ]

    subprocess.run(ffmpeg_command + ["-y"])

def replace_audio(uid):
    current_folder = os.getcwd()
    video_file = f"temp/{uid}.mp4"
    audio_file = f"temp/{uid}.mp3"

    if not (os.path.exists(video_file) and os.path.exists(audio_file)):
        app.logger.debug(f'Video file {video_file} or audio file {audio_file} not found.')
        return

    video = VideoFileClip(video_file)
    audio = AudioFileClip(audio_file)
    video_with_new_audio = video.set_audio(audio)
    video_with_new_audio.write_videofile(os.path.join(current_folder, f'outputs/{uid}.mp4'))

def send_to_openai(transcript, lang):
    4000-(len(transcript)//4)
    openai_url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('OPENAI_API_KEY')  # Replace with your API key
    }
    example_notes = """
Write notes on the transcript in markdown this is proper markdown formatting:

# 🧱 The Fall of the Berlin Wall ✊

## Overview 📄
The fall of the Berlin Wall on November 9, 1989, marked a significant turning point in world history. It symbolized the end of the Cold War and paved the way for German reunification and the broader collapse of Communist regimes in Eastern Europe.
> "Important Quote goes here"

## Background 📚
* **Construction**: The Berlin Wall was constructed by the German Democratic Republic (GDR) starting on August 13, 1961.
* **Purpose**: It was built to prevent East Germans from fleeing to West Berlin and subsequently to West Germany.
* **Symbolism**: The Wall became a symbol of the Iron Curtain and the division of Europe.
> "more important blockquote"

## Key Events Leading to the Fall 📅
1. **Reform Movements**: Throughout the 1980s, Eastern Bloc countries experienced significant political and social reforms.
2. **Hungary's Border Opening**: In May 1989, Hungary began dismantling its border fence with Austria, creating a breach in the Iron Curtain.
3. **Mass Protests**: Demonstrations in East Germany grew, culminating in massive protests in Leipzig and other cities.
4. **Political Changes**: The GDR leadership was forced to make concessions, including granting travel permissions.
> "here is a multiple paragraph
>
> blockquote"

## The Night of November 9, 1989 🌙
* **Press Conference**: GDR official Günter Schabowski mistakenly announced that East Germans could cross the border freely, effective immediately.
* **Border Openings**: Thousands of East Berliners flocked to the Wall, overwhelming the border guards.
* **Celebrations**: The Wall was breached, and East and West Germans celebrated together, tearing down sections of the Wall.

## Aftermath 🌅
* **German Reunification**: On October 3, 1990, East and West Germany were officially reunified.
* **Impact on Europe**: The fall of the Berlin Wall accelerated the collapse of other Communist regimes in Eastern Europe.
* **Global Significance**: It marked a victory for democracy and freedom, reshaping global geopolitics.

## Conclusion 🔚
The fall of the Berlin Wall remains a powerful symbol of the triumph of freedom over oppression. It stands as a reminder of the profound impact that the desire for liberty and unity can have on the course of history.

## Further Reading 📖
* [History.com: The Berlin Wall](https://www.history.com/topics/cold-war/berlin-wall)
* [BBC: Fall of the Berlin Wall](https://www.bbc.com/news/world-europe-50299106)
* [Smithsonian Magazine: The Day the Berlin Wall Fell](https://www.smithsonianmag.com/history/the-day-the-berlin-wall-came-down-180973128/)
"""
    data = {
        'model': 'gpt-3.5-turbo',
        "messages": [{"role": "system", "content": f"You are a student helper that takes video transcripts and take notes in a selected language. Write really good notes by bolding main concepts(in each title put an emoji next to it that explains the title) and explaining them in bullet points making subtopics using numbers, using important quotes which you put in blockquote format with (> ) and :{example_notes}"},
                   {"role": "user","content": f"take marksown notes in {lang} using this transcript: {transcript}"}],
        "max_tokens":  2000,  # Adjust as needed
    }

    response = requests.post(openai_url, headers=headers, json=data)
    if response.status_code == 200:
        app.logger.debug(response.json()['choices'][0]['message']['content'])
        return response.json()['choices'][0]['message']['content']
    else:
        app.logger.debug(f"Error from OpenAI: {response.text}")
        return "Error in processing notes"
    
def send_to_openai1(prompt):
    transcript = global_translated_text
    4000 - (len(transcript) // 4)
    openai_url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('OPENAI_API_KEY')  # Replace with your API key
    }
    data = {
        'model': 'gpt-3.5-turbo',
        "messages": [
            {"role": "system", "content": "You are a student helper that takes video transcripts, text in pdf, audio transcript and uses prompts to answer questions, make quizzes, take notes, etc."},
            {"role": "user", "content": f"{prompt} using this in this language({global_output_language}): {transcript}"}
        ],
        "max_tokens": 2000,  # Adjust as needed
    }

    response = requests.post(openai_url, headers=headers, json=data)
    if response.status_code == 200:
        app.logger.debug(response.json()['choices'][0]['message']['content'])
        return response.json()['choices'][0]['message']['content']
    else:
        app.logger.debug(f"Error from OpenAI: {response.text}")
        return "Error in processing notes"
    


def flashcards(transcript):
    4000 - (len(transcript) // 4)
    openai_url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('OPENAI_API_KEY')  # Replace with your API key
    }
    data = {
        'model': 'gpt-3.5-turbo',
        "messages": [{"role": "system", "content": "You are a flashcard maker, return in the format: {\"question\": the question, \"answer\": the answer}, for each flashcard and SEPARATE EACH FLASHCARD WITH A COMMA (essentially json formatted). Make the flashcards quizzable questions and key concepts in 10 flashcards or more"},
                     {"role": "user", "content": 'Make flashcards in ' + global_output_language + ' out of this video transcript. Please return in the format {"question": the question, "answer": the answer} for each flashcard and SEPARATE EACH FLASHCARD WITH A COMMA (essentially json formatted). Here is the video transcript: ' + transcript, }],
        "max_tokens": 2000,  # Adjust as needed
    }

    response = requests.post(openai_url, headers=headers, json=data)
    if response.status_code == 200:
        ai_response = response.json()['choices'][0]['message']['content']
        app.logger.debug(ai_response)
        # Correct the formatting
        corrected_response = correct_flashcard_format(ai_response)
        return corrected_response
    else:
        app.logger.debug(f"Error from OpenAI: {response.text}")
        return "Error in processing notes"

def correct_flashcard_format(response_text):
    # Insert commas where necessary
    formatted_text = response_text.replace("\n", "")
    formatted_text = response_text.replace("}{", "}, {")
    formatted_text = response_text.replace("} {", "}, {")

    # Ensure it's a valid JSON array format
    if not formatted_text.startswith("["):
        formatted_text = "[" + formatted_text
    if not formatted_text.endswith("]"):
        formatted_text += "]"
    return formatted_text
# Route for processing the YouTube video


def split_text(text, limit=4000):
    """
    Splits the text into chunks that are smaller than the specified limit,
    trying to avoid cutting in the middle of a sentence.
    """
    sentences = text.split('. ')
    chunks = []
    current_chunk = sentences[0]

    for sentence in sentences[1:]:
        if len(current_chunk) + len(sentence) + 1 <= limit:
            current_chunk += '. ' + sentence
        else:
            chunks.append(current_chunk)
            current_chunk = sentence
    chunks.append(current_chunk)  # Add the last chunk
    return chunks

def translate_text(text, source_lang='auto', target_lang='en'):
    """
    Translates text that might be longer than the limit by splitting it into chunks,
    translating each chunk, and then concatenating the results.
    """
    chunks = split_text(text)
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    translated_chunks = [translator.translate(chunk) for chunk in chunks]
    return ' '.join(translated_chunks)

@app.route('/check_video_length', methods=['POST'])
def check_video_length():
    try:
        data = request.json
        youtube_url = data.get('youtube_url')  # Match the key with the frontend code

        if not youtube_url:
            return "No YouTube URL provided", 400  # Bad Request

        video_long = is_video_long(youtube_url)

        response_data = {"video_long": video_long}  # Match the key with the frontend code
        response = make_response(response_data, 200)  # Status code 200 for OK
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        error_response = make_response("No", 500)  # Status code 500 for Internal Server Error
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response
    
@app.route('/processPDF', methods=['POST'])

def process_pdf():
    try:
        app.logger.debug('/processPDF')
        global global_translated_text
        global global_output_language

        # Get the file from the request
        uploaded_file = request.files['file']
        lang = request.form['lang']
        lang2 = request.form['lang2']
        uid = request.form['uid']
        global_output_language = lang

        if uploaded_file:
            # Create the "pdf" directory if it doesn't exist
            pdf_directory = os.path.join("pdf")
            if not os.path.exists(pdf_directory):
                os.makedirs(pdf_directory)

            # Save the PDF file to a specific location using uid
            pdf_filename = f"{uid}.pdf"
            pdf_path = os.path.join(pdf_directory, pdf_filename)
            uploaded_file.save(pdf_path)

            # Convert PDF to TXT using convertapi
            app.logger.debug("PDF to TXT")
            txt_filename = f"{uid}.txt"
            txt_path = os.path.join(pdf_directory, txt_filename)
            convertapi.api_secret = 'PhK92ENuyvxM6pqt'
            convertapi.convert('txt', {'File': pdf_path}, from_format='pdf').save_files(txt_path)

            # Read the TXT file
            app.logger.debug("Reading TXT")
            with open(txt_path, 'r') as txt_file:
                transcript = txt_file.read()
                global_translated_text = transcript

            # Make notes and flashcards
            app.logger.debug("making notes")
            openai_response = send_to_openai(transcript, lang)
            app.logger.debug("making flashcards")
            try:
                flashcard_response = json.loads(flashcards(transcript))
            except:
                flashcard_response = json.loads('{"error": "error"}')

            response_data = {
                "notes": openai_response,
                "flashcards": flashcard_response,
                "transcript": transcript,
                "vidCheck": "PDF",
            }

            response = make_response(response_data, 200)  # Status code 200 for OK
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        # Create an error response with the Access-Control-Allow-Origin header
        error_response = make_response("No", 500)  # Status code 500 for Internal Server Error
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response

@app.route('/process', methods=['POST'])

def process():
    try:
        app.logger.debug('/process')
        # Get data from POST request body
        global global_translated_text
        global global_output_language
        data = request.json
        app.logger.debug(json.dumps(data, indent=2))
        youtube_link = data.get('youtube_link')
        lang = data.get('lang')
        lang2 = data.get('lang2')
        uid = data.get('uid')
        global_output_language=lang

        if not youtube_link or not lang:
            return "No", 400  # Bad Request

        # Check for YouTube transcript
        app.logger.debug("Checking for YouTube transcript")
        transcript = fetch_youtube_transcript(youtube_link)

        if transcript:
            app.logger.debug("YouTube transcript found")
        else:
            app.logger.debug("YouTube transcript not found, using Assembly AI")
            # Process the video and audio
            audio_filename = download_audio(youtube_link, uid)
            app.logger.debug("Starting Transcription")
            transcript = transcribe(audio_filename, lang2)
        app.logger.debug("Downloading YouTube video")
        video_output_path = download_video(youtube_link, uid)
        
        # Check if the video was successfully downloaded
        if os.path.exists(video_output_path):
            app.logger.debug(f"Video downloaded successfully: {video_output_path}")
        else:
            app.logger.debug("Video download failed")
        global_translated_text = transcript
        
        # Transcribe and translate the audio file
        
        # Send transcript to OpenAI for processing
        app.logger.debug("making notes")
        openai_response = send_to_openai(transcript, lang)
        app.logger.debug("making flashcards")
        try:
            flashcard_response = json.loads(flashcards(transcript))
        except:
            flashcard_response = json.loads('{"error": "error"}')

        
        # If everything goes well, return notes
        response_data = {"notes": openai_response,
                         "flashcards": flashcard_response, 
                         "transcript": transcript,
                }
        

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)  # Status code 200 for OK
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        # Create an error response with the Access-Control-Allow-Origin header
        error_response = make_response("No", 500)  # Status code 500 for Internal Server Error
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response

@app.route('/processvid', methods=['POST'])

def process_video1():
    app.logger.debug('/processvid')
    try:
        # Get data from POST request body
        global global_translated_text
        global global_output_language
        data = request.json
        youtube_link = data.get('youtube_link')
        lang = data.get('lang')
        lang2 = data.get('lang2')
        uid = data.get('uid')
        global_output_language=lang

        if not youtube_link or not lang:
            return "No", 400  # Bad Request

        # Process the video and audio
        
        check = True
        # Transcribe and translate the audio file
        if lang != lang2:
            #translate(transcript, lang)
            app.logger.debug("translating")
            gtts_lang_code = LANGUAGE_MAPPING1.get(lang)
            translated = translate_text(global_translated_text, target_lang=gtts_lang_code)
            app.logger.debug("Generating Audio")
            generate_audio(translated, lang, uid)
            app.logger.debug("speeding up audio")
            speed_up_audio(uid)
            app.logger.debug("making video")
            replace_audio(uid)
        else:
            check = False
            app.logger.debug("downloading original video")
            download_video_again(youtube_link, uid)

        
        vidCheck = "VideoURL"
        # If everything goes well, return notes
        response_data = {
                         "check": check,
                         "vidCheck": vidCheck,}
        

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)  # Status code 200 for OK
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        # Create an error response with the Access-Control-Allow-Origin header
        error_response = make_response("No", 500)  # Status code 500 for Internal Server Error
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response

@app.route('/process_audio', methods=['POST'])

def process_audio():
    app.logger.debug('/process_audio')
    try:
        global global_translated_text
        global global_output_language
        lang = request.form['lang']
        lang2 = request.form['lang2']
        uid = request.form['uid']
        global_output_language = lang

        uploaded_file = request.files['file']
        if not os.path.exists("temp"):
            os.makedirs("temp")
        uploaded_file.save(os.path.join('temp', f'{uid}.mp3'))
        if lang == lang2:
            if not os.path.exists("outputs"):
                os.makedirs("outputs")
            uploaded_file.save(os.path.join('outputs', f'{uid}.mp3'))
        audio_file_path = os.path.join('temp', f'{uid}.mp3')

        # Process the audio
        app.logger.debug("Starting Transcription")
        transcript = transcribe(audio_file_path, lang2)
        global_translated_text=transcript

        # Translate the audio if languages are different

        # Send transcript to OpenAI for processing
        app.logger.debug("Writing notes")
        openai_response = send_to_openai(transcript, lang)
        app.logger.debug("Writing flashcards")
        try:
            flashcard_response = json.loads(flashcards(transcript))
        except:
            flashcard_response = json.loads('{"error": "error"}')

        response_data = {"notes": openai_response,
                         "flashcards": flashcard_response, 
                         "transcript": transcript,}

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        error_response = make_response("No", 500)
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response
    
@app.route('/process_audio2', methods=['POST'])
def process_audio2():
    app.logger.debug('/process_audio2')
    try:
        global global_translated_text
        global global_output_language
        lang = request.form['lang']
        lang2 = request.form['lang2']
        uid = request.form['uid']
        global_output_language = lang

        # Translate the audio if languages are different
        
        app.logger.debug("Translating")
        gtts_lang_code = LANGUAGE_MAPPING1.get(lang)
        translated = translate_text(global_translated_text, target_lang=gtts_lang_code)
        app.logger.debug("Generating Audio")
        generate_audio(translated, lang, uid)

        # Send transcript to OpenAI for processing

        response_data = {"vidCheck": "audio"}

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        error_response = make_response("No", 500)
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response

@app.route('/process_video_file', methods=['POST'])
def process_video_file():
    app.logger.debug('/process_video_file')
    try:
        global global_translated_text
        lang = request.form['lang']
        lang2 = request.form['lang2']
        uid = request.form['uid']

        uploaded_file = request.files['file']
        if not os.path.exists("temp"):
            os.makedirs("temp")
        uploaded_mp4_path = os.path.join('temp', f'{uid}.mp4')
        uploaded_file.save(uploaded_mp4_path)   

        if lang == lang2:
            if not os.path.exists("outputs"):
                os.makedirs("outputs")
            output_mp4_path = os.path.join('outputs', f'{uid}.mp4')
            uploaded_file.save(output_mp4_path)

        audio_clip = VideoFileClip(uploaded_mp4_path).audio
        audio_file_path = os.path.join('temp', f'{uid}.mp3')
        audio_clip.write_audiofile(audio_file_path, codec='mp3')

        # Close the audio clip to release resources
        audio_clip.close()

        # Process the audio
        app.logger.debug("Starting Transcription")
        transcript = transcribe(audio_file_path, lang2)
        global_translated_text=transcript
        app.logger.debug("Writing notes")
        # Send transcript to OpenAI for processing
        openai_response = send_to_openai(transcript, lang)
        app.logger.debug("Writing Flashcards")
        try:
            flashcard_response = json.loads(flashcards(transcript))
        except:
            flashcard_response = json.loads('{"error": "error"}')

        response_data = {"notes": openai_response,
                         "flashcards": flashcard_response, 
                         "transcript": transcript,
                        }

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        error_response = make_response("No", 500)
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response
    
@app.route('/process_video_file2', methods=['POST'])
def process_video_file2():
    app.logger.debug('/process_video_file2')
    try:
        # Get data from POST request body
        global global_translated_text
        global global_output_language
        data = request.json
        lang = data.get('lang')
        lang2 = data.get('lang2')
        uid = data.get('uid')
        global_output_language=lang

        # Process the video and audio
        
        check = True
        # Transcribe and translate the audio file
        if lang != lang2:
            app.logger.debug("translating")
            gtts_lang_code = LANGUAGE_MAPPING1.get(lang)
            translated = translate_text(global_translated_text, target_lang=gtts_lang_code)
            app.logger.debug("Generating Audio")
            generate_audio(translated, lang, uid)
            app.logger.debug("speeding up audio")
            speed_up_audio(uid)
            app.logger.debug("making video")
            replace_audio(uid)
        
        
        vidCheck = "VideoURL"
        # If everything goes well, return notes
        response_data = {
                         "check": check,
                         "vidCheck": vidCheck,}
        

        # Create the response with the Access-Control-Allow-Origin header
        response = make_response(response_data, 200)  # Status code 200 for OK
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
        # Create an error response with the Access-Control-Allow-Origin header
        error_response = make_response("No", 500)  # Status code 500 for Internal Server Error
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response


@app.route('/processGPT', methods=['POST'])
def gptResponse():
    app.logger.debug('/processGPT')
    data = request.json
    prompt = data.get('prompt')
    gptResponse = send_to_openai1(prompt)
    response_data = {"gptResponse": gptResponse}
    response = make_response(response_data, 200)  # Status code 200 for OK
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/outputs/<filename>')
def serve_file(filename):
    app.logger.debug('/outputs/<filename>')
    output_dir = os.path.join("outputs")  # Path relative to the script location
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return send_from_directory('outputs', filename)

@app.route('/ping')
def ping():
    app.logger.debug('/ping')
    return "pong"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
