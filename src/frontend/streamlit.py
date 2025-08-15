import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)
import streamlit as st
import asyncio
import concurrent.futures

from src.backend.core.Facade import Facade
from src.backend.utils.logger import CustomLog

log = CustomLog()

class StreamlitAsyncManager:
    @staticmethod
    def run_async(coro):
        """Execute async coroutine safely in Streamlit context"""

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                log.info(f"Thread execution result: {result}")
                return result
            except Exception as e:
                log.error(f"Error in thread execution: {e}")
                raise e
            finally:
                loop.close()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return asyncio.run(coro)
        except RuntimeError:
            return asyncio.run(coro)
        except Exception as e:
            log.error(f"Error in StreamlitAsyncManager: {e}")
            raise e

@st.cache_resource
def get_initialized_facade():
    async def init_facade():
        facade = Facade()
        return facade

    try:
        facade = StreamlitAsyncManager.run_async(init_facade())
        log.info("Facade initialized successfully")
        return facade
    except Exception as e:
        log.error(f"Error initializing facade: {e}")
        raise e

def get_facade():
    if 'facade' not in st.session_state:
        st.session_state.facade = get_initialized_facade()
        st.session_state.facade_initialized = True
    return st.session_state.facade

def run(meet_code, duration):
    with st.spinner(" The bot enters the rally and starts recording..."):
        async def _process(meet_code, duration):
            facade = get_facade()
            try:
                response = await facade.run_google_meet_recording(meet_code, duration)
                st.success("✅ Done! Audio and transcript saved.")
                return response
            except Exception as e:
                log.error(f"Error while recording: {e}")
                st.error(f"❌ Error: {e}")
                raise e

        return StreamlitAsyncManager.run_async(_process(meet_code, duration))

def main():
    st.set_page_config(page_title="🎙 Google Meet Recorder", layout="centered")
    st.title("🎙 Google Meet Audio Recorder with Whisper")
    st.markdown("Launches a bot in Google Meet, records audio and transcribes it via Whisper.")

    meet_code = st.text_input("Enter the rally code (for example: jsa-vatt-ovo)", "jsa-vatt-ovo")
    duration = st.slider("Recording duration (sec)", min_value=30, max_value=600, value=60, step=30)

    if st.button(" Start recording"):
        if not meet_code:
            st.warning("❗ Please enter the rally code.")
        else:
            run(meet_code, duration)

if __name__ == "__main__":
    main()