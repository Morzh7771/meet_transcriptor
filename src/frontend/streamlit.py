import streamlit as st
import os
import sys
 
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)
from src.backend.core.facade import MeetAudioFacade
from src.backend.utils.logger import CustomLog

log = CustomLog()

st.set_page_config(page_title="Google Meet AudioBot", layout="centered")

st.title("🎙 Google Meet AudioBot")

if "facade" not in st.session_state:
    st.session_state.facade = MeetAudioFacade()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

meet_code = st.text_input("Enter Google Meet code", placeholder="e.g. abc-defg-hij")

if st.button("Send Bot to Google Meet"):
    if meet_code:
        try:
            meet_link = f"https://meet.google.com/{meet_code}"
            st.session_state.facade.start(meet_link)
            st.success("Bot started and recording...")
            log.info(f"Bot started for meeting link: {meet_link}")
        except Exception as e:
            st.error(f"Error starting bot: {e}")
            log.error(f"Error starting bot: {e}")
    else:
        st.error("Please enter a meeting code.")

if st.button("Disconnect the bot from Google Meet"):
    try:
        st.session_state.facade.stop()
        st.success("Bot stopped and audio saved.")
        log.info("Bot stopped and audio saved.")
    except Exception as e:
        st.error(f"Error stopping bot: {e}")
        log.error(f"Error stopping bot: {e}")

if st.session_state.facade.last_audio_file:
    st.info(f"Last recorded file: {st.session_state.facade.last_audio_file}")

if st.session_state.facade.last_transcript:
    st.subheader("📝 Transcript:")
    st.write(st.session_state.facade.last_transcript)

    st.subheader("💬 Chat about the transcript")

    # replay chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # chat input
    user_question = st.chat_input("Ask your question here...")
    if user_question:
        st.session_state.chat_history.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.write(user_question)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            with st.spinner("Thinking..."):
                try:
                    for chunk in st.session_state.facade.ask_question(user_question):
                        full_response += chunk
                        response_placeholder.markdown(full_response)
                except Exception as e:
                    st.error(f"Error while generating streamed answer: {e}")
                    log.error(f"ChatBot streaming error: {e}")
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
