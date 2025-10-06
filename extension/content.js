(() => {
  if (window.top !== window.self) return;

  const meetCodeRegex = /^\/([a-z]{3}-[a-z]{4}-[a-z]{3})$/i;
  if (!meetCodeRegex.test(window.location.pathname)) return;

  const meetCodeMatch = window.location.pathname.match(meetCodeRegex);
  const MEET_CODE = meetCodeMatch ? meetCodeMatch[1] : null;
  
  console.log("[content] URL pathname:", window.location.pathname);
  console.log("[content] Meet code match:", meetCodeMatch);
  console.log("[content] Extracted MEET_CODE:", MEET_CODE);
  
  if (!MEET_CODE) {
    console.error("Could not extract meet code from URL");
    return;
  }
  
  const ROOM = MEET_CODE;
  console.log("[content] Using ROOM:", ROOM);

  let panel, startStopBtn, statusEl, transcriptEl;
  let isRecording = false;
  let speakerMonitorInterval = null;
  let inMeeting = false;
  let lastMuted = null;

  let currentSpeakerStates = {};

  const addTranscript = (text) => {
    if (transcriptEl && text) {
      const currentContent = transcriptEl.value || "";
      transcriptEl.value = currentContent ? `${text}\n\n${currentContent}` : text;
    }
  };

  const addViolation = (violationMessage) => {
    if (!transcriptEl) {
      console.warn("[content] transcriptEl not available");
      return;
    }
    
    console.log("[content] Adding violation to transcript:", violationMessage);
    
    const timestamp = new Date().toLocaleTimeString();
    const formattedViolation = `VIOLATION: \n${violationMessage}`;
    
    const currentContent = transcriptEl.value || "";
    transcriptEl.value = currentContent ? `${formattedViolation}\n\n${currentContent}` : formattedViolation;
    
    console.log("[content] Transcript updated, new length:", transcriptEl.value.length);
  };

  // UPDATED: New selector for audio indicator circles
  const scanAndUpdateSpeakers = () => {
    // Find all audio indicator elements by their specific classes
    // The audio circles have jscontroller="YQvg8b" and classes starting with "DYfzY"
    const audioIndicators = document.querySelectorAll('[jscontroller="YQvg8b"].DYfzY');
    const newSpeakerStates = {};
    
    console.log("[content] Found audio indicators:", audioIndicators.length);
    
    // Go through all audio indicators
    Array.from(audioIndicators).forEach((indicator) => {
      const participantName = findParticipantName(indicator);
      const isSpeakingNow = isSpeaking(indicator);
      
      // Store current state
      newSpeakerStates[participantName] = isSpeakingNow;
    });

    // Check if anything changed
    const statesChanged = !areStatesEqual(currentSpeakerStates, newSpeakerStates);
    
    if (statesChanged) {
      logSpeakerChanges(currentSpeakerStates, newSpeakerStates);
      currentSpeakerStates = { ...newSpeakerStates };
      
      if (isRecording) {
        sendSpeakerStates();
      }
    }
  };

  const areStatesEqual = (oldStates, newStates) => {
    const oldKeys = Object.keys(oldStates);
    const newKeys = Object.keys(newStates);
    
    if (oldKeys.length !== newKeys.length) return false;
    
    for (const participant of newKeys) {
      if (oldStates[participant] !== newStates[participant]) {
        return false;
      }
    }
    return true;
  };

  const logSpeakerChanges = (oldStates, newStates) => {
    const time = new Date().toLocaleTimeString();
    
    for (const [participant, isNowSpeaking] of Object.entries(newStates)) {
      const wasSpeaking = oldStates[participant] || false;
      
      if (wasSpeaking !== isNowSpeaking) {
        if (isNowSpeaking) {
          console.log(`[${time}] 🎤 ${participant} started speaking`);
        } else {
          console.log(`[${time}] 🔇 ${participant} stopped speaking`);
        }
      }
    }
    
    const currentSpeakers = Object.entries(newStates)
      .filter(([name, speaking]) => speaking)
      .map(([name]) => name);
      
    if (currentSpeakers.length > 0) {
      console.log(`[${time}] Currently speaking: ${currentSpeakers.join(", ")}`);
    }
  };

  const sendSpeakerStates = () => {
    console.log("[content] Sending speaker states:", currentSpeakerStates);
    
    sendExtMessage({ 
      type: "update-speakers", 
      speakerStates: currentSpeakerStates,
      time: Date.now()
    });
  };

  const reportMicState = (muted) => {
    if (!inMeeting || typeof muted !== "boolean" || muted === lastMuted) return;
    console.log(`[content] Mic state: ${muted ? "MUTED" : "UNMUTED"}`);
    lastMuted = muted;
    sendExtMessage({ type: "meet-mic-state", muted });
  };

  const setStatus = (text) => (statusEl && (statusEl.textContent = text));
  const setRecording = (rec) => {
    isRecording = !!rec;
    if (startStopBtn) startStopBtn.textContent = rec ? "Stop" : "Start";
    setStatus(rec ? "PCM Streaming..." : "Idle");

    if (clientIdInput) clientIdInput.disabled = rec;
    if (consultantIdInput) consultantIdInput.disabled = rec;
  };

  const createPanel = () => {
    if (panel) return;
    panel = el("div", {}, {
      position: "fixed",
      bottom: "85px",
      left: "16px",
      zIndex: 999999,
      background: "rgba(28,28,28,0.95)",
      color: "#fff",
      padding: "12px",
      borderRadius: "12px",
      width: "420px",
      boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
      fontFamily: "system-ui,Arial,sans-serif",
    });

    const title = el("div", { textContent: "Qontext Audio Transcriptor (PCM Stream)" }, { fontWeight: "600", marginBottom: "6px" });
    
    const inputsContainer = el("div", {}, { marginTop: "8px", marginBottom: "8px" });
    
    const clientIdLabel = el("label", { textContent: "Client ID:" }, { 
      display: "block", 
      fontSize: "12px", 
      marginBottom: "4px",
      color: "#ccc"
    });
    clientIdInput = el("input", { 
      type: "text",
      placeholder: "Enter Client ID",
      value: localStorage.getItem("qontext_client_id") || ""
    }, {
      width: "100%",
      padding: "8px",
      marginBottom: "8px",
      borderRadius: "6px",
      border: "1px solid #444",
      background: "#1a1a1a",
      color: "#fff",
      fontSize: "13px",
      fontFamily: "system-ui,Arial,sans-serif",
    });
    
    const consultantIdLabel = el("label", { textContent: "Consultant ID:" }, { 
      display: "block", 
      fontSize: "12px", 
      marginBottom: "4px",
      color: "#ccc"
    });
    consultantIdInput = el("input", { 
      type: "text",
      placeholder: "Enter Consultant ID",
      value: localStorage.getItem("qontext_consultant_id") || ""
    }, {
      width: "100%",
      padding: "8px",
      marginBottom: "4px",
      borderRadius: "6px",
      border: "1px solid #444",
      background: "#1a1a1a",
      color: "#fff",
      fontSize: "13px",
      fontFamily: "system-ui,Arial,sans-serif",
    });
    
    clientIdInput.addEventListener("input", (e) => {
      localStorage.setItem("qontext_client_id", e.target.value);
    });
    
    consultantIdInput.addEventListener("input", (e) => {
      localStorage.setItem("qontext_consultant_id", e.target.value);
    });
    
    inputsContainer.append(clientIdLabel, clientIdInput, consultantIdLabel, consultantIdInput);
    
    startStopBtn = el("button", { textContent: "Start" }, {
      marginTop: "4px",
      width: "100%",
      padding: "10px",
      borderRadius: "8px",
      border: "1px solid #4a90e2",
      background: "#2d6cdf",
      color: "#fff",
      cursor: "pointer",
    });
    statusEl = el("div", { textContent: "Idle" }, { marginTop: "6px", opacity: "0.85", fontSize: "12px" });
    transcriptEl = el("textarea", { readOnly: true, rows: 10 }, {
      width: "100%",
      marginTop: "8px",
      padding: "8px",
      borderRadius: "8px",
      border: "1px solid #444",
      background: "#111",
      color: "#e6ffe6",
      fontFamily: "monospace",
      resize: "vertical",
    });

    panel.append(title, inputsContainer, startStopBtn, statusEl, transcriptEl);
    document.body.appendChild(panel);
    startStopBtn.onclick = () => (isRecording ? handleStop() : handleStart());
    setRecording(false);
  };

  const destroyPanel = () => {
    if (!panel) return;
    if (isRecording) handleStop().catch(() => {});
    panel.remove();
    panel = startStopBtn = statusEl = transcriptEl = clientIdInput = consultantIdInput = null;
  };

  const handleStart = async () => {
    console.log("[content] Start PCM streaming button clicked");

    const clientId = clientIdInput?.value?.trim();
    const consultantId = consultantIdInput?.value?.trim();
    
    if (!clientId || !consultantId) {
      alert("Please enter both Client ID and Consultant ID before starting");
      setStatus("Error: IDs required");
      return;
    }

    startStopBtn.disabled = true;
    setStatus("Starting PCM session...");

    const startMessage = {
      type: "start",
      opts: { 
        apiBase: API_BASE, 
        room: ROOM,
        clientId: clientId,
        consultantId: consultantId
      },
    };

    const ack = await sendExtMessage(startMessage);
    console.log("[content] Received PCM start response:", ack);

    setRecording(true);

    const micBtn = findMicButton();
    const currentMuted = getMicMuted(micBtn);
    if (currentMuted !== null) {
      sendExtMessage({ type: "meet-mic-state", muted: currentMuted });
    }

    scanAndUpdateSpeakers();
    speakerMonitorInterval = setInterval(scanAndUpdateSpeakers, 100);
    startStopBtn.disabled = false;
  };

  const handleStop = async () => {
    startStopBtn.disabled = true;
    setStatus("Stopping PCM streaming...");
    
    if (speakerMonitorInterval) {
      clearInterval(speakerMonitorInterval);
      speakerMonitorInterval = null;
    }
     
    await sendExtMessage({ type: "stop" });
    setRecording(false);
    startStopBtn.disabled = false;
  };

  const isInMeeting = () => !!document.querySelector('[jsname="BOHaEe"], [data-participant-id]');
  const checkMeetingState = () => {
    const current = isInMeeting();
    if (current === inMeeting) return;
    inMeeting = current;
    if (inMeeting) {
      console.log("[content] Entered meeting, creating panel");
      createPanel();
      const micBtn = findMicButton();
      const currentMuted = getMicMuted(micBtn);
      reportMicState(currentMuted);
    } else {
      console.log("[content] Left meeting, destroying panel");
      destroyPanel();
      currentSpeakerStates = {};
    }
  };

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    console.log("[content] Received message type:", msg?.type, "Full message:", msg);
    
    if (msg?.type === "chunk-transcript" && msg.data?.processed_text) {
      const textToShow = msg.data.processed_text.trim();
      console.log("[content] Processing transcript:", textToShow);
      if (textToShow && !transcriptEl?.value?.includes(textToShow)) {
        addTranscript(textToShow);
      }
    }
    
    if (msg?.type === "violation-message") {
      console.log("[content] Processing violation message:", msg.message);
      if (msg.message) {
        addViolation(msg.message);
      } else {
        console.warn("[content] Violation message is empty");
      }
    }
    
    sendResponse({ ok: true });
    return true;
  });

  setTimeout(checkMeetingState, 1000);
  setInterval(() => {
    checkMeetingState();
    if (inMeeting) {
      const micBtn = findMicButton();
      const currentMuted = getMicMuted(micBtn);
      reportMicState(currentMuted);
    }
  }, 2000);
  
  new MutationObserver(checkMeetingState).observe(document.body, { childList: true, subtree: true });
})();