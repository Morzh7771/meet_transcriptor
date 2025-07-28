
const express = require("express");
const { first_login, submit2FACode } = require("./first_login");
const { SessionManager } = require("./sessionManager");
const { v4: uuidv4 } = require("uuid");

const app = express();
const PORT = 3003;
const sessionManager = new SessionManager();

app.use(express.json());

app.post("/login", (req, res) => {
  const { email, password, phone } = req.body;

  if (!email || !password || !phone) {
    return res.status(400).json({ error: "Missing email, password, or phone" });
  }

  void (async () => {
    try {
      console.log(`👤 Launching login for ${email}. Waiting for 2FA code in terminal...`);
      await first_login(email, password, phone);
    } catch (err) {
      console.error("❌ Error inside async first_login():", err);
    }
  })();

  res.status(200).json({ status: "Login started in background. Check terminal for 2FA." });
});

app.post("/submit-2fa", (req, res) => {
  const { code } = req.body;

  if (!code) {
    return res.status(400).json({ error: "Missing 2FA code" });
  }

  void (async () => {
    try {
      await submit2FACode(code);
    } catch (err) {
      console.error("❌ Error inside async submit2FACode():", err);
    }
  })();

  res.status(200).json({ status: "2FA code submitted. Finishing login in background." });
});

app.post("/start", async (req, res) => {
  const { email, password, meetCode, port } = req.body;
  if (!email || !password || !meetCode || !port) {
    return res.status(400).json({ error: "Missing required parameters." });
  }

  const sessionId = uuidv4();
  try {
    const result = await sessionManager.startSession(email, password,sessionId, meetCode, port);
    res.status(200).json({ ...result, sessionId });
  } catch (err) {
    console.error("❌ Failed to start session:", err);
    res.status(500).json({ error: "Failed to start session." });
  }
});


app.post("/terminate", async (req, res) => {
  const { sessionId } = req.body;
  const result = await sessionManager.terminate(sessionId);
  res.json(result);
});

app.get("/list", (req, res) => {
  res.json(sessionManager.listSessions());
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
