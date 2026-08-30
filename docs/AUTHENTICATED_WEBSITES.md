# Authenticated courses and websites

DubLocal can treat an authenticated course or lesson as another **source** for Magic Flow. It is not a separate dubbing pipeline.

The architectural boundary is deliberate:

```text
Authenticated website
  -> SourceProvider
  -> authorised local media acquisition
  -> normalized local AcquiredMedia
  -> existing DubLocal Magic Flow
     -> subtitles / Whisper
     -> contextual translation
     -> TTS
     -> mixing
     -> export
```

Website adapters do not know about Whisper, Qwen, Kokoro, mixing or export. Once an adapter produces a normal local media file, the established DubLocal pipeline owns the job.

## Simple workflow

In **Main -> Simple**, choose **Course / Website**.

1. Paste a course or direct lesson URL.
2. If the site requires authentication, choose **Open / Sign in**.
3. Sign in directly on the website in the dedicated DubLocal browser window, then close that browser window.
4. Choose **Inspect course / lesson**.
5. Select the lessons to process.
6. Confirm legitimate access / processing rights.
7. Choose the normal subtitles, translation, voice and media outputs.
8. Run Magic Flow.

Lessons run sequentially. A failed lesson is recorded and the queue continues. Completed lessons are persisted in a small course-job manifest so reopening DubLocal and inspecting the course again selects only unfinished/failed work by default.

## Advanced workflow

Advanced keeps the existing stage-by-stage pipeline. **Course / Website** is available as a Source choice there as well, but Advanced intentionally accepts a direct single-lesson URL rather than turning the manual workflow into a course manager.

## Authentication and local privacy

DubLocal never asks for a website password.

Authenticated sources use a dedicated local Chromium profile under the DubLocal application-support directory. The user enters credentials directly into the website. The profile is isolated from the user's ordinary Safari/Chrome profile, so DubLocal does not need access to unrelated browsing data.

Settings -> **Authenticated Websites** provides explicit browser preparation and session clearing. Browser/session data stays local. Temporary yt-dlp cookie export, when needed for acquisition, is written with restrictive permissions inside the job cache and deleted immediately after acquisition.

DubLocal must never persist reusable signed media URLs, Authorization headers, cookie contents or passwords in course manifests or normal diagnostics.

## DRM boundary

DubLocal does not bypass DRM.

The authenticated provider checks obvious protected-player/license endpoints and inspects HLS/DASH manifests when available. Encrypted/protected streams are refused. yt-dlp DRM/encrypted-media errors are also converted into a clear unsupported-source result.

This subsystem must never add Widevine/FairPlay/PlayReady key extraction, CDM manipulation, licence interception or similar circumvention behavior.

If a platform exposes an authorised ordinary download, DubLocal prefers that path. Otherwise it may acquire an unprotected authenticated MP4/WebM/HLS/DASH stream that the signed-in user is already authorised to access.

## Providers

The provider registry has two layers:

- **Built-in site-specific adapters** can add course/lesson discovery while still using the generic authenticated acquisition machinery.
- **Generic authenticated website** fallback handles one normal authenticated video/audio page when ordinary unprotected media can be discovered.

Public documentation intentionally keeps course-platform examples provider-neutral. Specific adapters are application code shipped through normal DubLocal updates; DubLocal does not download executable scraper plugins from arbitrary repositories.

A site changing its HTML/player can break an adapter without breaking the media pipeline. That failure should be reported as a source/import problem, not as a transcription/translation/TTS failure.

## Output and temporary data

Course outputs are organized by provider/course, normally under:

```text
~/Movies/DubLocal/<Provider>/<Course>/
```

Example:

```text
01 - Introduction.fr.srt
01 - Introduction.en.srt
01 - Introduction.voice.en.wav
01 - Introduction.dub.en.mkv
```

Authenticated source media itself is temporary by default and remains under the normal DubLocal job cache. It is eligible for the same cache cleanup as other working media.

## Resume and failure isolation

Course-job manifests store only non-secret provenance and processing state: provider, canonical course/lesson URL without transient query credentials, title/order, state, output paths and error status.

States are per lesson. Completed lessons are not reprocessed on resume. Failed/cancelled lessons remain pending and can be selected again. Stopping a course job keeps completed outputs and prevents later queued lessons from starting, using the same central cancellation lifecycle as other Magic Flow jobs.

## Supported scope

The first implementation supports:

- dedicated authenticated browser profile;
- generic authenticated website acquisition;
- built-in site-specific course/lesson discovery where an adapter is available;
- single lesson and multi-lesson queues;
- lesson multiselect;
- sequential processing;
- persistent resume state;
- failure isolation;
- existing subtitle preservation when the acquired media exposes them;
- ordinary non-DRM media/HLS/DASH acquisition;
- explicit DRM refusal;
- local-only session handling;
- structured course outputs;
- the same Stop/cleanup lifecycle as normal Magic Flow.

Compatibility with an authenticated site is not guaranteed merely because it plays in a browser. Sites can change their markup/player, require unsupported browser challenges, or use DRM. Those cases should fail clearly without changing the established DubLocal processing architecture.
