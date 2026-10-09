# Delivery validation

Validation performed on 9 October 2026 using the delivered source code, the real API-17 AAR and the checksum-pinned toolchain.

| Check | Result |
| --- | --- |
| Python configuration and publishing tests | 11 tests passed |
| Kotlin extraction fixtures | 15 checks passed |
| Actual source selector syntax | Passed for the supplied MDN source |
| Kotlin source/API compatibility | Compiled against official extensions-lib v17 |
| Android bytecode and APK packaging | D8, aapt and zipalign succeeded |
| APK signing | RSA 3072-bit certificate; APK v2 and v3 signatures verified |
| Manifest/index consistency | Package, entry class, feature, API version and source ID checked |
| Repository signing key | Matches the APK certificate and private setup kit |
| Publishing | Initial publication and update tested with an isolated local bare Git remote |
| Accidental signing-key replacement | Rejected before publication; original branch left unchanged |
| Sample media URL | HTTP 206, video/mp4, first 32 bytes readable |

The Kotlin fixtures cover relative and protocol-relative URLs, query preservation, unsafe URL rejection, hidden/lazy HTML5 videos, JSON-LD, plain script URLs, deduplication, `<base>` resolution, direct videos, parent Referer preservation, iframe allowlists, catalogue selectors and custom video attributes.

The shipped sample extension is compiled for the **local validation identity**, not for a claimed live GitHub repository. Your first workflow run generates packages and repository URLs for your actual GitHub repository. If you manually install the demonstration APK, it is separate from the identically named source later generated under your account; remove the demonstration package when you no longer need it.

Not performed: installation or playback inside Aniyomi on a real Android device/emulator, publication to your GitHub account, or compatibility checks against unspecified extraction websites. A successful build proves packaging/API compilation and fixture behavior, not universal website support.

The current compatibility target is Aniyomi 0.18.2.1 / extensions-lib 17. Aniyomi's own implementation supplies runtime libraries, source loading, playback and downloading.
