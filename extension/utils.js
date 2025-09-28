
const API_BASE = "http://127.0.0.1:8000";

function el(tag, attrs = {}, style = {}) {
  const n = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "textContent") n.textContent = v;
    else if (k === "html") n.innerHTML = v;
    else n.setAttribute(k, v);
  });
  Object.assign(n.style, style || {});
  return n;
}

async function postJSON(url, body) {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) return null;
    try { return await res.json(); } catch { return {}; }
  } catch {
    return null;
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function sendExtMessage(msg) {
  try {
    return await chrome?.runtime?.sendMessage(msg);
  } catch {
    return null;
  }
}

function getRoomIdFromUrl(pathname = (typeof window !== "undefined" ? window.location.pathname : "")) {
  const match = pathname.match(/^\/([a-z]{3}-[a-z]{4}-[a-z]{3})$/i);
  return match ? match[1] : null;
}

// Choose a supported audio MIME type for MediaRecorder.
function getMimeType() {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  return types.find((t) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t));
}

// Expose to global scope for content/offscreen scripts.
window.API_BASE = API_BASE;
window.el = el;
window.postJSON = postJSON;
window.sleep = sleep;
window.sendExtMessage = sendExtMessage;
window.getRoomIdFromUrl = getRoomIdFromUrl;
window.getMimeType = getMimeType;
