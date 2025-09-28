const msg = document.getElementById('msg');

async function requestMic() {
  msg.textContent = "Requesting microphone...";
  try {
    const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    s.getTracks().forEach(t => t.stop());
    msg.textContent = "Microphone granted.";
    msg.className = "ok";
    try { await chrome.runtime.sendMessage({ type: "mic-permission", ok: true }); } catch {}
    setTimeout(() => window.close(), 300);
  } catch (e) {
    console.error("Mic permission error:", e);
    msg.textContent = "Permission denied or not available.";
    msg.className = "err";
    try { await chrome.runtime.sendMessage({ type: "mic-permission", ok: false, error: String(e) }); } catch {}
  }
}

//automatic asking for micro permission
requestMic().catch(() => {});