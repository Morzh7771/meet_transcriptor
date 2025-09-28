let offscreenCreated = false;
let isRecording = false;

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
    tabs.forEach(t => chrome.tabs.sendMessage(t.id, payload).catch(() => {}));
    chrome.runtime.sendMessage(payload).catch(() => {});
  } catch {}
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg?.type) {
        case "status":
          sendResponse({ isRecording });
          break;

        case "start":
          await ensureMicPermissionFixed();
          {
            const startResp = await offscreenSend({ type: "offscreen-start", opts: msg.opts || {} });
            isRecording = !!(startResp?.ok);
            sendResponse({ ok: isRecording });
          }
          break;

        case "stop":
          {
            const stopResp = await offscreenSend({ type: "offscreen-stop" });
            isRecording = false;
            sendResponse({ ok: !!(stopResp?.ok) });
          }
          break;

        case "chunk-transcript":
          await broadcast({ type: "chunk-transcript", data: msg.data });
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

self.addEventListener("onSuspend", async () => {
  try {
    if (await chrome.offscreen.hasDocument?.()) {
      await chrome.offscreen.closeDocument();
    }
    offscreenCreated = false;
  } catch {}
});
