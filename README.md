# TV-x86_64

Automated **x86_64 ABI** build of [FongMi/TV](https://github.com/FongMi/TV) (`fongmi` branch) via GitHub Actions.

## What this produces

| Property | Value |
| --- | --- |
| ABI | `x86_64` (native, no ARM translation) |
| Player | ExoPlayer (upstream default) |
| Media3 | Custom [FongMi/media](https://github.com/FongMi/media) fork, **built from source** via Gradle composite build |
| Signature | Android debug key (sideload only) |
| Runtime modules | Python / Node.js / QuickJS / Thunder / mpv-native **not bundled** |

APKs are published to Releases on every successful build, and are also attached to the workflow run as artifacts.

> For a pure x86_64 environment **without** an ARM translation bridge, the upstream `arm64-v8a` APK cannot be installed — which is why a native x86_64 build is required.

## How it works

The workflow (`.github/workflows/build.yml`) only **orchestrates**. Every source modification lives in standalone files under `scripts/`:

1. Clone `FongMi/TV@fongmi` and `FongMi/media@release-1.11.0-fongmi`.
2. Run `scripts/patch.py`, which:
   - wires the custom Media3 fork in with `includeBuild` + `dependencySubstitution` (so **all** custom Media3 APIs — mpvplayer, ui-danmaku, Exo extensions — resolve from source and the app Java needs no rewriting);
   - switches ABI splits to `x86_64` and disables the private-AAR ELF verification;
   - removes the private runtime modules and debug-signs the build.
3. Gradle builds `:app:assembleLeanbackDebug` and `:app:assembleMobileDebug`.
4. APKs are uploaded as artifacts and attached to a Release.

`scripts/media3_settings.gradle.kts` and `media3-stubs/` support the composite build by limiting Media3 to the required modules.

## Why build Media3 from source

FongMi/TV does not declare its Media3 dependencies in `build.gradle`; it relies on a gitignored local `test.gradle` and private `lib-*.aar` files. Public prebuilt AARs (JitPack) are too old and lack the custom classes the current source imports. Building the matching fork from source avoids all of that — and, because it never runs the `publish` task, also sidesteps a POM-generation whitelist bug in the fork's build logic. No patch to FongMi/media itself is needed.

## Auto-follow upstream

The workflow runs daily and on manual dispatch, always cloning the current upstream `fongmi` HEAD.
