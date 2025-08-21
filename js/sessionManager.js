const { launchBrowser, joinMeetAndRecord } = require("./meet_record");

class SessionManager {
  constructor() {
    this.sessions = new Map(); // sessionId → session data
  }

  async startSession(email, password, sessionId, meetCode, wsPort, chatPort) {
    const session = {
      sessionId,
      meetCode,
      wsPort,
      chatPort,
      browser: null,
      page: null,
      currentStream: null,
      ws: null,
      chatWS: null,
      terminateRequested: false,
      speakerTrackerTask: null,
    };

    try {
      const { browser, page } = await launchBrowser();
      session.browser = browser;
      session.page = page;

      this.sessions.set(sessionId, session);

      joinMeetAndRecord(email, password, session, page, meetCode, wsPort, chatPort)
        .catch(err => {
          console.error(`Session ${sessionId} crashed:`, err.message);
        });

      return { status: "started", sessionId };
    } catch (err) {
      console.error("Failed to start session:", err);
      return { status: "error", message: err.message };
    }
  }

  async cleanup(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return;

    session.terminateRequested = true;

    if (session.page && !session.page.isClosed()) {
      try {
        await session.page.close();
      } catch (e) {
        console.warn("Page close failed:", e.message);
      }
    }

    if (session.speakerTrackerTask) {
      try {
        await session.speakerTrackerTask;
      } catch (e) {
        console.warn("Speaker tracker error:", e.message);
      }
    }

    if (session.browser) {
      try {
        const pages = await session.browser.pages();
        if (pages.length <= 1) {
          await session.browser.close();
        }
      } catch (e) {
        console.warn("Browser close failed:", e.message);
      }
    }

    if (session.currentStream) {
      try {
        session.currentStream.destroy();
      } catch {}
    }

    if (session.chatWS && session.chatWS.readyState === session.chatWS.OPEN) {
      try { session.chatWS.close(); } catch {}
    }
    if (session.ws && session.ws.readyState === session.ws.OPEN) {
      session.ws.close();
    }

    this.sessions.delete(sessionId);
  }

  async terminate(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return { status: "not found" };

    await this.cleanup(sessionId);
    return { status: "terminated" };
  }

  listSessions() {
    return Array.from(this.sessions.values()).map(session => ({
      sessionId: session.sessionId,
      meetCode: session.meetCode,
    }));
  }
}

module.exports = { SessionManager };
