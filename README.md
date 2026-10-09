# Aniyomi Website Repository Builder

Create a personal Aniyomi extension repository. Use a GitHub Actions form to add a website; the workflow builds a signed Android extension APK for that source and publishes the repository index. Each website appears as an independently installable source in Aniyomi.

Targets **Aniyomi 0.18.2.1 with extensions-lib v17**. Future app compatibility is not guaranteed. These are extension APKs loaded by Aniyomi, not standalone apps with launcher icons.

## What adding a URL does

With default rules, a source shows one entry for your supplied URL. Open it and select **Play video**, or paste another full HTTPS video-page URL into that source's search box. The extractor recognizes HTML5 videos, lazy video attributes, direct media links, VideoObject data and plain media URLs inside scripts. It resolves relative URLs and can follow same-host iframes.

It does **not** make every website work automatically. Custom catalogue and episode layouts need site-specific selector rules. JavaScript-only players, encrypted/obfuscated player code, login sessions, CAPTCHA, protected APIs and DRM require a different adapter and are outside this generic engine. HTTPS only. Playback and downloading are handled by Aniyomi and depend on its player, codecs, the media server and stream format.

## Set up from a phone without editing code

The delivered kit contains a private setup HTML file, this public source project and a signed sample extension. **Keep the setup HTML private**: it contains the signing key for future APK updates. Do not upload the complete kit to GitHub. The separately nested `Aniyomi-Public-Source.zip` contains only publishable source files.

