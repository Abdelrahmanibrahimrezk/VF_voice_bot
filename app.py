import os
import streamlit as st
from openai import OpenAI
import base64
import time
from voice_api import record_voice
from config import Config

# Configuration settings (from both files)
st.set_page_config(page_title="🎙️ Vodafone | Gen AI Consultant", layout="wide")
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


# Function to encode image to base64
def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Function to handle text-to-speech
def speak_text(text, lang="en"):
    """
    Generate speech using OpenAI's Text-to-Speech API
    
    Args:
        text (str): Text to convert to speech
        lang (str): Language code (currently supports 'en' and 'ar')
    """
    try:
        # Select voice based on language
        voice = "alloy" if lang == "en" else "shimmer"
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
        )
        
        # Convert response directly to base64
        audio_bytes = response.read()
        b64_audio = base64.b64encode(audio_bytes).decode()
        
        # Inject hidden autoplay audio using HTML
        audio_html = f"""
        <audio autoplay="true" hidden>
            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"❌ TTS failed: {str(e)}")

# Function to print text with RTL support for Arabic
def print_txt(text):
    if any("\u0600" <= c <= "\u06FF" for c in text):  # Arabic text detection
        text = f"<p style='direction: rtl; text-align: right;'>{text}</p>"
    st.markdown(text, unsafe_allow_html=True)

# Function to print chat messages with the right formatting
def print_chat_message(message):
    text = message["content"]
    if message["role"] == "user":
        with st.chat_message("user", avatar="🎙️"):
            print_txt(text)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            print_txt(text)

# Function to get answer from the model directly (replacing streaming)
def get_answer(question, history=[]):
    if question.strip() == "":
        return Config.fall_back_msg
    
    messages = [
        {"role": "system", "content": Config.prompt}
    ]
    
    # Add chat history
    for i, conv in enumerate(history):
        # Skip the first message if it's an intro
        if i == 0:
            continue
        messages.append(conv)
    
    # Add the current question
    messages.append({"role": "user", "content": question})
    
    try:
        # Call the OpenAI API directly (non-streaming)
        response = client.chat.completions.create(
            model=Config.model,
            messages=messages,
            temperature=Config.temperature,
            top_p=1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# Main function
def main():
    
    
    # Try to load the logo
    try:
        image_base64 = get_base64_image("./vodafone.png")
        st.markdown(
            f"""
            <h1>
                <img src="data:image/png;base64,{image_base64}" width="70" style="vertical-align:middle; margin-right:10px;">
                <b>Vodafone | <span style='color:red;'>Gen AI Consultant</span></b>
            </h1>
            """,
            unsafe_allow_html=True
        )
    except Exception:
        st.title("🎙️ Vodafone | Gen AI Consultant")
    
    # Sidebar for language selection and voice input
    st.sidebar.title("Ask your question in English or Arabic")
    
    def language_selector():
        with st.sidebar:
            return st.selectbox("Speech Language", ["en", "ar"])
    
    with st.sidebar:
        question = record_voice(language=language_selector())
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Show previous messages
    for message in st.session_state.chat_history:
        print_chat_message(message)
    
    # Process new question if provided
    if question:
        user_message = {"role": "user", "content": question}
        st.session_state.chat_history.append(user_message)
        print_chat_message(user_message)
        
        # Get answer directly from the model
        answer = get_answer(question, st.session_state.chat_history)
        
        # Display the answer
        ai_message = {"role": "assistant", "content": answer}
        print_chat_message(ai_message)
        
        # Convert answer to speech
        lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in answer) else "en"
        speak_text(answer, lang=lang)
        
        # Add the message to history
        st.session_state.chat_history.append(ai_message)
        
        # Keep only last 20 messages for context window management
        if len(st.session_state.chat_history) > 20:
            st.session_state.chat_history = st.session_state.chat_history[-20:]

if __name__ == "__main__":
    main()
