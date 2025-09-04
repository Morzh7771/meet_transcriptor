const WebSocket = require('ws');
const { getStream } = require('puppeteer-stream');
const { trackSpeakersAndChat, sendMessageToChat } = require('../browser/meetActions');
const { cleanupSession } = require('../browser/browserManager');

/**
 * Initializes WebSocket connections for audio streaming and chat
 */
async function initializeWebSockets(page, sessionState, port, chatPort, timeStart) {
  const ws = new WebSocket(`ws://localhost:${port}`);
  const chatWS = new WebSocket(`ws://localhost:${chatPort}`);
  
  sessionState.ws = ws;
  sessionState.chatWS = chatWS;

  // Audio WebSocket connection
  ws.on("open", async () => {
    console.log("Audio WebSocket connected");
    
    const currentStream = await getStream(page, {
      audio: true,
      video: false,
      mimeType: "audio/webm; codecs=opus",
      audioBitsPerSecond: 128000
    });

    sessionState.currentStream = currentStream;

    currentStream.on("data", chunk => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(chunk);
      }
    });

    // Start tracking speakers and chat
    sessionState.speakerTrackerTask = trackSpeakersAndChat(
      page, 
      ws, 
      chatWS, 
      sessionState, 
      timeStart
    );
  });

  // Chat WebSocket message handling
  chatWS.on("message", async (msg) => {
    const message = msg.toString().trim();
    
    if (message === "terminate") {
      await cleanupSession(sessionState);
      return;
    }
    
    if (!message.startsWith("{")) return;
    
    try {
      const payload = JSON.parse(message);
      if (payload.type === "chat_response") {
        await sendMessageToChat(page, payload.message);
      }
    } catch (e) {
      console.error("Error parsing chat message:", e);
    }
  });

  // Audio WebSocket message handling
  ws.on("message", async (msg) => {
    const command = msg.toString().trim();
    console.log("Received command:", command);
    
    try {
      if (command === "terminate") {
        await cleanupSession(sessionState);
        return;
      }
      
      if (command === "restart-stream") {
        await restartAudioStream(page, sessionState, ws);
      }
    } catch (e) {
      console.error("Error handling WebSocket message:", e);
    }
  });

  // WebSocket error handling
  ws.on("error", (error) => {
    console.error("Audio WebSocket error:", error);
  });

  chatWS.on("error", (error) => {
    console.error("Chat WebSocket error:", error);
  });
}

/**
 * Restarts audio stream
 */
async function restartAudioStream(page, sessionState, ws) {
  if (sessionState.currentStream) {
    try { 
      sessionState.currentStream.destroy(); 
    } catch {}
  }

  if (!page || page.isClosed()) return;

  try {
    const stream = await getStream(page, {
      audio: true,
      video: false,
      mimeType: "audio/webm; codecs=opus",
      audioBitsPerSecond: 128000
    });

    sessionState.currentStream = stream;
    stream.on("data", chunk => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(chunk);
      }
    });
    
    console.log("Audio stream restarted");
  } catch (error) {
    console.error("Failed to restart audio stream:", error);
  }
}

module.exports = {
  initializeWebSockets,
  restartAudioStream
};