/**
 * Velopack packaging script for AutoRename-PDF.
 *
 * Creates portable ZIP and installer from a staging directory.
 * Follows the same pattern as PhraseVault/PraxChat/BackupOnShutdown
 * in the electron-workspace.
 *
 * Usage:
 *   node velopack.cjs                     Pack and sign
 *   node velopack.cjs --nosign            Pack without signing
 */

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const noSign =
    process.env.npm_config_nosign === "true" ||
    process.argv.includes("--nosign");

// Read version from gui/package.json (single source of truth)
const guiPkg = JSON.parse(
    fs.readFileSync(path.join(__dirname, "gui", "package.json"), "utf-8")
);
const version = guiPkg.version.replace(/^v/, "");

const PACK_DIR = path.join(__dirname, "dist", "staging");
const ICON = path.join(__dirname, "gui", "src-tauri", "icons", "icon.ico");
const METADATA = path.join(__dirname, "metadata.json");

const args = [
    "pack",
    "--packId", "AutoRename-PDF",
    "--packVersion", version,
    "--packTitle", "AutoRename-PDF",
    "--packAuthors", "SPQRK Web Solutions",
    "--packDir", PACK_DIR,
    "--mainExe", "autorename-pdf-gui.exe",
    "--icon", ICON,
    "--delta", "None",
    "--outputDir", path.join(__dirname, "Releases"),
];

if (!noSign) {
    args.push("--azureTrustedSignFile", METADATA);
}

console.log(`Velopack: packing v${version}${noSign ? " (unsigned)" : ""}`);
console.log(`  packDir: ${PACK_DIR}`);
console.log(`  vpk ${args.join(" ")}\n`);

const r = spawnSync("vpk", args, { stdio: "inherit" });

if (r.error) {
    console.error("Failed to run vpk:", r.error.message);
    if (r.error.code === "ENOENT") {
        console.error("'vpk' not found. Install: dotnet tool install -g vpk");
    }
    process.exit(1);
}

if (r.status !== 0) {
    console.error(`vpk exited with code ${r.status}`);
    process.exit(r.status ?? 1);
}

// Rename release artifacts with version numbers (matches electron-workspace pattern)
const releasesDir = path.join(__dirname, "Releases");
const renames = [
    { src: "AutoRename-PDF-win-Setup.exe", dest: `AutoRename-PDF-Setup-${version}.exe` },
    { src: "AutoRename-PDF-win-Portable.zip", dest: `AutoRename-PDF-Portable-${version}.zip` },
];

for (const { src, dest } of renames) {
    const srcPath = path.join(releasesDir, src);
    const destPath = path.join(releasesDir, dest);
    if (fs.existsSync(srcPath)) {
        // Remove existing dest if present (re-build same version)
        if (fs.existsSync(destPath)) fs.unlinkSync(destPath);
        fs.copyFileSync(srcPath, destPath);
        console.log(`  ${src} -> ${dest}`);
    }
}

console.log("\nVelopack complete.");
