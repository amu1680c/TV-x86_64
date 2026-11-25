#!/usr/bin/env python3
"""Patch a checked-out FongMi/TV source tree into an x86_64, source-built-Media3 build.

All repository modifications live in this standalone file. The GitHub Actions
workflow only orchestrates: checkout TV -> clone Media3 -> call this script ->
gradle build -> publish Release. No patch logic is embedded in the workflow.

Usage:
    python3 patch.py <tv-source-root> <media3-source-root>

Design (verified against wobuhui666/TV and yangxiaoge/tvbox_cust, 2026-11):
---------------------------------------------------------------------------
* FongMi/TV does NOT declare Media3 in build.gradle; upstream injects it via a
  gitignored local `test.gradle` from private, prebuilt AARs. Public source
  therefore cannot compile on its own.
* We build the custom Media3 fork from source and wire it in with Gradle
  composite builds (includeBuild + dependencySubstitution). This:
    - keeps ALL custom Media3 APIs (mpvplayer / ui-danmaku / Exo extensions),
      so no app Java files need to be deleted or rewritten;
    - never runs the `publish` task, so the aarTypeWorkaround smbj whitelist
      bug is irrelevant (zero patches to FongMi/media).
* Media3 source used: FongMi/media @ release-1.11.0-fongmi (Media3 1.11.0),
  matching the current TV source baseline.
* ABI is switched to x86_64 everywhere (splits + AbiApkPackaging map), and the
  private-AAR ELF verification is disabled (those AARs are not shipped).
* The six private runtime modules (chaquo/nodejs/quickjs/thunder + mpv/ffmpeg
  AARs) are dropped; the player runs on ExoPlayer, which is the upstream default.
"""
import pathlib
import sys


if len(sys.argv) != 3:
    raise SystemExit("usage: patch.py <tv-source-root> <media3-source-root>")

TV = pathlib.Path(sys.argv[1]).resolve()
M3 = pathlib.Path(sys.argv[2]).resolve()
MEDIA_VERSION = "1.11.0"

# media3 module -> composite-build project path. Keep in sync with
# media3_settings.gradle.kts (requiredModules) and libs.versions.toml bundle.
MODULES = {
    "media3-common": "lib-common",
    "media3-container": "lib-container",
    "media3-database": "lib-database",
    "media3-datasource": "lib-datasource",
    "media3-datasource-okhttp": "lib-datasource-okhttp",
    "media3-datasource-rtmp": "lib-datasource-rtmp",
    "media3-decoder": "lib-decoder",
    "media3-decoder-ffmpeg": "lib-decoder-ffmpeg",
    "media3-exoplayer": "lib-exoplayer",
    "media3-exoplayer-dash": "lib-exoplayer-dash",
    "media3-exoplayer-hls": "lib-exoplayer-hls",
    "media3-exoplayer-rtsp": "lib-exoplayer-rtsp",
    "media3-exoplayer-smoothstreaming": "lib-exoplayer-smoothstreaming",
    "media3-extractor": "lib-extractor",
    "media3-session": "lib-session",
    "media3-ui": "lib-ui",
    "media3-ui-danmaku": "lib-ui-danmaku",
    "media3-mpvplayer": "lib-mpvplayer",
}
BUNDLE_NAMES = [m for m in MODULES if m != "media3-container"]


def tv_read(rel):
    p = TV / rel
    if not p.is_file():
        raise SystemExit(f"[patch] missing TV file: {rel}")
    return p.read_text(encoding="utf-8")


def tv_write(rel, text):
    (TV / rel).write_text(text, encoding="utf-8")
    print(f"[patch] wrote TV/{rel}")


def sub(text, old, new, label, required=True, count=1):
    if old not in text:
        if required:
            raise SystemExit(f"[patch] pattern not found ({label}) -- upstream drifted")
        print(f"[patch] WARN skip ({label})")
        return text
    return text.replace(old, new, count)


