const { launchBrowser, joinMeetAndRecord } = require("./meet_record");

class SessionManager {
  constructor() {
    this.sessions = new Map(); // sessionId → session object
  }

  async startSession(email, password, sessionId, meetCode, wsPort) {
    const session = {
      sessionId,
      meetCode,
      wsPort,
      browser: null,
      page: null,
      currentStream: null,
      ws: null,
      terminateRequested: false,
      speakerTrackerTask: null,
    };

    try {
      const { browser, page } = await launchBrowser();
      session.browser = browser;
      session.page = page;

      this.sessions.set(sessionId, session);

      console.log(`✅ Started session ${sessionId} for meet ${meetCode}`);

      joinMeetAndRecord(email, password, session, page, meetCode, wsPort)
        .catch(err => {
          console.error(`❌ Session ${sessionId} crashed:`, err.message);
        })

      return { status: "started", sessionId };
    } catch (err) {
      console.error("🔥 Failed to start session:", err);
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
        console.warn("⚠️ Failed to close page:", e.message);
      }
    }

    if (session.speakerTrackerTask) {
      try {
        await session.speakerTrackerTask;
      } catch (e) {
        console.warn("⚠️ Error in speaker tracker:", e.message);
      }
    }

    if (session.browser) {
      try {
        const pages = await session.browser.pages();
        if (pages.length <= 1) {
          await session.browser.close();
        }
      } catch (e) {
        console.warn("⚠️ Failed to close browser:", e.message);
      }
    }

    if (session.currentStream) {
      try {
        session.currentStream.destroy();
      } catch (e) {}
    }

    if (session.ws && session.ws.readyState === session.ws.OPEN) {
      session.ws.close();
    }

    this.sessions.delete(sessionId);
    console.log(`🧹 Session ${sessionId} cleaned up`);
  }

  listSessions() {
    return Array.from(this.sessions.values()).map(s => ({
      sessionId: s.sessionId,
      meetCode: s.meetCode,
    }));
  }

  async terminate(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return { status: "not found" };
    await this.cleanup(sessionId);
    return { status: "terminated" };
  }
}

module.exports = { SessionManager };
