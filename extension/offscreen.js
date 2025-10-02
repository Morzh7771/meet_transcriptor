/* global getRoomIdFromUrl, getMimeType */

let config = {
  apiBase: "http://127.0.0.1:8000",
  room: "",
  chunkMs: 15000,
  desktop: false,
};

let tabStream = null;
let micStream = null;
let mixedStream = null;

let isRunning = false;
let websocket = null;
let websocketPort = null;
let websocketPingInterval = null;

let chatWebsocket = null;
let chatWebsocketPort = null;
let chatWebsocketPingInterval = null;

let mediaRecorder = null;
const MEDIAREC_TIMESLICE = 200; // ms

let currentSpeakerStates = {};
let speakerUpdateInterval = null;
const SPEAKER_UPDATE_INTERVAL = 100; // 100ms

// Track restart state
let isRestarting = false;
let accumulatedChunkData = [];  // Store data chunks for current recording
let isFirstStart = true;  // Track if this is the first start


// Speaker state helpers
const areStatesEqual = (oldStates, newStates) => {
  const oldKeys = Object.keys(oldStates);
  const newKeys = Object.keys(newStates);
  if (oldKeys.length !== newKeys.length) return false;
  for (const k of newKeys) {
    if (oldStates[k] !== newStates[k]) return false;
  }
  return true;
};

const logStateChanges = (oldStates, newStates) => {
  for (const [name, now] of Object.entries(newStates)) {
    const was = oldStates[name] || false;
    if (was !== now) {
      console.log(`[offscreen] ${name} -> ${now ? "TRUE" : "FALSE"}`);
    }
  }
};

const sendCurrentSpeakerStates = () => {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) return;
  const msg = {
    type: "speakers",
    speakers: currentSpeakerStates,
    time: Date.now(),
  };
  try {
    websocket.send(JSON.stringify(msg));
  } catch (e) {
    console.error("[offscreen] Failed to send speaker states:", e);
  }
};

const updateSpeakerStates = (newStates) => {
  if (!newStates || typeof newStates !== "object") return;
  const changed = !areStatesEqual(currentSpeakerStates, newStates);
  if (changed) {
    logStateChanges(currentSpeakerStates, newStates);
    currentSpeakerStates = { ...newStates };
    if (isRunning) sendCurrentSpeakerStates();
  }
};

const startSpeakerStateUpdates = () => {
  if (speakerUpdateInterval) clearInterval(speakerUpdateInterval);
  speakerUpdateInterval = setInterval(() => {
    if (isRunning) sendCurrentSpeakerStates();
  }, SPEAKER_UPDATE_INTERVAL);
  console.log("[offscreen] Started speaker state updates");
};

const stopSpeakerStateUpdates = () => {
  if (speakerUpdateInterval) {
    clearInterval(speakerUpdateInterval);
    speakerUpdateInterval = null;
  }
  // Do NOT reset currentSpeakerStates - speakers should be tracked continuously
  console.log("[offscreen] Stopped speaker state updates");
};

// Capture helpers - improved from file 2
const captureMic = async () => {
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1
      },
      video: false
    });
  } catch (e) {
    console.warn("[offscreen] mic failed:", e);
    return null;
  }
};

const captureTab = async () => {
  console.log("[offscreen] Requesting display media for browser audio with tab selection dialog");
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        systemAudio: "include",
        channelCount: 1
      },
      video: {
        mediaSource: 'tab'
      }
    });
    
    // Stop video tracks since we only need audio
    stream.getVideoTracks().forEach((track) => track.stop());
    console.log("[offscreen] Tab audio captured successfully");
    return stream;
  } catch (e) {
    console.warn("[offscreen] Tab audio capture failed:", e);
    return null;
  }
};

const captureDesktop = async () => {
  console.log("[offscreen] Requesting display media for desktop audio");
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      audio: { 
        echoCancellation: false, 
        noiseSuppression: false, 
        systemAudio: "include",
        channelCount: 1
      },
      video: true,
    });
    // Stop video tracks as we only need audio
    stream.getVideoTracks().forEach((track) => track.stop());
    console.log("[offscreen] Desktop audio captured successfully");
    return stream;
  } catch (e) {
    console.warn("[offscreen] Desktop audio capture failed:", e);
    throw e;
  }
};

