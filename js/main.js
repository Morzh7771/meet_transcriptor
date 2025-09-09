const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { submit2FACode } = require('./src/auth/googleAuth');
const sessionManager = require('./src/session/sessionManager');

const app = express();
const PORT = process.env.PORT || 3003;

app.use(express.json());

// 2FA код отправка
app.post("/submit-2fa", (req, res) => {
  const { code } = req.body;

  if (!code) {
    return res.status(400).json({ error: "Missing 2FA code" });
  }

  void (async () => {
    try {
      await submit2FACode(code);
    } catch (err) {
      console.error("2FA submit error:", err);
    }
  })();

  res.status(200).json({ status: "2FA code submitted." });
});

// Запуск новой сессии
app.post("/start", async (req, res) => {
  const { email, password, meetCode, port, chatPort } = req.body;

  if (!email || !password || !meetCode || !port) {
    return res.status(400).json({ error: "Missing required parameters." });
  }

  const sessionId = uuidv4();
  console.log("SessionId is: ", sessionId);

  try {
    const result = await sessionManager.startSession(email, password, sessionId, meetCode, port, chatPort);
    res.status(200).json({ ...result, sessionId });
  } catch (err) {
    console.error("Failed to start session:", err);
    res.status(500).json({ error: "Internal server error." });
  }
});

// Завершение сессии
app.post("/terminate", async (req, res) => {
  const { sessionId } = req.body;
  const result = await sessionManager.terminate(sessionId);
  res.json(result);
});

// Список активных сессий
app.get("/list", (req, res) => {
  res.json(sessionManager.listSessions());
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

setInterval(() => {
  process.stdout.write('.');
  require('fs').writeFileSync('/temp/node-alive', Date.now().toString());
}, 5000);