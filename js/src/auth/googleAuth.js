const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch } = require("puppeteer-stream");
const { executablePath } = require("puppeteer");
const { logStep, sleep } = require('../utils/helpers');

puppeteer.use(StealthPlugin());

let browser, page;
let stepCounter = 1;

/**
 * Starts Google authentication process
 */
async function startLogin(email, password, phone) {
  const fs = require('fs');
  if (!fs.existsSync("js/screenshots/login"))
    fs.mkdirSync("js/screenshots/login", { recursive: true });

  browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ["--mute-audio"],
    args: [
      "--disable-notifications",
      "--window-size=1280,1200",
      "--autoplay-policy=no-user-gesture-required",
      "--no-sandbox",
    ],
    closeDelay: 2000,
  });

  page = await browser.newPage();
  await page.goto("https://accounts.google.com/", {
    waitUntil: "networkidle2",
  });
  
  await browser
    .defaultBrowserContext()
    .overridePermissions("https://meet.google.com/", [
      "microphone",
      "camera",
      "notifications",
    ]);
    
  await logStep(page, "Login page is open", stepCounter++, "login");

  // Email input
  await page.waitForSelector('input[type="email"]');
  await page.click('input[type="email"]');
  await page.keyboard.type(email, { delay: 150 });
  await sleep(500);
  await logStep(page, "Email entered", stepCounter++, "login");
  await page.click("#identifierNext");

  // Password input
  await page.waitForSelector('input[type="password"]', { visible: true });
  await sleep(700);
  await page.keyboard.type(password, { delay: 120 });
  await sleep(500);
  await logStep(page, "Password entered", stepCounter++, "login");
  await page.click("#passwordNext");

  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(2000);

  // Phone number if required
  if (phone) {
    await page.keyboard.type(phone, { delay: 120 });
    await page.keyboard.press("Enter");
    await sleep(4000);
  }

  await logStep(page, "Waiting for 2FA code", stepCounter++, "login");
}

/**
 * Submits 2FA code to complete authentication
 */
async function submit2FACode(code) {
  if (!page) throw new Error("Login session not started");

  await page.keyboard.type(code, { delay: 120 });
  await page.keyboard.press("Enter");
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await logStep(page, "2FA code submitted and login complete", stepCounter++, "login");

  return true;
}

module.exports = { 
  startLogin, 
  submit2FACode 
};