// Backend session / WebSocket
const startSession = async () => {
  try {
    const meetCode = getRoomIdFromUrl(config.room) || config.room;
    console.log(config.clientId,config.consultantId)
     const requestBody = {
      client_id: config.clientId || "d4dee85f-ebf7-46d3-a60f-a562d12bd328",
      consultant_id: config.consultantId || "68f997c0-95d5-4c88-b0c6-c5c13061ec2a",
      meet_code: meetCode,
      meeting_language: "ru"
    };

    const res = await fetch(`${config.apiBase}/start`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Failed to start session: ${res.status} - ${text}`);
    }
    const data = await res.json();
    if (data.ok === false) throw new Error(data.error || "Backend returned ok: false");
    websocketPort = data.ws_port;
    chatWebsocketPort = data.chat_port;
    if (!websocketPort) throw new Error("No ws_port in backend response");
    if (!chatWebsocketPort) throw new Error("No chat_port in backend response");
    console.log("[offscreen] Got WebSocket port:", websocketPort);
    console.log("[offscreen] Got Chat WebSocket port:", chatWebsocketPort);
    return { websocketPort, chatWebsocketPort };
  } catch (e) {
    console.error("[offscreen] Failed to start session:", e);
    throw e;
  }
};

const startWebSocketPing = () => {
  if (websocketPingInterval) clearInterval(websocketPingInterval);
  websocketPingInterval = setInterval(() => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      try {
        websocket.send(JSON.stringify({ type: "ping", timestamp: Date.now() }));
      } catch (e) {
        console.warn("[offscreen] Failed to send ping:", e);
      }
    }
  }, 5000);
};

const stopWebSocketPing = () => {
  if (websocketPingInterval) {
    clearInterval(websocketPingInterval);
    websocketPingInterval = null;
  }
};

const startChatWebSocketPing = () => {
  if (chatWebsocketPingInterval) clearInterval(chatWebsocketPingInterval);
  chatWebsocketPingInterval = setInterval(() => {
    if (chatWebsocket && chatWebsocket.readyState === WebSocket.OPEN) {
      try {
        chatWebsocket.send(JSON.stringify({ type: "ping", timestamp: Date.now() }));
      } catch (e) {
        console.warn("[offscreen] Failed to send chat ping:", e);
      }
    }
  }, 5000);
};

const stopChatWebSocketPing = () => {
  if (chatWebsocketPingInterval) {
    clearInterval(chatWebsocketPingInterval);
    chatWebsocketPingInterval = null;
  }
};

// Format violation data for display
const formatViolationMessage = (violationData) => {
  if (!violationData || typeof violationData !== 'object') {
    return JSON.stringify(violationData);
  }
  
  // Format the violation data in a readable way
  const lines = [];
  for (const [key, value] of Object.entries(violationData)) {
    if (typeof value === 'object' && value !== null) {
      lines.push(`${key}: ${JSON.stringify(value, null, 2)}`);
    } else {
      lines.push(`${key}: ${value}`);
    }
  }
  
  return lines.join('\n');
};

// MediaRecorder restart logic
const handleRecorderRestart = async () => {
  console.log("[offscreen] Handling MediaRecorder restart command");
  
  if (!mediaRecorder || !isRunning || isRestarting) {
    console.log("[offscreen] No active recorder to restart or already restarting");
    return;
  }
  
  isRestarting = true;
  
  try {
    // Prepare to collect final data from current recording
    accumulatedChunkData = [];
    
    if (mediaRecorder.state !== "inactive") {
      console.log("[offscreen] Stopping current MediaRecorder for restart");
      
      // Create promise to wait for final data and stop event
      const stopPromise = new Promise((resolve) => {
        let dataReceived = false;
        let stopReceived = false;
        
        const checkComplete = () => {
          if (dataReceived && stopReceived) {
            resolve();
          }
        };
        
        // Set timeout as fallback
        const timeout = setTimeout(() => {
          console.warn("[offscreen] Timeout waiting for MediaRecorder finalization");
          resolve();
        }, 3000);
        
        // Override ondataavailable to collect final chunk
        const originalOnDataAvailable = mediaRecorder.ondataavailable;
        mediaRecorder.ondataavailable = (event) => {
          console.log("[offscreen] Receiving final data chunk:", event.data.size, "bytes");
          if (event.data && event.data.size > 0) {
            accumulatedChunkData.push(event.data);
          }
          dataReceived = true;
          checkComplete();
        };
        
        // Override onstop to know when recording is fully stopped
        const originalOnStop = mediaRecorder.onstop;
        mediaRecorder.onstop = (event) => {
          console.log("[offscreen] MediaRecorder fully stopped");
          clearTimeout(timeout);
          stopReceived = true;
          checkComplete();
          
          // Restore original handlers
          if (originalOnDataAvailable) {
            mediaRecorder.ondataavailable = originalOnDataAvailable;
          }
          if (originalOnStop) {
            mediaRecorder.onstop = originalOnStop;
          }
        };
      });
      
      // Stop the recorder
      mediaRecorder.stop();
      
      // Wait for stop to complete
      await stopPromise;
      
      // Send accumulated data as complete chunk if we have any
      if (accumulatedChunkData.length > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
        // Combine all chunks into single blob
        const completeBlob = new Blob(accumulatedChunkData, { type: 'audio/webm' });
        console.log("[offscreen] Sending complete finalized chunk:", completeBlob.size, "bytes");
        
        try {
          // Send the complete finalized chunk
          websocket.send(completeBlob);
          
          // Give backend time to process
          await new Promise(resolve => setTimeout(resolve, 200));
        } catch (e) {
          console.error("[offscreen] Failed to send finalized chunk:", e);
        }
      }
    }
    
    // Clear accumulated data
    accumulatedChunkData = [];
    
    // Start new MediaRecorder with fresh state
    await startWebMRecorder();
    console.log("[offscreen] MediaRecorder restarted successfully");
    
    // Send acknowledgment to backend
    const ackMessage = {
      type: "restart_ready",
      timestamp: Date.now()
    };
    
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      try {
        websocket.send(JSON.stringify(ackMessage));
        console.log("[offscreen] Sent restart acknowledgment to backend");
      } catch (e) {
        console.error("[offscreen] Failed to send restart ack:", e);
      }
    }
    
  } catch (error) {
    console.error("[offscreen] Error during MediaRecorder restart:", error);
    
    // Send error acknowledgment
    try {
      const ackMessage = {
        type: "restart_ready",
        timestamp: Date.now(),
        error: true
      };
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify(ackMessage));
      }
    } catch (e) {
      console.error("[offscreen] Failed to send error ack:", e);
    }
    
    throw error;
  } finally {
    isRestarting = false;
  }
};

const connectWebSocket = async () => {
  if (!websocketPort) throw new Error("WebSocket port not available");
  return new Promise((resolve, reject) => {
    const wsUrl = `ws://localhost:${websocketPort}`;
    console.log("[offscreen] WebSocket URL:", wsUrl);
    websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      console.log("[offscreen] WebSocket connected successfully");
      startWebSocketPing();
      const init = {
        type: "init",
        room: config.room,
        audio_config: {
          format: "webm_opus"
        },
        timestamp: Date.now()
      };
      websocket.send(JSON.stringify(init));
      resolve();
    };

    websocket.onerror = (err) => {
      console.error("[offscreen] WebSocket error:", err);
      stopWebSocketPing();
      reject(new Error(`WebSocket connection failed to ${wsUrl}`));
    };

    websocket.onclose = (event) => {
      console.log("[offscreen] WebSocket closed:", event.code, event.reason);
      stopWebSocketPing();
      if (isRunning && event.code !== 1000) {
        console.log("[offscreen] Reconnecting WebSocket in 2s");
        setTimeout(() => {
          if (isRunning) {
            connectWebSocket().catch(e => console.error("[offscreen] WS reconnection failed:", e));
          }
        }, 2000);
      }
    };

    websocket.onmessage = (event) => {
      try {
        if (typeof event.data === "string") {
          const data = JSON.parse(event.data);
          
          if (data.type === "pong") return;
          
          if (data.type === "init_ack") {
            console.log("[offscreen] Backend ready for WebM streaming");
            return;
          }
          
          if (data.type === "restart_recorder") {
            console.log("[offscreen] Received restart command from backend");
            
            // Handle restart asynchronously
            handleRecorderRestart().then(() => {
              console.log("[offscreen] Restart completed successfully");
            }).catch(e => {
              console.error("[offscreen] MediaRecorder restart failed:", e);
            });
            
            return;
          }
          
          if (data.type === "transcript") {
            chrome.runtime.sendMessage({
              type: "chunk-transcript",
              data: {
                room: config.room,
                processed_text: data.text,
                transcribed: true,
                timestamp: data.timestamp
              }
            }).catch(() => {});
          }
        }
      } catch (e) {
        console.warn("[offscreen] Could not parse WebSocket message:", e);
      }
    };

    setTimeout(() => {
      if (websocket.readyState !== WebSocket.OPEN) {
        try { websocket.close(); } catch {}
        stopWebSocketPing();
        reject(new Error("WebSocket connection timeout"));
      }
    }, 10000);
  });
};

