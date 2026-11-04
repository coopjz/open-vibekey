# VibeKey Studio investigation handoff

Recovered 2026-11-04 from session `01a19b00-530d-79b1-97ec-6e7fe3439d70`.
Last substantive instruction: use REA to obtain VibeKey assets and features from
`/home/cooper/Downloads/Win_Ulanzi_Studio_V3.4.8.20261027.exe` for the Linux project.
The later model-test animation sessions are unrelated.

## Verified progress

- Source SHA-256: `72cc5c89f85941522a906dfd2bc77fd32e0416aa261fc96177ea3a6be7e4caa9`.
- REA CLI 6.7.0 inspected PE resources. Evidence:
  `ev_f12cc76b4bbbd96dc78d905e6ac46306bdcca2557821a0ace8de20a3d5de1e8e`.
  Full record: `studio-pe-resources.json`.
- Both p7zip 16.02 and 7-Zip 23.01 rejected explicit NSIS inspection.
- Shell/Python extraction succeeded with 8-byte block lengths at offset
  `0x23024`, high-bit compression marker and raw LZMA1 properties.
  This is shell evidence, not REA evidence. Extracted 744 blocks totaling
  635,098,132 bytes to `/tmp/vibekey-update-20261104/`.
- Every block's source offset, size and digest is in `studio-block-manifest.json`.
  `scripts/extract-studio-blocks.py` reproduces this exact local extraction.
  Blocks retain numeric names; installer filename mapping has not been recovered.
- Block 000 is the decompressed installer header (304118 bytes).
  Block 370 is a Windows x64 GUI executable, 372 an x64 DLL, 373 an x86 DLL.
- Blocks 053/090/147/177/274 parse as JSON action manifests for Pages,
  Soundboard, Ulanzi Connect, OBS Studio and TC002. Their `Devices` arrays
  contain `~AU05`; the meaning of `~` is unverified and may denote exclusion.
  These strings do NOT establish AU05 support.

## Remaining work

1. Recover filename/path mapping from the installer header; identify AU05
   resources and its actual control implementation, including embedded resources.
2. Trace the device selector semantics before choosing candidate features.
3. Analyze selected executable/DLL functions with REA and installed Ghidra.
4. Integrate features justified by evidence, document asset provenance and
   redistribution terms, and validate Linux behavior.

Current session has no REA MCP tools. CLI works; doctor reports missing Codex
registration. No configuration changes were made. Ghidra previously installed
under `~/.local/opt/rea/` needs explicit environment paths for CLI use.
No vendor executable was run, hardware command sent, feature added, or push made.

## Update after integration

See `studio-integration.md` for the current result. All 743 payload filenames
are mapped, 92 Qt resources recovered, and the AU05 illustration plus a Linux
website action integrated. REA CLI/Ghidra successfully inspected the x64 DLL.
Earlier “Remaining work” entries describe the starting state; device filters,
hardware writes and firmware update behavior remain unverified.
