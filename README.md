# TV x86_64

Native **x86_64** build of [FongMi/TV](https://github.com/FongMi/TV) via GitHub Actions.

## What this builds

- **ABI:** x86_64 only (native, no ARM translation)
- **Player:** ExoPlayer (upstream default)
- **Media3:** FongMi's custom fork [`release-1.11.0-fongmi`](https://github.com/FongMi/media/tree/release-1.11.0-fongmi), compiled from source and wired in through a Gradle composite build (`includeBuild` + `dependencySubstitution`). This keeps all custom APIs (`mpvplayer`, `ui-danmaku`, Exo extensions).
- **Signature:** Android debug key (sideload only)
- **Not bundled:** private native runtime modules (Python / Node / QuickJS / Thunder / mpv / ffmpeg `.so`)

## Layout

- `.github/workflows/build.yml` — orchestration only (checkout TV + Media3, call the patch script, build, publish). No patch logic is embedded here.
- `scripts/patch.py` — all source-tree modifications (ABI, dependencies, signing, composite-build wiring).
- `scripts/media3_settings.gradle.kts` — composite-build settings installed into the Media3 checkout.
- `scripts/compat-init.gradle` — Gradle init script (AGP 9 / embedded-Kotlin compatibility).
- `media3-stubs/` — empty stub modules for transitively-referenced Media3 test modules.

## Automation

- Runs on push to `master` (when build scripts change), daily at 03:17 UTC, and on manual dispatch.
- APKs are uploaded as workflow artifacts and published under a `build-<run id>` tag.
