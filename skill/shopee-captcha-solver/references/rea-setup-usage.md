# REA (morluto/rea) — Setup & Usage

Reverse Engineer Anything MCP. Terpasang 2026-10-16.

## Instalasi

```bash
git clone --depth 1 https://github.com/morluto/rea /tmp/rea
cd /tmp/rea && npm install && npm run build
node scripts/rea.mjs setup --client hermes --yes     # → /root/.hermes/config.yaml
```
- Node 22.22.2 OK (butuh ^22.19 || ^24.11 || >=26).
- MCP server terdaftar: `mcp_servers.rea` → `node /tmp/rea/scripts/rea.mjs mcp`.

## Ghidra (opsional — utk native)

```bash
# download release (API GitHub rate-limited → pakai URL langsung)
curl -sL https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_11.4.2_build/ghidra_11.4.2_PUBLIC_20250826.zip -o ghidra.zip
unzip ghidra.zip -d /opt/ghidra_dl
export GHIDRA_INSTALL_DIR=/opt/ghidra_dl/ghidra_11.4.2_PUBLIC   # → tambahkan ke ~/.bashrc
```
- Java 17 sudah ada. Ghidra butuh Java 17+.

## Doctor

```bash
GHIDRA_INSTALL_DIR=... node scripts/rea.mjs doctor
export GHIDRA_INSTALL_DIR=... node scripts/rea.mjs doctor --format json
```
- JS analysis TIDAK butuh engine native.
- hopper/ida/jadx opsional (macOS/Windows only utk beberapa).

## JS analysis (paling berguna utk web target)

```bash
node scripts/rea.mjs analyze-javascript-application <dir> --format json > out.json
# atau web bundle (butuh CDP endpoint + targetId):
node scripts/rea.mjs list-browser-targets <cdp-endpoint>
node scripts/rea.mjs analyze-web-bundle <cdp-endpoint> <targetId> --fetch-source-maps
```
- Output: semantic_graph {nodes, relations, fingerprints} — fungsi, call-site, binding.
- 41201 node / 64263 relatation utk 50 file. Berguna utk peta fungsi.
- `decompile`/`function` = NATIVE saja; JS pakai semantic graph.

## Keterbatasan di JS

- Graph tidak menyertakan string literal → utk string pakai decoder sendiri (`ak_decode.py`).
- Provider native macOS tidak jalan di Linux (wajar).