const connectChatWebSocket = async () => {
  if (!chatWebsocketPort) throw new Error("Chat WebSocket port not available");
  return new Promise((resolve, reject) => {
    const wsUrl = `ws://localhost:${chatWebsocketPort}`;
    console.log("[offscreen] Chat WebSocket URL:", wsUrl);
    chatWebsocket = new WebSocket(wsUrl);

    chatWebsocket.onopen = () => {
      console.log("[offscreen] Chat WebSocket connected successfully");
      startChatWebSocketPing();
      resolve();
    };

    chatWebsocket.onerror = (err) => {
      console.error("[offscreen] Chat WebSocket error:", err);
      stopChatWebSocketPing();
      reject(new Error(`Chat WebSocket connection failed to ${wsUrl}`));
    };

    chatWebsocket.onclose = (event) => {
      console.log("[offscreen] Chat WebSocket closed:", event.code, event.reason);
      stopChatWebSocketPing();
      if (isRunning && event.code !== 1000) {
        console.log("[offscreen] Reconnecting Chat WebSocket in 2s");
        setTimeout(() => {
          if (isRunning) {
            connectChatWebSocket().catch(e => console.error("[offscreen] Chat WS reconnection failed:", e));
          }
        }, 2000);
      }
    };

    chatWebsocket.onmessage = (event) => {
      console.log("[offscreen] Chat WebSocket raw event:", event);
      try {
        if (typeof event.data === "string") {
          const data = JSON.parse(event.data);
          
          console.log("[offscreen] Chat WebSocket parsed data:", data);
          
          if (data.type === "pong") return;
          
          if (data.type === "violation_detected") {
            console.log("=== VIOLATION DETECTED ===");
            console.log("Full data object:", JSON.stringify(data, null, 2));
            
            // Extract only the 'res' field from data.data
            let violationText = "";
            if (data.data && typeof data.data === 'object' && data.data.res) {
              violationText = String(data.data.res);
            } else {
              // Fallback: if no 'res' field, show entire data
              violationText = JSON.stringify(data.data, null, 2);
            }
            
            console.log("[offscreen] Sending violation text (res field):", violationText);
            
            // Send to background script, which will forward to content
            chrome.runtime.sendMessage({
              type: "violation-alert",
              message: violationText,
              timestamp: data.timestamp
            }).then(() => {
              console.log("[offscreen] Violation sent to background");
            }).catch((e) => {
              console.error("[offscreen] Failed to send to background:", e);
            });
          }
        }
      } catch (e) {
        console.error("[offscreen] Error parsing Chat WebSocket message:", e);
      }
    };

    setTimeout(() => {
      if (chatWebsocket.readyState !== WebSocket.OPEN) {
        try { chatWebsocket.close(); } catch {}
        stopChatWebSocketPing();
        reject(new Error("Chat WebSocket connection timeout"));
      }
    }, 10000);
  });
};

