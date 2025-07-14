import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.backend.utils.logger import CustomLog

log = CustomLog()

class JoinGoogleMeet:
    def __init__(self):
        self.meet_link = os.getenv("MEET_LINK")
        if not self.meet_link:
            raise ValueError("MEET_LINK is missing in environment variables.")

        chrome_options = Options()
        
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--lang=en")
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream_mic": 2,
            "profile.default_content_setting_values.media_stream_camera": 2,
            "profile.default_content_setting_values.notifications": 2
        })
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def wait_for_admission(self, timeout=60):
        try:
            # подождать появления кнопки "Leave call" (означает, что бот реально ВНУТРИ)
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Leave call']"))
            )
            log.info("Bot has been admitted to the meeting.")
            return True
        except:
            log.error("Bot was not admitted to the meeting in time.")
            return False
    
    def join_meet(self):
        log.info(f"Navigating to the meeting {self.meet_link}")
        self.driver.get(self.meet_link)
        time.sleep(5)

        # enter guest name
        try:
            name_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Your name']"))
            )
            name_input.clear()
            name_input.send_keys("AudioBot")
            log.info("Guest name set to 'AudioBot'")
        except:
            log.warning("Name input field not found — maybe already signed in.")

        # continue without mic/camera
        try:
            continue_without_mic_cam = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Continue without microphone and camera')]"))
            )
            continue_without_mic_cam.click()
            log.info("Continued without microphone and camera.")
        except:
            log.warning("Continue button not found — possibly already skipped.")

        # join the meeting
        try:
            join_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(),'Ask to join')]]"))
            )
            join_button.click()
            log.info("Join button clicked successfully.")
            time.sleep(5)
        except:
            log.error("Join button not found.")
