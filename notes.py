import os
import pyaudio
import wave
import speech_recognition as sr
import pyttsx3
import json
import threading

BASE_DIR = "course_audios"
os.makedirs(BASE_DIR, exist_ok=True)

SETTINGS_FILE = "user_settings.json"
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"first_time": True,"playback_rate": 1.0}, f)

stop_flag = threading.Event()
pause_flag = threading.Event()

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def recognize_speech(prompt=None, silent=False):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    if prompt and not silent:
        speak(prompt)

    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        while True:
            try:
                audio = recognizer.listen(source, timeout=10)
                return recognizer.recognize_google(audio).lower()
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                if not silent:
                    speak("Network error. Please check your connection.")
                return None

def check_first_time():
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
    if settings.get("first_time", True):
        speak("Welcome to the Course Audio Manager! Let's begin.")
        speak("Say 'help' at any time to know what you can do.")
        settings["first_time"] = False
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

def listen_for_stop_command():
    while not stop_flag.is_set():
        command = recognize_speech(silent=True)
        if command:
            if "stop recording" in command:
                stop_flag.set()
            elif "pause playback" in command:
                pause_flag.set()
            elif "resume playback" in command:
                pause_flag.clear()

def list_courses():
    courses = sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])
    if not courses:
        speak("No courses found.")
        return []
    speak("Here are your available courses:")
    for course in courses:
        speak(course)
    return courses

def list_recordings(course_name):
    course_dir = os.path.join(BASE_DIR, course_name)
    if not os.path.exists(course_dir):
        speak(f"Course {course_name} does not exist.")
        return []
    files = [f for f in os.listdir(course_dir) if f.endswith(".wav")]
    files.sort(key=lambda f: os.path.getctime(os.path.join(course_dir, f)), reverse=True)
    if not files:
        speak("No recordings found in this course.")
        return []
    speak("Recordings from newest to oldest. Say 'play' if you hear the one you want.")
    for f in files:
        speak(f[:-4])
        command = recognize_speech(silent=True)
        if command == "play":
            play_audio(course_name, f[:-4])
            return [f[:-4]]
    return [f[:-4] for f in files]

def record_audio(course_name, file_name):
    stop_flag.clear()
    course_dir = os.path.join(BASE_DIR, course_name)
    os.makedirs(course_dir, exist_ok=True)

    file_path = os.path.join(course_dir, f"{file_name}.wav")

    while os.path.exists(file_path):
        speak(f"A file named {file_name} already exists in course {course_name}. Say 'yes' to overwrite or 'no' to rename.")
        response = recognize_speech()
        if response == "yes":
            break
        elif response == "no":
            file_name = recognize_speech("Please say a new file name.")
            file_path = os.path.join(course_dir, f"{file_name}.wav")
        else:
            speak("Sorry, I didn't understand. Please say 'yes' or 'no'.")

    chunk = 1024
    format = pyaudio.paInt16
    channels = 1
    rate = 16000
    frames = []

    p = pyaudio.PyAudio()
    stream = p.open(format=format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)

    speak("Recording started. Say 'stop recording' to stop.")
    listener_thread = threading.Thread(target=listen_for_stop_command)
    listener_thread.start()

    while not stop_flag.is_set():
        data = stream.read(chunk, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()
    listener_thread.join()

    if frames:
        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(format))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
        speak(f"Recording saved as {file_name} in course {course_name}.")
    else:
        speak("No audio was recorded.")

def play_audio(course_name, file_name):
    stop_flag.clear()
    pause_flag.clear()
    course_dir = os.path.join(BASE_DIR, course_name)
    file_path = os.path.join(course_dir, f"{file_name}.wav")

    if not os.path.exists(file_path):
        speak(f"The file {file_name} in course {course_name} was not found.")
        return

    speak(f"Playing {file_name}. Say 'pause playback' or 'resume playback'.")
    wf = wave.open(file_path, 'rb')
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

    listener_thread = threading.Thread(target=listen_for_stop_command)
    listener_thread.start()

    chunk = 1024
    data = wf.readframes(chunk)
    while data and not stop_flag.is_set():
        if pause_flag.is_set():
            continue
        stream.write(data)
        data = wf.readframes(chunk)

    stream.stop_stream()
    stream.close()
    p.terminate()
    wf.close()
    listener_thread.join()
    speak("Playback finished.")

def help_menu():
    speak("Here are the commands you can say:")
    speak("'record' to start a new recording.")
    speak("'play' to listen to a saved recording.")
    speak("'list courses' to hear all available folders.")
    speak("'list recordings' to explore files in a course.")
    speak("'help' to hear these instructions again.")
    speak("'exit' to end the session.")

def main():
    check_first_time()
    continue_session = True
    while continue_session:
        user_input = recognize_speech("Say 'record', 'play', 'list courses', 'list recordings', 'help', or 'exit'.")
        if not user_input:
            continue

        if "record" in user_input:
            course_name = recognize_speech("Say the course name.")
            file_name = recognize_speech("Say the file name.")
            if course_name and file_name:
                record_audio(course_name, file_name)

        elif "play" in user_input:
            courses = list_courses()
            if not courses:
                continue
            course_name = recognize_speech("Say the course name to explore.")
            if course_name not in courses:
                speak(f"Course {course_name} not found.")
                continue
            files = list_recordings(course_name)
            if not files:
                continue
            file_name = recognize_speech("Say the file name to play.")
            if file_name in files:
                # play_audio(course_name, file_name)
                course_dir = os.path.join(BASE_DIR, course_name)
                file_path = os.path.join(course_dir, f"{file_name}.wav")
                print("ah you are here????? so return????")
                return file_path
                

            else:
                speak(f"File {file_name} not found in course {course_name}.")

        elif "list courses" in user_input:
            list_courses()

        elif "list recordings" in user_input:
            courses = list_courses()
            if not courses:
                continue
            course_name = recognize_speech("Say the course name to explore recordings.")
            if course_name in courses:
                list_recordings(course_name)
            else:
                speak(f"Course {course_name} not found.")

        elif "help" in user_input:
            help_menu()

        elif "exit" in user_input:
            speak("Goodbye!")
            break

        next_action = recognize_speech("Would you like to do anything else? Say 'yes' or 'no'.")
        if next_action != "yes":
            speak("Session ended. See you next time!")
            continue_session = False
