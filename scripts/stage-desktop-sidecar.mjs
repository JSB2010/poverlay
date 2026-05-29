import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const extension = process.platform === "win32" ? ".exe" : "";
const source = join("apps", "local-worker", "dist", `poverlay-worker${extension}`);

function fallbackTargetTriple() {
  const archMap = {
    arm64: "aarch64",
    x64: "x86_64",
  };
  const osMap = {
    darwin: "apple-darwin",
    linux: "unknown-linux-gnu",
    win32: "pc-windows-msvc",
  };
  const arch = archMap[process.arch];
  const os = osMap[process.platform];
  return arch && os ? `${arch}-${os}` : "";
}

function hostTargetTriple() {
  if (process.env.TARGET_TRIPLE) {
    return process.env.TARGET_TRIPLE.trim();
  }
  try {
    return execFileSync("rustc", ["--print", "host-tuple"], { encoding: "utf8" }).trim();
  } catch {
    return fallbackTargetTriple();
  }
}

const targetTriple = hostTargetTriple();

if (!targetTriple) {
  throw new Error("Unable to determine Rust target triple for sidecar staging.");
}

if (!existsSync(source)) {
  throw new Error(`Missing local worker sidecar at ${source}. Build it with PyInstaller first.`);
}

const destinationDir = join("apps", "desktop", "src-tauri", "binaries");
mkdirSync(destinationDir, { recursive: true });
copyFileSync(source, join(destinationDir, `poverlay-worker-${targetTriple}${extension}`));
