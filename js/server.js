// server.js

const express = require("express");
const { main } = require("./meet_record.js");
const { first_login,submit2FACode } = require("./first_login");

const app = express();
const PORT = 3003;

app.use(express.json());

app.post("/login", async (req, res) => {
    const { email, password, phone } = req.body;
  
    if (!email || !password || !phone) {
      return res.status(400).json({ error: "Missing email, password, or phone" });
    }
  
    try {
      console.log(`👤 Launching login for ${email}. Waiting for 2FA code in terminal...`);
  
      await first_login(email, password, phone);
  
      res.status(200).json({ status: "Login complete" });
    } catch (error) {
      console.error("❌ Error during login:", error);
      res.status(500).json({ error: "Login failed" });
    }
  });
app.post("/submit-2fa", async (req, res) => {
  const { code } = req.body;

  if (!code) {
    return res.status(400).json({ error: "Missing 2FA code" });
  }

  try {
    await submit2FACode(code);
    res.status(200).json({ status: "2FA code submitted, login complete" });
  } catch (error) {
    console.error("❌ Error during 2FA submission:", error);
    res.status(500).json({ error: "Failed to submit 2FA code" });
  }
});
app.post("/start", async (req, res) => {
  const { email, password, meetCode, duration, port} = req.body;

  if (!email || !password || !meetCode) {
    return res.status(400).json({ error: "Missing required parameters." });
  }

  try {
    main(email, password, meetCode, duration || 10, port); // launch without waiting for completion
        res.status(200).json({ status: "Recording started." });
  } catch (error) {
    console.error("Error at start main:", error);
        res.status(500).json({ error: "Failed to start recording." });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Server is running on http://localhost:${PORT}`);
});
