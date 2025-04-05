import os
import streamlit as st
from openai import OpenAI
import base64
import time
import uuid
from voice_api import record_voice
from config import Config
import concurrent.futures

# Set page configuration as the very first Streamlit command
st.set_page_config(page_title="🎙️ Vodafone | Gen AI Consultant", layout="wide")

# Initialize OpenAI client using secrets
@st.cache_resource
def get_openai_client():
    try:
        api_key = st.secrets["openai"]["api_key"]
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing OpenAI client: {str(e)}")
        return None

# Get the client
client = get_openai_client()

# Function to encode image to base64
def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Function to split text into chunks of maximum length
def split_text_for_tts(text, max_length=2000):
    """
    Split text into chunks that fit within the TTS character limit
    
    Args:
        text (str): Text to split
        max_length (int): Maximum length of each chunk
    
    Returns:
        list: List of text chunks
    """
    # Split by sentences for more natural breaks
    sentences = []
    for paragraph in text.split('\n'):
        for sentence in paragraph.split('. '):
            if sentence:
                sentences.append(sentence + ('' if sentence.endswith('.') else '.'))
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed the limit, start a new chunk
        if len(current_chunk) + len(sentence) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

# Function to generate speech for a single chunk
def generate_speech(chunk):
    """
    Generate speech for a text chunk using OpenAI's TTS API
    
    Args:
        chunk (str): Text chunk to convert to speech
    
    Returns:
        str: Base64 encoded audio data
    """
    try:
        # Use a faster voice model
        response = client.audio.speech.create(
            model="tts-1-echo",  # Using the faster model
            voice="alloy",
            input=chunk,
        )
        
        # Convert response directly to base64
        audio_bytes = response.read()
        return base64.b64encode(audio_bytes).decode()
    except Exception as e:
        st.error(f"❌ TTS chunk generation failed: {str(e)}")
        return None

# Function to handle text-to-speech with sequential playback
def speak_text(text, ai_message):
    """
    Generate speech using OpenAI's Text-to-Speech API and play sequentially
    
    Args:
        text (str): Text to convert to speech
        ai_message (dict): The AI message for display
    """
    try:
        print_chat_message(ai_message)
        
        # Split text into chunks that fit within the TTS character limit
        text_chunks = split_text_for_tts(text)
        
        # Process chunks in parallel to generate audio
        audio_elements = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chunk = {executor.submit(generate_speech, chunk): i for i, chunk in enumerate(text_chunks)}
            # Sort by original chunk order
            for i in range(len(text_chunks)):
                for future, idx in future_to_chunk.items():
                    if idx == i and future.done():
                        b64_audio = future.result()
                        if b64_audio:
                            audio_elements.append(b64_audio)
                        break
        
        # Create sequential audio player with callbacks
        if audio_elements:
            # Create unique IDs for each audio element
            audio_ids = [f"audio-{uuid.uuid4()}" for _ in range(len(audio_elements))]
            
            # Create custom JavaScript to handle sequential playback
            js_code = """
            <script>
                const audioIds = %s;
                const audioElements = [];
                
                function setupAudio() {
                    for (let i = 0; i < audioIds.length; i++) {
                        const audio = document.getElementById(audioIds[i]);
                        audioElements.push(audio);
                        
                        // Connect sequential playback
                        if (i < audioIds.length - 1) {
                            audio.onended = function() {
                                audioElements[i+1].play();
                            };
                        }
                    }
                    
                    // Start playing the first audio
                    if (audioElements.length > 0) {
                        audioElements[0].play();
                    }
                }
                
                // Setup after a short delay to ensure elements are loaded
                setTimeout(setupAudio, 100);
            </script>
            """ % str(audio_ids)
            
            # Add audio elements to the page (hidden)
            for i, b64_audio in enumerate(audio_elements):
                audio_html = f"""
                <audio id="{audio_ids[i]}" preload="auto" hidden>
                    <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
                </audio>
                """
                st.markdown(audio_html, unsafe_allow_html=True)
            
            # Add the JavaScript for sequential playback
            st.markdown(js_code, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"❌ TTS failed: {str(e)}")

# Function to print chat messages with the right formatting
def print_chat_message(message):
    text = message["content"]
    if message["role"] == "user":
        with st.chat_message("user", avatar="🎙️"):
            st.markdown(text)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(text)

# Function to get answer from the model directly
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
    
    # Sidebar for input method selection
    st.sidebar.title("Ask your question")
    
    # Toggle between voice and text input
    input_method = st.sidebar.radio("Input Method", ["Text", "Voice"])
    
    # Get user question based on selected input method
    question = None
    
    if input_method == "Voice":
        with st.sidebar:
            st.write("Click to record your voice question:")
            question = record_voice(language="en")
    else:  # Text input
        with st.sidebar:
            question = st.text_area("Type your question:", height=100)
            if st.button("Submit"):
                # This will trigger the question processing
                st.session_state["submitted"] = True
            else:
                # If the button wasn't pressed, don't process empty text input
                if not st.session_state.get("submitted", False):
                    question = None
    
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
        
        # Convert answer to speech
        speak_text(answer, ai_message)
        
        # Add the message to history
        st.session_state.chat_history.append(ai_message)
        
        # Keep only last 20 messages for context window management
        if len(st.session_state.chat_history) > 20:
            st.session_state.chat_history = st.session_state.chat_history[-20:]
        
        # Reset the submitted state for text input
        st.session_state["submitted"] = False

if __name__ == "__main__":
    main()
