const { launchBrowser, keepAudioAlive, cleanupSession } = require('../browser/browserManager');
const { 
  waitMeetJoin, 
  tabUntilAllClassesMatch, 
  openDropdown,
  findChat,
  findPeople,
  trackSpeakersAndChat
} = require('../browser/meetActions');
const { initializeWebSockets } = require('../websocket/wsHandler');
const { logStep, sleep, startMinuteScreenshots } = require('../utils/helpers');

class SessionManager {
  constructor() {
    this.sessions = new Map();
  }

  /**
   * Starts new recording session
   */
  async startSession(email, password, sessionId, meetCode, port, chatPort) {
    const sessionState = {
      sessionId,
      email,
      meetCode,
      terminateRequested: false,
      browser: null,
      page: null,
      ws: null,
      chatWS: null,
      currentStream: null,
      speakerTrackerTask: null,
      minuteInterval: null
    };

    try {
      const { browser, page } = await launchBrowser();
      sessionState.browser = browser;
      sessionState.page = page;

      // Login to Google
      await this.performLogin(page, email, password);
      
      // Join Meet
      await this.joinMeet(page, meetCode);
      
      // Setup recording
      await this.setupRecording(page, sessionState, port, chatPort);

      this.sessions.set(sessionId, sessionState);
      
      return { 
        status: "Session started successfully",
        meetCode,
        sessionId 
      };
    } catch (error) {
      await cleanupSession(sessionState);
      throw error;
    }
  }

  /**
   * Performs Google login
   */
  async performLogin(page, email, password) {
    const fs = require('fs');
    if (!fs.existsSync("js/screenshots")) fs.mkdirSync("js/screenshots", { recursive: true });

    await page.goto("https://accounts.google.com/", { waitUntil: "networkidle2" });
    await page.browser().defaultBrowserContext().overridePermissions("https://meet.google.com/", ["microphone", "camera", "notifications"]);
    await logStep(page, "Login page");

    await page.waitForSelector('input[type="email"]');
    await page.click('input[type="email"]');
    await page.keyboard.type(email, { delay: 150 });
    await sleep(500);
    await logStep(page, "Email typed");
    await page.click("#identifierNext");

    await page.waitForSelector('input[type="password"]', { visible: true });
    await sleep(700);
    await page.keyboard.type(password, { delay: 120 });
    await sleep(500);
    await logStep(page, "Password typed");
    await page.click("#passwordNext");
    await page.waitForNavigation({ waitUntil: "networkidle2" });
    await sleep(2000);
  }

  /**
   * Joins Google Meet
   */
  async joinMeet(page, meetCode) {
    await page.goto("https://meet.google.com/", { waitUntil: "networkidle2" });
    await logStep(page, "Meet homepage");
    await sleep(2000);
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('input[type="text"]');
    await page.click('input[type="text"]');
    await page.keyboard.type(meetCode, { delay: 120 });
    await logStep(page, "Meeting code typed");
    await sleep(400);
    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: "networkidle2" });
    await logStep(page, "Meeting page");

   

    await tabUntilAllClassesMatch(page);
    await page.keyboard.press("Enter");
    await logStep(page, "Joined meeting");
    await sleep(3000);

    await waitMeetJoin(page);
    await logStep(page, "Meeting entered");
    await sleep(5000);
    await page.keyboard.press('Enter');
    await sleep(2000);

    let buttons = await openDropdown(page);
    await findChat(buttons);
    await sleep(1500);
    await findPeople(buttons,page);

    await logStep(page, "Participants panel");
    await sleep(1000);
  }

  /**
   * Sets up recording and WebSocket connections
   */
  async setupRecording(page, sessionState, port, chatPort) {
    await keepAudioAlive(page);
    startMinuteScreenshots(page, sessionState);

    const timeStart = Date.now();
    await initializeWebSockets(page, sessionState, port, chatPort, timeStart);
  }

  /**
   * Terminates session
   */
  async terminate(sessionId) {
    const sessionState = this.sessions.get(sessionId);
    
    if (!sessionState) {
      return { status: "Session not found", sessionId };
    }

    try {
      console.log(`Terminating session ${sessionId}...`);
      await cleanupSession(sessionState);
      this.sessions.delete(sessionId);
      console.log(`Session ${sessionId} terminated successfully`);
      
      return { 
        status: "Session terminated successfully", 
        sessionId 
      };
    } catch (error) {
      console.error(`Error terminating session ${sessionId}:`, error);
      // Still remove from sessions even if cleanup failed
      this.sessions.delete(sessionId);
      
      return {
        status: "Session terminated with errors",
        sessionId,
        error: error.message
      };
    }
  }

  /**
   * Lists all active sessions
   */
  listSessions() {
    const sessionList = [];
    
    for (const [sessionId, state] of this.sessions.entries()) {
      sessionList.push({
        sessionId,
        email: state.email,
        meetCode: state.meetCode,
        status: state.terminateRequested ? 'terminating' : 'active'
      });
    }
    
    return { sessions: sessionList };
  }
}

module.exports = new SessionManager();