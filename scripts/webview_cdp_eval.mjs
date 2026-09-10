// Click a DOM node in the native Tauri WebView2 via CDP.
// Requires WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222
// Usage: node scripts/webview_cdp_eval.mjs "document.getElementById('btn-browse-files').click()"

const port = process.env.WEBVIEW_CDP_PORT || "9222";
const expr = process.argv.slice(2).join(" ").trim();
if (!expr) {
  console.error("usage: node scripts/webview_cdp_eval.mjs <javascript>");
  process.exit(2);
}

const targets = await fetch(`http://127.0.0.1:${port}/json`).then((r) => r.json());
const page =
  targets.find((t) => (t.type === "page" || t.type === "webview") && /AutoRename/i.test(t.title || "")) ||
  targets.find((t) => t.type === "page" || t.webSocketDebuggerUrl);

if (!page?.webSocketDebuggerUrl) {
  console.error("no WebView2 CDP target on port", port);
  console.error(targets.map((t) => ({ type: t.type, title: t.title })));
  process.exit(1);
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("error", reject);
  ws.addEventListener("open", resolve);
});

const id = 1;
const result = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("CDP timeout")), 8000);
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id !== id) return;
    clearTimeout(timer);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  });
  ws.send(
    JSON.stringify({
      id,
      method: "Runtime.evaluate",
      params: { expression: expr, awaitPromise: true, returnByValue: true },
    }),
  );
});
ws.close();
if (result?.exceptionDetails) {
  console.error(result.exceptionDetails);
  process.exit(1);
}
console.log(JSON.stringify(result?.result ?? result));