// Modified startWebMRecorder with improved audio mixing from file 2
const startWebMRecorder = async () => {
  // Stop existing recorder if any
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try {
      mediaRecorder.stop();
      // Wait a bit for cleanup
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (e) {
      console.warn("[offscreen] Error stopping existing recorder:", e);
    }
  }

  // Create audio context with specific sample rate for better quality
  const ac = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  const dest = ac.createMediaStreamDestination();

  // Create gain nodes for mixing
  const tabGain = ac.createGain();
  const micGain = ac.createGain();
  
  tabGain.gain.value = 1.0;
  micGain.gain.value = 1.0;

  let connected = 0;
  
  if (micStream?.getAudioTracks().length) {
    const micSrc = ac.createMediaStreamSource(micStream);
    micSrc.connect(micGain);
    micGain.connect(dest);
    connected++;
    console.log("[offscreen] Mic connected to mix");
  }
  
  if (tabStream?.getAudioTracks().length) {
    const tabSrc = ac.createMediaStreamSource(tabStream);
    tabSrc.connect(tabGain);
    tabGain.connect(dest);
    connected++;
    console.log("[offscreen] Tab audio connected to mix");
  }
  
  if (!connected) throw new Error("No audio sources available for WebM");

  mixedStream = dest.stream;

  const mimeType = getMimeType();
  if (!mimeType || !mimeType.includes("webm")) {
    throw new Error("No supported WebM/Opus mimeType for MediaRecorder");
  }
  console.log("[offscreen] Using MediaRecorder mimeType:", mimeType);

  mediaRecorder = new MediaRecorder(mixedStream, {
    mimeType,
    audioBitsPerSecond: 128000
  });

  // Track data chunks during normal operation
  let normalOperationChunks = [];
  
  mediaRecorder.ondataavailable = (e) => {
    if (!e.data || !e.data.size) return;
    
    // During restart, chunks are accumulated separately
    if (isRestarting) {
      console.log("[offscreen] Ignoring data during restart:", e.data.size, "bytes");
      return;
    }
    
    // During normal operation, send data immediately
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      // Check for backpressure
      if (websocket.bufferedAmount > 2 * 1024 * 1024) {
        console.warn("[offscreen] WS backpressure, dropping chunk");
        return;
      }
      
      try {
        // Don't send data from first start until first restart
        if (!isFirstStart) {
          websocket.send(e.data);
          console.log("[offscreen] Sent audio chunk:", e.data.size, "bytes");
        } else {
          console.log("[offscreen] Skipping initial data until first restart");
        }
      } catch (err) {
        console.error("[offscreen] Failed to send WebM chunk:", err);
      }
    }
  };

  mediaRecorder.onerror = (e) => {
    console.error("[offscreen] MediaRecorder error:", e.error || e);
  };

  // Start recording with timeslice
  mediaRecorder.start(MEDIAREC_TIMESLICE);
  console.log("[offscreen] MediaRecorder started, timeslice:", MEDIAREC_TIMESLICE, "ms");
  
  // After first restart, we can send data normally
  if (isFirstStart && !isRestarting) {
    isFirstStart = false;
  }
};

