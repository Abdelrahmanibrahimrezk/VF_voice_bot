import os
import streamlit as st
from openai import OpenAI
import base64
import time
from voice_api import record_voice
from config import Config

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
def split_text_for_tts(text, max_length=4000):
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

# Function to handle text-to-speech
def speak_text(text, ai_message):
    try:
        # Display the AI message
        print_chat_message(ai_message)

        # Split text into chunks
        text_chunks = split_text_for_tts(text)

        # Prepare list of audio base64 chunks
        audio_b64_chunks = []

        for i, chunk in enumerate(text_chunks):
            if chunk.strip():
                try:
                    response = client.audio.speech.create(
                        model="tts-1",  # use correct model
                        voice="alloy",
                        input=chunk,
                    )
                    audio_bytes = response.read()
                    b64_audio = base64.b64encode(audio_bytes).decode()
                    audio_b64_chunks.append(b64_audio)
                except Exception as e:
                    st.error(f"❌ TTS chunk {i} generation failed: {str(e)}")

        # Generate JavaScript to play each chunk sequentially
        js_chunks = ""
        for i, b64 in enumerate(audio_b64_chunks):
            js_chunks += f"""
                audios[{i}] = new Audio("data:audio/mp3;base64,{b64}");
            """

        js_play_sequence = """
        <script>
            const audios = [];
            let current = 0;

            function playNext() {
                if (current < audios.length) {
                    audios[current].onended = playNext;
                    audios[current].play();
                    current++;
                }
            }

            """ + js_chunks + """
            playNext();
        </script>
        """

        st.components.v1.html(js_play_sequence, height=0)
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
