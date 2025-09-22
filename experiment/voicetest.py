import pyttsx3

def text_to_speech(text):
    # Initialize the engine
    engine = pyttsx3.init()

    # Optional: set voice properties
    engine.setProperty("rate", 150)   # Speed (words per minute)
    engine.setProperty("volume", 1.0) # Volume (0.0 to 1.0)

    # List available voices (male/female, different accents)
    voices = engine.getProperty("voices")
    for i, voice in enumerate(voices):
        print(f"Voice {i}: {voice.name} ({voice.id})")

    # Choose a voice (e.g., 0 = first, 1 = second)
    engine.setProperty("voice", voices[0].id)

    # Speak the text
    engine.say(text)
    engine.runAndWait()

if __name__ == "__main__":
    sample_text = "Hello! This is a text to speech demo using pyttsx3."
    text_to_speech(sample_text)