// Public control (start/stop)
const startCapture = async (opts = {}) => {
  Object.assign(config, {
    apiBase: opts.apiBase || config.apiBase,
    room: opts.room || String(Date.now()),
    chunkMs: Math.max(1000, Math.min(120000, opts.chunkMs || config.chunkMs)),
    desktop: !!opts.desktop,
    clientId: opts.clientId,
    consultantId: opts.consultantId
  });

  isRunning = true;
  isRestarting = false;

  try {
    console.log("[offscreen] Capturing audio streams first");
    
    // Get mic stream first
    micStream = await captureMic();
    
    // Get tab/desktop stream using improved logic - FIRST before WebSocket
    try {
      if (config.desktop) {
        tabStream = await captureDesktop();
      } else {
        tabStream = await captureTab();
      }
    } catch (e) {
      console.warn("[offscreen] Primary capture failed:", e);
      if (config.desktop) {
        // Fallback to tab capture if desktop fails
        try {
          tabStream = await captureTab();
          console.log("[offscreen] Fallback to tab audio successful");
        } catch (fallbackError) {
          console.warn("[offscreen] Fallback tab capture also failed:", fallbackError);
          tabStream = null;
        }
      } else {
        tabStream = null;
      }
    }

    // Verify we have at least one audio source
    const hasTabAudio = tabStream?.getAudioTracks().length > 0;
    const hasMicAudio = micStream?.getAudioTracks().length > 0;
    
    if (!hasTabAudio && !hasMicAudio) {
      throw new Error("No audio sources available");
    }
    
    console.log("[offscreen] Audio sources - Tab:", hasTabAudio, "Mic:", hasMicAudio);

    // Only after successful audio capture, connect to backend
    console.log("[offscreen] Starting WebM session and requesting WebSocket port");
    await startSession();

    console.log("[offscreen] Waiting 5s for backend to open WebSocket port");
    await new Promise(r => setTimeout(r, 20000));

    console.log("[offscreen] Connecting WebSocket");
    await connectWebSocket();

    console.log("[offscreen] Connecting Chat WebSocket");
    await connectChatWebSocket();

    // Start recording with the captured streams
    await startWebMRecorder();

    // Speakers - alongside, JSON
    startSpeakerStateUpdates();

    console.log("[offscreen] Started WebM audio streaming successfully");
    return { ok: true };
  } catch (e) {
    console.error("[offscreen] Failed to start WebM streaming:", e);
    isRunning = false;
    isRestarting = false;
    stopWebSocketPing();
    
    // Clean up any captured streams if WebSocket setup failed
    [tabStream, micStream].forEach((s) => {
      if (s) s.getTracks().forEach(t => t.stop());
    });
    tabStream = micStream = null;
    
    return Promise.reject(e);
  }
};