# ---------------------------------------------------------------------------
# 1. TV settings.gradle: drop private runtime modules + add composite build
# ---------------------------------------------------------------------------
def patch_settings():
    s = tv_read("settings.gradle")
    for mod in ("chaquo", "nodejs", "quickjs", "thunder"):
        s = sub(s, f"include ':{mod}'\n", "", f"drop :{mod}", required=False)

    substitution = "\n".join(
        f'                substitute module("androidx.media3:{name}") using project(":{proj}")'
        for name, proj in MODULES.items()
    )
    block = f"""
// ---- x86_64 build: in-tree custom Media3 via composite build ----
def media3SourceDir = System.getenv("MEDIA3_SOURCE_DIR")
if (media3SourceDir == null || media3SourceDir.isBlank()) {{
    throw new GradleException("MEDIA3_SOURCE_DIR must point to a FongMi/media checkout")
}}
def media3Dir = file(media3SourceDir)
if (!media3Dir.isDirectory()) throw new GradleException("MEDIA3_SOURCE_DIR does not exist: ${{media3Dir}}")
includeBuild(media3Dir) {{
    dependencySubstitution {{
{substitution}
    }}
}}
"""
    if "MEDIA3_SOURCE_DIR" not in s:
        s = s.rstrip() + "\n" + block
    # flatDir for local AARs is fine to keep; jitpack no longer needed but harmless.
    tv_write("settings.gradle", s)


# ---------------------------------------------------------------------------
# 2. TV gradle/libs.versions.toml: add media3 version + libraries + bundle
# ---------------------------------------------------------------------------
def patch_versions():
    t = tv_read("gradle/libs.versions.toml")
    # AGP alignment: the custom Media3 fork is built with AGP 9.0.1. Gradle
    # forbids two AGP versions in one composite build, so pin TV to 9.0.1 no
    # matter which AGP the pinned TV snapshot declares (9.5.1 on fongmi HEAD,
    # 9.2.1 on the API-matched 2026-07-29 snapshot we now use).
    import re as _re
    t, n = _re.subn(r'agp = "[0-9][^"]*"', 'agp = "9.0.1"', t, count=1)
    if n:
        print("[patch] aligned TV AGP -> 9.0.1 to match Media3 fork")
    if 'media3 = ' not in t:
        t = sub(t, "[versions]\n", f'[versions]\nmedia3 = "{MEDIA_VERSION}"\n', "add media3 version")
    libs_lines = "\n".join(
        f'{name} = {{ group = "androidx.media3", name = "{name}", version.ref = "media3" }}'
        for name in MODULES
    )
    anchor = "[libraries]\n"
    if "media3-common = " not in t:
        t = sub(t, anchor, anchor + libs_lines + "\n", "add media3 libraries")
    bundle = "[bundles]\nmedia3 = [" + ", ".join(f'"{n}"' for n in BUNDLE_NAMES) + "]\n"
    if "[bundles]" in t:
        if "media3 = [" not in t:
            t = sub(t, "[bundles]\n", bundle, "add media3 bundle")
    else:
        t = t.rstrip() + "\n\n" + bundle
    tv_write("gradle/libs.versions.toml", t)


# ---------------------------------------------------------------------------
# 3. TV app/build.gradle: ABI, media3 deps, signing, drop runtime module deps
# ---------------------------------------------------------------------------
def patch_app_build():
    b = tv_read("app/build.gradle")

    # 3a. ABI splits -> x86_64
    b = sub(
        b,
        '            include "arm64-v8a", "armeabi-v7a"',
        '            include "x86_64"',
        "abi split -> x86_64",
    )

    # 3b. signing: use debug keystore, no local.properties needed
    old_sign = """    signingConfigs {
        release {
            storeFile file(localProps['storeFile'])
            keyAlias localProps['keyAlias']
            keyPassword localProps['storePassword']
            storePassword localProps['storePassword']
        }
    }"""
    new_sign = """    signingConfigs {
        release {
            storeFile file("${System.getProperty('user.home')}/.android/debug.keystore")
            keyAlias 'androiddebugkey'
            keyPassword 'android'
            storePassword 'android'
        }
    }"""
    b = sub(b, old_sign, new_sign, "signing -> debug keystore")

    # 3c. local.properties is not present in Actions; make loading optional
    old_props = """def localProps = new Properties()
rootProject.file('local.properties').withInputStream {
    localProps.load(it)
}"""
    new_props = """def localProps = new Properties()
def localPropsFile = rootProject.file('local.properties')
if (localPropsFile.exists()) {
    localPropsFile.withInputStream { localProps.load(it) }
}"""
    b = sub(b, old_props, new_props, "optional local.properties")

    # 3d. inject Media3 dependencies after the catvod project dep.
    # Gradle version-catalog aliases with dashes (media3-common) are accessed as
    # libs.media3.common in Groovy, so we use the bundle alias libs.bundles.media3
    # instead, which expands to the same coordinates.
    dep_anchor = "    implementation project(':catvod')\n"
    m3_deps = "    // Custom Media3 from composite build (dependencySubstitution handles coordinates)\n"
    m3_deps += "    implementation libs.bundles.media3\n"
    if "libs.bundles.media3" not in b:
        b = sub(b, dep_anchor, dep_anchor + m3_deps, "inject media3 deps")

    # 3e. drop any project deps on private runtime modules (defensive)
    for mod in ("chaquo", "nodejs", "quickjs", "thunder"):
        b = sub(b, f"    implementation project(':{mod}')\n", "", f"drop app dep :{mod}", required=False)
    tv_write("app/build.gradle", b)


