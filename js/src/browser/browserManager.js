const { launch } = require("puppeteer-stream");
const { executablePath } = require("puppeteer");
const WebSocket = require("ws");

/**
 * Launches new browser instance
 */
async function launchBrowser() {
  const browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ['--mute-audio'],
    args: [
      "--disable-notifications",
      "--window-size=1920,1080",
      "--autoplay-policy=no-user-gesture-required",
      "--no-sandbox",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-features=TranslateUI",
      "--disable-extensions",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "--disable-backgrounding-occluded-windows",
      "--disable-features=AudioServiceOutOfProcess",
      "--autoplay-policy=no-user-gesture-required",
      "--disable-features=CalculateNativeWinOcclusion",
    ],
    closeDelay: 2000,
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  
  return { browser, page };
}

/**
 * Keeps audio context alive to prevent suspension
 */
async function keepAudioAlive(page) {
  await page.evaluate(() => {
    try {
      if (window.__silence_src) {
        window.__silence_src.stop();
        window.__silence_src = null;
      }
      if (window.__silence_ctx) {
        window.__silence_ctx.close();
        window.__silence_ctx = null;
      }

      const AC = window.AudioContext || window.webkitAudioContext;
      const ctx = new AC();
      
      if (ctx.state === 'suspended') {
        ctx.resume();
      }
      
      const src = ctx.createBufferSource();
      const buf = ctx.createBuffer(1, ctx.sampleRate * 0.1, ctx.sampleRate);
      
      const data = buf.getChannelData(0);
      for (let i = 0; i < data.length; i++) {
        data[i] = (Math.random() - 0.5) * 0.001;
      }
      
      src.buffer = buf;
      src.loop = true;
      src.connect(ctx.destination);
      src.start();
      
      window.__silence_ctx = ctx;
      window.__silence_src = src;
      
      window.__audioKeepAlive = setInterval(() => {
        if (ctx.state === 'suspended') {
          console.log('reload suspended audio context');
          ctx.resume();
        }
        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Shift'}));
        document.dispatchEvent(new MouseEvent('mousemove'));
      }, 5000);
      
      console.log("🔊 Silent audio keepalive started");
    } catch (e) {
      console.error("keepAudioAlive error:", e);
    }
  });
}

/**
 * Cleans up session resources
 */
async function cleanupSession(sessionState) {
  const { ws, chatWS, browser, currentStream, speakerTrackerTask, minuteInterval } = sessionState;
  sessionState.terminateRequested = true;

  console.log("Starting cleanup session...");

  // Stop minute interval
  if (minuteInterval) {
    clearInterval(minuteInterval);
  }

  // Close audio stream
  if (currentStream) {
    try { 
      currentStream.destroy(); 
      console.log("Audio stream destroyed");
    } catch (e) {
      console.error("Error destroying stream:", e);
    }
  }

  // Close WebSocket connections
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.close();
      console.log("Audio WebSocket closed");
    } catch (e) {
      console.error("Error closing audio WebSocket:", e);
    }
  }

  if (chatWS && chatWS.readyState === WebSocket.OPEN) {
    try { 
      chatWS.close(); 
      console.log("Chat WebSocket closed");
    } catch (e) {
      console.error("Error closing chat WebSocket:", e);
    }
  }

  // Wait for speaker tracker task to complete
  if (speakerTrackerTask) {
    try {
      await speakerTrackerTask;
      console.log("Speaker tracker stopped");
    } catch (e) {
      console.error("Error stopping speaker tracker:", e);
    }
  }

  // Close browser
  if (browser) {
    try { 
      await browser.close(); 
      console.log("Browser closed");
    } catch (e) {
      console.error("Error closing browser:", e);
    }
  }

  // Reset session state
  sessionState.browser = null;
  sessionState.ws = null;
  sessionState.chatWS = null;
  sessionState.currentStream = null;
  sessionState.speakerTrackerTask = null;
  sessionState.minuteInterval = null;
  sessionState.terminateRequested = false;

  console.log("Session cleanup completed");
}

module.exports = {
  launchBrowser,
  keepAudioAlive,
  cleanupSession
};