const stopCapture = async () => {
  console.log("[offscreen] Stopping capture - closing WebSocket connection");
  isRunning = false;
  isRestarting = false;

  stopSpeakerStateUpdates();
  stopWebSocketPing();
  stopChatWebSocketPing();

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try { 
      mediaRecorder.stop(); 
      console.log("[offscreen] MediaRecorder stopped");
    } catch {}
  }
  mediaRecorder = null;

  if (mixedStream) {
    mixedStream.getTracks().forEach(t => t.stop());
    mixedStream = null;
  }

  // Simply close WebSocket - backend handles everything itself
  if (websocket) {
    if (websocket.readyState === WebSocket.OPEN) {
      try {
        console.log("[offscreen] Sending end message and closing WebSocket");
        websocket.send(JSON.stringify({ type: "end", room: config.room, timestamp: Date.now() }));
        await new Promise(r => setTimeout(r, 100)); // Give time to send
      } catch {}
    }
    try { 
      websocket.close(); 
      console.log("[offscreen] WebSocket closed");
    } catch {}
    websocket = null;
  }

  if (chatWebsocket) {
    if (chatWebsocket.readyState === WebSocket.OPEN) {
      try {
        console.log("[offscreen] Closing Chat WebSocket");
        await new Promise(r => setTimeout(r, 100));
      } catch {}
    }
    try { 
      chatWebsocket.close(); 
      console.log("[offscreen] Chat WebSocket closed");
    } catch {}
    chatWebsocket = null;
  }

  [tabStream, micStream].forEach((s) => {
    if (s) s.getTracks().forEach(t => t.stop());
  });
  tabStream = micStream = null;
  websocketPort = null;
  chatWebsocketPort = null;

  console.log("[offscreen] Stopped WebM audio streaming");
};

const setMicEnabled = (enabled) => {
  if (micStream) {
    micStream.getAudioTracks().forEach((track) => (track.enabled = enabled));
    console.log("[offscreen] mic enabled:", enabled);
  }
};

// Message handler
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("[offscreen] Received message:", msg?.type);

  switch (msg?.type) {
    case "offscreen-start":
      console.log("[offscreen] Processing WebM start request with opts:", msg.opts);
      startCapture(msg.opts)
        .then(() => sendResponse({ ok: true }))
        .catch((e) => {
          console.error("[offscreen] WebM start failed:", e);
          sendResponse({ ok: false, error: e.message || String(e) });
        });
      return true;

    case "offscreen-stop":
      console.log("[offscreen] Processing WebM stop request");
      stopCapture()
        .then(() => sendResponse({ ok: true }))
        .catch((e) => {
          console.error("[offscreen] WebM stop failed:", e);
          sendResponse({ ok: false, error: String(e) });
        });
      return true;

    case "mic-set-enabled":
      setMicEnabled(!!msg.enabled);
      sendResponse({ ok: true });
      break;

    case "update-speakers":
      console.log("[offscreen] Received speaker states:", msg.speakerStates);
      updateSpeakerStates(msg.speakerStates);
      sendResponse({ ok: true });
      break;

    // Handle messages that should be ignored in offscreen context
    case "start":
    case "stop":
    case "meet-mic-state":
    case "mic-permission":
      console.log("[offscreen] Message handled by background script:", msg.type);
      sendResponse({ ok: true });
      break;

    default:
      console.warn("[offscreen] Unknown message type:", msg?.type);
      sendResponse({ ok: false, error: "Unknown message type" });
  }
  return false;
});