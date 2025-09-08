const { chromium } = require("@playwright/test");
const { v4: uuidv4 } = require("uuid");
const axios = require("axios");

class BrowserManager {
  constructor() {
    this.browsers = new Map(); // Map of uniqueId -> {browser, port, debuggerUrl}
    this.basePort = 9222;
    this.usedPorts = new Set();
  }

  getNextAvailablePort() {
    let port = this.basePort;
    while (this.usedPorts.has(port)) {
      port++;
    }
    this.usedPorts.add(port);
    return port;
  }

  async createBrowserInstance() {
    const uniqueId = uuidv4();
    const port = this.getNextAvailablePort();

    try {
      const browser = await chromium.launch({
        headless: false,
        args: [
          `--remote-debugging-port=${port}`,
          "--remote-debugging-address=0.0.0.0",
          "--disable-web-security",
          "--no-sandbox",
          "--disable-host-rules",
          "--disable-host-blocking",
          '--host-resolver-rules="MAP * 0.0.0.0"',
          "--window-position=0,0",
          "--window-size=1920,1920",
          "--no-startup-window",
          "--start-minimized",
        ],
      });

      // Get debugger URL
      const response = await axios.get(`http://localhost:${port}/json/version`);
      const debuggerUrl = response.data.webSocketDebuggerUrl;

      this.browsers.set(uniqueId, {
        port,
        debuggerUrl,
        browser,
      });

      return {
        uniqueId,
        port,
        debuggerUrl,
        status: "active",
      };
    } catch (error) {
      this.usedPorts.delete(port);
      throw error;
    }
  }

  async stopBrowserInstance(uniqueId) {
    const instance = this.browsers.get(uniqueId);
    if (!instance) {
      return { status: "inactive", message: "Browser instance not found" };
    }

    try {
      this.usedPorts.delete(instance.port);
      this.browsers.delete(uniqueId);
      await instance.browser.close();
      return {
        status: "inactive",
        message: "Browser instance stopped successfully",
      };
    } catch (error) {
      console.log("error in stopBrowserInstance", error);
      this.usedPorts.delete(instance.port);
      this.browsers.delete(uniqueId);
      return {
        status: "inactive",
        message: "Browser instance is not responding",
      };
    }
  }

  async getBrowserInstance(uniqueId) {
    const instance = this.browsers.get(uniqueId);
    if (!instance) {
      return { status: "inactive", message: "Browser instance not found" };
    }

    try {
      // Verify the browser is still running by checking the debugger endpoint
      const response = await axios.get(
        `http://localhost:${instance.port}/json/version`
      );

      if (response.status !== 200) {
        this.usedPorts.delete(instance.port);
        this.browsers.delete(uniqueId);
        return {
          status: "inactive",
          message: "Browser instance is not responding",
        };
      }
      return {
        uniqueId,
        port: instance.port,
        debuggerUrl: instance.debuggerUrl,
        status: "active",
      };
    } catch (error) {
      // If we can't reach the debugger, the browser is likely down
      this.usedPorts.delete(instance.port);
      this.browsers.delete(uniqueId);
      return {
        status: "inactive",
        message: "Browser instance is not responding",
      };
    }
  }
}

module.exports = new BrowserManager();
