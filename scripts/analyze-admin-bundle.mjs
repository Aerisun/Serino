import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const distDir = path.join(repoRoot, "admin", "dist");
const assetsDir = path.join(distDir, "assets");
const indexHtmlPath = path.join(distDir, "index.html");

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  return `${(bytes / 1024).toFixed(2)} kB`;
}

function loadAssets() {
  if (!fs.existsSync(assetsDir)) {
    throw new Error(
      `Missing admin build output at ${assetsDir}. Run "corepack pnpm -C admin build" first.`,
    );
  }

  return fs
    .readdirSync(assetsDir)
    .filter((name) => /\.(js|css)$/.test(name))
    .map((name) => {
      const filePath = path.join(assetsDir, name);
      const buffer = fs.readFileSync(filePath);
      const ext = path.extname(name).slice(1);
      return {
        name,
        ext,
        rawBytes: buffer.byteLength,
        gzipBytes: zlib.gzipSync(buffer).byteLength,
      };
    })
    .sort((left, right) => right.rawBytes - left.rawBytes);
}

function loadEntryAssets() {
  if (!fs.existsSync(indexHtmlPath)) {
    return [];
  }

  const html = fs.readFileSync(indexHtmlPath, "utf8");
  const matches = html.match(/assets\/[^"' )]+/g) ?? [];
  return [...new Set(matches.map((value) => value.replace(/^assets\//, "")))];
}

function printSection(title, rows) {
  console.log(`\n${title}`);
  if (rows.length === 0) {
    console.log("  (none)");
    return;
  }

  for (const row of rows) {
    console.log(
      `  ${row.name.padEnd(44)} ${formatBytes(row.rawBytes).padStart(10)} raw  ${formatBytes(row.gzipBytes).padStart(10)} gzip`,
    );
  }
}

function sumBytes(rows, key) {
  return rows.reduce((total, row) => total + row[key], 0);
}

const assets = loadAssets();
const entryAssetNames = new Set(loadEntryAssets());
const entryAssets = assets.filter((asset) => entryAssetNames.has(asset.name));
const jsAssets = assets.filter((asset) => asset.ext === "js");
const cssAssets = assets.filter((asset) => asset.ext === "css");
const hotspotAssets = assets.filter((asset) => asset.rawBytes >= 40 * 1024);

console.log("Admin bundle analysis");
console.log(`Dist directory: ${distDir}`);
console.log(`Asset files: ${assets.length}`);

printSection("Entry assets from dist/index.html", entryAssets);
printSection("Top 10 JS assets", jsAssets.slice(0, 10));
printSection("Top 5 CSS assets", cssAssets.slice(0, 5));
printSection("Hotspots (>= 40 kB raw)", hotspotAssets);

console.log("\nTotals");
console.log(
  `  JS   ${formatBytes(sumBytes(jsAssets, "rawBytes")).padStart(10)} raw  ${formatBytes(sumBytes(jsAssets, "gzipBytes")).padStart(10)} gzip`,
);
console.log(
  `  CSS  ${formatBytes(sumBytes(cssAssets, "rawBytes")).padStart(10)} raw  ${formatBytes(sumBytes(cssAssets, "gzipBytes")).padStart(10)} gzip`,
);
