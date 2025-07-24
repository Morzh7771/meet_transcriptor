
const express = require("express");
const { main } = require("./meet_record.js");
const { first_login, submit2FACode } = require("./first_login");

const app = express();
const PORT = 3003;

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

app.post("/start", (req, res) => {
  const { email, password, meetCode, duration, port } = req.body;

  if (!email || !password || !meetCode) {
    return res.status(400).json({ error: "Missing required parameters." });
  }

  void (async () => {
    try {
      console.log(`🎥 Starting recording for ${email} | Code: ${meetCode}`);
      await main(email, password, meetCode, duration || 10, port);
      console.log(`✅ Recording for ${email} finished.`);
    } catch (err) {
      console.error("❌ Error inside async main():", err);
    }
  })();

  res.status(200).json({ status: "Recording started in background." });
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
