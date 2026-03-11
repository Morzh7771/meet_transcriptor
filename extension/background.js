let offscreenCreated = false;
let isRecording = false;
let recordingTabId = null; // tab that started the recording

async function ensureOffscreen() {
  if (offscreenCreated) return;
  const has = await chrome.offscreen.hasDocument?.();
  if (!has) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["BLOBS"],
      justification: "WebM audio capture & WebSocket streaming"
    });
  }
  offscreenCreated = true;
}

async function offscreenSend(msg) {
  await ensureOffscreen();
  return await chrome.runtime.sendMessage(msg);
}

async function ensureMicPermissionFixed() {
  const w = await chrome.windows.create({
    url: "mic_permission.html",
    type: "popup",
    width: 360,
    height: 180
  });

  const ok = await new Promise((resolve) => {
    let resolved = false;
    const listener = (msg) => {
      if (msg?.type === "mic-permission") {
        if (!resolved) {
          resolved = true;
          resolve(!!msg.ok);
          chrome.runtime.onMessage.removeListener(listener);
          if (w && w.id) chrome.windows.remove(w.id);
        }
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve(false);
        chrome.runtime.onMessage.removeListener(listener);
        if (w && w.id) chrome.windows.remove(w.id);
      }
    }, 15000);
  });
  return ok;
}

async function broadcast(payload) {
  try {
    const tabs = await chrome.tabs.query({ url: ["https://meet.google.com/*"] });
    console.log("[background] Broadcasting to", tabs.length, "Meet tabs:", payload.type);
    tabs.forEach(t => {
      chrome.tabs.sendMessage(t.id, payload)
        .then(() => console.log("[background] Sent to tab", t.id))
        .catch((e) => console.log("[background] Failed to send to tab", t.id, e.message));
    });
  } catch (e) {
    console.error("[background] Broadcast error:", e);
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("[background] Received message:", msg?.type, "from:", sender.tab ? "tab" : "extension");
  
  (async () => {
    try {
      switch (msg?.type) {
        case "status":
          sendResponse({ isRecording });
          break;

        case "start":
          await ensureMicPermissionFixed();
          {
            const opts = msg.opts || {};
            const startResp = await offscreenSend({
              type: "offscreen-start",
              opts: { apiBase: opts.apiBase, room: opts.room, slackDmEmail: opts.slackDmEmail || "" }
            });
            isRecording = !!(startResp?.ok);
            recordingTabId = isRecording ? (sender.tab?.id ?? null) : null;
            sendResponse({ ok: isRecording });
          }
          break;

        case "stop":
          {
            const stopResp = await offscreenSend({ type: "offscreen-stop" });
            isRecording = false;
            recordingTabId = null;
            sendResponse({ ok: !!(stopResp?.ok) });
          }
          break;

        case "chunk-transcript":
          console.log("[background] Broadcasting transcript to Meet tabs");
          await broadcast({ type: "chunk-transcript", data: msg.data });
          sendResponse({ ok: true });
          break;

        case "violation-alert":
          console.log("[background] Received violation alert, broadcasting to Meet tabs");
          console.log("[background] Violation message:", msg.message);
          await broadcast({ 
            type: "violation-message", 
            message: msg.message,
            timestamp: msg.timestamp 
          });
          sendResponse({ ok: true });
          break;

        case "meet-mic-state":
          await offscreenSend({ type: "mic-set-enabled", enabled: !msg.muted });
          sendResponse({ ok: true });
          break;

        case "update-speakers":
          // ВАЖНО: проксируем правильное поле speakerStates (а не speakers)
          await offscreenSend({ type: "update-speakers", speakerStates: msg.speakerStates });
          sendResponse({ ok: true });
          break;

        default:
          sendResponse({ ok: false });
      }
    } catch (e) {
      console.error("[background] error:", e);
      sendResponse({ ok: false, error: String(e) });
    }
  })();
  return true;
});

async function triggerStopIfRecording(reason) {
  if (!isRecording) return;
  console.log(`[background] Auto-stop triggered: ${reason}`);
  try {
    await offscreenSend({ type: "offscreen-stop" });
  } catch (e) {
    console.warn("[background] Auto-stop failed:", e);
  }
  isRecording = false;
  recordingTabId = null;
}

// Tab closed → stop recording
chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === recordingTabId) {
    triggerStopIfRecording("Meet tab closed");
  }
});

// Tab navigated away from meet.google.com → stop recording
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (tabId !== recordingTabId) return;
  if (changeInfo.url && !changeInfo.url.includes("meet.google.com")) {
    triggerStopIfRecording("navigated away from Meet");
  }
});

self.addEventListener("onSuspend", async () => {
  try {
    if (await chrome.offscreen.hasDocument?.()) {
      await chrome.offscreen.closeDocument();
    }
    offscreenCreated = false;
  } catch {}
});