1. Extract the kit and open `Aniyomi-Setup-PRIVATE.html` in a browser. If your file viewer disables buttons, select and copy the text fields manually.
2. Sign in to [GitHub](https://github.com/new) and create a **public** repository. Choose a name such as `my-aniyomi-sources`, initialize it with a README, and use `main` as the default branch. Every configured source URL and rule will be public.
3. Open **Add file → Create new file**. For the filename, copy `.github/workflows/repository.yml` from the setup page. Copy its complete workflow into the editor and commit to `main`. On a small screen, use your browser's desktop-site view if GitHub hides the file controls. This is a complete, self-installing workflow; do not change its encoded bundle.
4. Under **Settings → Secrets and variables → Actions → New repository secret**, create `REPO_SIGNING_KEY` and `REPO_SIGNING_PASSWORD`. Copy their values from the private setup page. These belong in repository secrets, never in repository files.
5. Open **Actions → Add website and publish Aniyomi repo → Run workflow**. Select **rebuild** for the first run and leave the other inputs blank/default. Press **Run workflow**. Compilation takes several minutes; it is not instantaneous. GitHub may require you to enable Actions or allow workflow writes for your repository/account.
6. Wait for a successful green run. Its summary contains your actual **store.json URL**. The workflow has also installed the complete source project on `main` and created the public APK/index branch named `repo`.
7. In Aniyomi, open the anime extension repository/store management screen, add the URL from the successful run, then refresh extensions. Install **MDN Flower Demo** to try the supplied public sample. Menu names may vary between app releases.

This requires a GitHub account and one-time setup. No repository was published to your account when the kit was created. Once set up, the workflow form handles further builds and publication; no cloud IDE, Gradle project editing or Android Studio installation is needed.

## Add, update or remove websites

Open the same **Run workflow** form:

| Input | What to enter |
| --- | --- |
| operation | `add-or-update` to add/change a source; `rebuild` to republish all; `remove` to remove a source from the store |
| source_id | A stable ID such as `my-video-site`. Reuse exactly this ID for updates/removal. |
| source_name | The name displayed in Aniyomi. Required when adding; blank preserves it on updates. |
| source_url | The website/video-page HTTPS URL. Required when adding; blank preserves it on updates. |
| language | `en`, `ja`, another two-letter code, or `all`. New sources default to `all`. |
| adult | `preserve` keeps the previous value; `true` marks adult content; `false` marks general content. |
| rules | Leave blank for generic extraction or to preserve existing rules. `{}` resets to generic rules. |

After the run succeeds, refresh Aniyomi's extensions and install/update the source. The workflow does not silently install software on your phone. Removing a source from the store does not uninstall an extension already installed on your device.

For a catalogue, episode list or external iframe player, see [the extraction rules guide](docs/RULES.md). A selector configuration depends on the actual website HTML. Share the website URL with your coding assistant if you want its rules prepared; there is no universal selector that works for all layouts.

## Playback, downloads and history

This repository integrates into Aniyomi. Aniyomi supplies its player, download manager, library and history. There is no browser CORS proxy or Blob downloader in the extension. HLS links are returned as streams; the extension does not pretend that saving an `.m3u8` manifest saves the whole video. Do not put private session tokens or account cookies into public source definitions.

## Updates and signing

Keep a backup of your private signing setup file. One certificate signs every extension in this store. Publication stops if its fingerprint differs from the existing store. Losing this key means existing Android installations cannot accept normally signed updates from a replacement key.

Package names and source IDs are derived from the GitHub repository name and source ID. **Keep both stable**. Renaming/transferring the GitHub repository changes those identities and repository URLs on subsequent builds. Each new workflow run supplies an increasing APK version code. Use a new **Run workflow**, rather than rerunning an old run, for a new release. If you delete/recreate the workflow or reset run numbering, ensure the next version code exceeds published versions before issuing updates.

The repository has a modern `store.json`, a legacy entry `index.min.json` that points current clients to the modern store via `repo.json`, APKs, an icon and SHA-256 checksums. Legacy metadata does not make these API-17 APKs compatible with old Aniyomi versions.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Workflow is missing | Confirm the file is at `.github/workflows/repository.yml` on the default `main` branch, then enable Actions. |
| Missing signing key/password | Add both repository secrets using the exact names above. |
| Git push returns 403 | In repository Actions settings, allow the workflow's requested write permissions. Organization rules can still restrict them. |
| APK unsupported in Aniyomi | Use an app version supporting extension library 17; this project was checked against 0.18.2.1. |
| No static video URL found | Try a specific video-page URL; configure selectors/external iframe hosts if needed. Dynamic/protected players need a site-specific adapter. |
| One entry appears, no catalogue | Default mode opens the supplied URL. A browsable catalogue requires `catalogPath` and `itemSelector`. |
| Playback fails after links are found | The server may require headers, an expiring token, a different codec or another adapter. A successful build does not validate every website. |
| Download fails for HLS/DRM | Stream download support is determined by Aniyomi and the server; DRM is unsupported by this extractor. |

## Build and verification details

The workflow uses Python 3.12, JDK 17, Kotlin 2.4.0, Android build-tools 35 and compile-only Aniyomi API 17. Download URLs and SHA-256 hashes are pinned in `dependencies.lock.json`. Android tooling is fetched from Google; other tools are from Maven Central and the official Aniyomi JitPack artifact. Review the applicable SDK terms at [Android SDK terms](https://developer.android.com/studio/terms).

`scripts/build.py` compiles Kotlin, converts bytecode with D8, builds the manifest/resources, aligns and signs each APK, verifies the certificate and writes repository metadata. Runtime libraries are supplied by Aniyomi rather than duplicated into each APK. `scripts/publish.py` uses ordinary Git commits and non-forced pushes; signing files and caches are excluded.

Validation performed for the delivered build is recorded in `docs/VALIDATION.md`. No Android device or emulator was available for an in-app playback test. Website compatibility must be checked with the specific source and phone.

For developers with Linux, Python and JDK 17, run `python scripts/signing.py /private/path` once to create a separate signing kit, set `REPO_SIGNING_PASSWORD` from it, then run `python scripts/build.py --repository owner/repo --key /private/path/repo.p12`. `owner/repo` is an argument example, not a live repository address. The GitHub workflow supplies your real value automatically.

## Project files

| Path | Purpose |
| --- | --- |
| `.github/workflows/repository.yml` | Complete no-code form, bootstrap and cloud publishing pipeline |
| `sources/` | Public website configurations |
| `engine/` | Kotlin extraction engine and Aniyomi API integration |
| `scripts/source.py` | Input validation and source management |
| `scripts/build.py` | Tool verification, compilation, APK signing and indexes |
| `scripts/publish.py` | Stable-key check and Git publication |
| `scripts/test_parser.py`, `tests/` | Extraction, configuration and publishing checks |
| `scripts/signing.py` | Optional developer utility to create a new private key |
| `dependencies.lock.json` | Verified tool/dependency checksums |

Original project code is provided under the MIT license. See `NOTICE.md` for dependency and sample attribution.
