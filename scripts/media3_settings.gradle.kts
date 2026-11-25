// Composite-build settings for FongMi/media @ release-1.11.0-fongmi.
// Installed into the Media3 checkout by scripts/patch.py. Restricts the build to
// the modules the TV app substitutes, and provides tiny stubs for modules that
// are referenced transitively but not needed at runtime.
import androidx.media3.buildlogic.Media3Modules

pluginManagement {
  includeBuild("build-logic-settings")
  includeBuild("build-logic")
  repositories {
    google()
    mavenCentral()
    gradlePluginPortal()
  }
}

plugins { id("gradlebuild.media3-settings-logic") }

rootProject.name = "androidx.media3"

val requiredModules =
  setOf(
    "lib-common",
    "lib-container",
    "lib-database",
    "lib-datasource",
    "lib-datasource-okhttp",
    "lib-datasource-rtmp",
    "lib-decoder",
    "lib-decoder-ffmpeg",
    "lib-exoplayer",
    "lib-exoplayer-dash",
    "lib-exoplayer-hls",
    "lib-exoplayer-rtsp",
    "lib-exoplayer-smoothstreaming",
    "lib-extractor",
    "lib-session",
    "lib-ui",
    "lib-ui-danmaku",
    "lib-mpvplayer",
  )

Media3Modules.EXTERNAL_MODULES.forEach { (gradleName, moduleInfo) ->
  if (gradleName in requiredModules) {
    include(":$gradleName")
    project(":$gradleName").projectDir = file(moduleInfo.directory)
  }
}

// Some included modules reference these at compile time. Provide empty Android
// libraries from a sibling directory written by the workflow so the composite
// resolves without pulling in tests/inspector.
val stubRoot = rootDir.parentFile.resolve("media3-stubs")
setOf("lib-inspector", "test-data", "test-utils", "test-utils-robolectric").forEach { gradleName ->
  val dir = stubRoot.resolve(gradleName)
  if (dir.isDirectory) {
    include(":$gradleName")
    project(":$gradleName").projectDir = dir
  }
}