# ---------------------------------------------------------------------------
# 4. AbiApkPackaging: ABI_FLAVORS -> x86_64, disable private-AAR verification
# ---------------------------------------------------------------------------
def patch_abi_packaging():
    p = TV / "buildSrc/src/main/groovy/com/fongmi/gradle/AbiApkPackaging.groovy"
    g = p.read_text(encoding="utf-8")
    g = sub(
        g,
        "static final Map<String, String> ABI_FLAVORS = [arm64: 'arm64-v8a', arm32: 'armeabi-v7a'].asImmutable()",
        "static final Map<String, String> ABI_FLAVORS = [x64: 'x86_64'].asImmutable()",
        "ABI_FLAVORS -> x86_64",
    )
    # Make native-library verification a no-op: the private AARs are absent.
    old_body = """    private static void configureNativeLibraries(Project project, def variant, List<String> abis) {
        variant.packaging.jniLibs.excludes.addAll((THUNDER_LIBRARIES + MPV_LIBRARIES + [RUNTIME_PROFILES.nodejs.library, RUNTIME_PROFILES.quickjs.library]).collect { "**/${it}".toString() })
        variant.packaging.jniLibs.keepDebugSymbols.add('**/libc++_shared.so')
        def validation = project.tasks.register("verify${variant.name.capitalize()}MpvNative", VerifyMpvNativeTask) { task ->
            task.mpvArchive.set(project.layout.projectDirectory.file('libs/lib-mpvplayer-release.aar'))
            task.ffmpegArchive.set(project.layout.projectDirectory.file('libs/lib-decoder-ffmpeg-release.aar'))
            task.abis.set(abis)
        }
        project.tasks.matching { it.name == "merge${variant.name.capitalize()}NativeLibs" }.configureEach { it.dependsOn(validation) }
    }"""
    new_body = """    private static void configureNativeLibraries(Project project, def variant, List<String> abis) {
        // x86_64 build: no private mpv/ffmpeg AARs are shipped, skip ELF verification.
        variant.packaging.jniLibs.keepDebugSymbols.add('**/libc++_shared.so')
    }"""
    g = sub(g, old_body, new_body, "disable private-AAR native verification")
    p.write_text(g, encoding="utf-8")
    print("[patch] wrote buildSrc/.../AbiApkPackaging.groovy")


# ---------------------------------------------------------------------------
# 5. Force ExoPlayer at runtime (defensive; upstream already defaults EXO)
# ---------------------------------------------------------------------------
def patch_player_engine():
    p = TV / "app/src/main/java/com/fongmi/android/tv/setting/PlayerSetting.java"
    if p.is_file():
        j = p.read_text(encoding="utf-8")
        old = """    public static int getEngineCount() {
        return RuntimeModule.MPV.isInstalled() ? ENGINE_MPV + 1 : ENGINE_EXO + 1;
    }"""
        new = """    public static int getEngineCount() {
        return ENGINE_EXO + 1;
    }"""
        j = sub(j, old, new, "force single EXO engine", required=False)
        p.write_text(j, encoding="utf-8")
        print("[patch] wrote PlayerSetting.java")


# ---------------------------------------------------------------------------
# 6. Install the media3 composite settings override
# ---------------------------------------------------------------------------
def install_media3_settings():
    src = pathlib.Path(__file__).with_name("media3_settings.gradle.kts")
    if not src.is_file():
        raise SystemExit(f"[patch] missing companion file: {src}")
    dst = M3 / "settings.gradle.kts"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[patch] wrote {dst} (media3 composite settings)")


def main():
    if not TV.is_dir():
        raise SystemExit(f"[patch] TV source root not found: {TV}")
    if not M3.is_dir():
        raise SystemExit(f"[patch] Media3 source root not found: {M3}")
    patch_settings()
    patch_versions()
    patch_app_build()
    patch_abi_packaging()
    patch_player_engine()
    install_media3_settings()
    print(f"[patch] DONE. TV={TV}  MEDIA3={M3}")
    print(f"[patch] Media3 modules substituted: {len(MODULES)}")


if __name__ == "__main__":
    main()
