import streamlit as st
from streamlit_mic_recorder import mic_recorder
import io
import openai
from openai import OpenAI

# 🔑 Set your OpenAI API key

# Initialize OpenAI client using secrets
def get_openai_client():
    try:
        # Get API key from Streamlit secrets
        api_key = st.secrets["openai"]["api_key"]
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing OpenAI client: {str(e)}")
        st.error("Please make sure you've set up your OpenAI API key in Streamlit Secrets.")
        return None

# Get the client
client = get_openai_client()

def record_voice(language="en"):
    """
    Record voice input and use OpenAI Whisper API (v1.0+) for transcription.
    """
    audio = mic_recorder(
        start_prompt="🎤 Click and speak to ask question",
        stop_prompt="⚠️Stop recording🚨",
        just_once=True,
        use_container_width=True
    )
    
    if audio is not None:
        try:
            audio_bytes = audio['bytes']
            audio_stream = io.BytesIO(audio_bytes)
            audio_stream.name = "audio.wav"  # Required for OpenAI API
            
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_stream,
                language=language
            )
            
            return response.text.strip()
        except Exception as e:
            st.error(f"Transcription error:\n\n{e}")
            return None
    return None