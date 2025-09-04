/**
 * Sleep utility function
 */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let globalStepCounter = 1;

/**
 * Takes screenshot and logs step
 */
async function logStep(page, message, stepCounter = null, folder = "") {
  const counter = stepCounter || globalStepCounter++;
  const folderPath = folder ? `${folder}/` : "";
  const filename = `js/screenshots/${folderPath}step_${String(counter).padStart(2, "0")}_${message.replace(/\s+/g, "_")}.png`;
  
  try {
    await page.screenshot({ path: filename, fullPage: true });
    console.log(`📸 ${message} - screenshot saved: ${filename}`);
  } catch (error) {
    console.error(`Failed to take screenshot: ${error.message}`);
  }
}

/**
 * Starts periodic screenshots and keypresses to keep session alive
 */
function startMinuteScreenshots(page, sessionState, label = "minute_tick", intervalMs = 60000) {
  if (!sessionState) sessionState = {};
  if (sessionState.minuteInterval) clearInterval(sessionState.minuteInterval);

  let running = false;

  const minuteInterval = setInterval(async () => {
    if (running) return;
    if (sessionState.terminateRequested || !page || page.isClosed()) return;

    running = true;
    try {
      await page.bringToFront();
      await page.keyboard.press("Shift");
      await logStep(page, label);
    } catch (e) {
      console.error("❌ minute task error:", e);
    } finally {
      running = false;
    }
  }, intervalMs);

  sessionState.minuteInterval = minuteInterval;
  return minuteInterval;
}

/**
 * Generates unique session ID
 */
function generateSessionId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Validates email format
 */
function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validates meeting code format
 */
function isValidMeetCode(code) {
  // Google Meet codes are typically 3 groups of 4 characters separated by dashes
  const meetCodeRegex = /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/i;
  return meetCodeRegex.test(code) || code.length >= 10;
}

/**
 * Safe JSON parse with fallback
 */
function safeJsonParse(str, fallback = null) {
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
}

/**
 * Retry function with exponential backoff
 */
async function retry(fn, maxAttempts = 3, baseDelay = 1000) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxAttempts) throw error;
      
      const delay = baseDelay * Math.pow(2, attempt - 1);
      console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
      await sleep(delay);
    }
  }
}

module.exports = {
  sleep,
  logStep,
  startMinuteScreenshots,
  generateSessionId,
  isValidEmail,
  isValidMeetCode,
  safeJsonParse,
  retry
};