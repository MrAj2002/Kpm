# Attribution and dependency notes

This is an independent repository builder, not an official Aniyomi product.

- Aniyomi and its extension API: https://github.com/aniyomiorg/aniyomi and https://github.com/aniyomiorg/extensions-lib. API 17 is used as a compile-only dependency. Its classes are supplied by the installed Aniyomi app.
- Kotlin compiler/standard library and kotlinx libraries: https://github.com/JetBrains/kotlin and https://github.com/Kotlin. Build or compile-only dependencies.
- Jsoup: https://jsoup.org/; OkHttp/Okio: https://square.github.io/okhttp/ and https://square.github.io/okio/. Compile-only dependencies provided at runtime by Aniyomi.
- Android SDK build tools/platform: https://developer.android.com/studio. Downloaded by the workflow; SDK terms apply.
- Additional compile/test dependencies and their exact checksums are listed in dependencies.lock.json. Downloaded third-party tool binaries are not bundled in the source ZIP.
- The sample links to the MDN flower video under its `cc0-videos` path: https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4. No video file is redistributed in the project. MDN video examples: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video.

Primary compatibility references checked when building this project:

- Aniyomi v0.18.2.1: https://github.com/aniyomiorg/aniyomi/releases/tag/v0.18.2.1
- App source commit: 97414446b8a95994c72dd33c41c971a89d4d25b8
- extensions-lib v17: https://github.com/aniyomiorg/extensions-lib/tree/v17
- GitHub manual workflow runs: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

The original engine, generator, workflow and documentation in this project are under the accompanying MIT license. Refer to each dependency's upstream distribution for its own license. The source package includes neither the Aniyomi app nor its API implementation.
