# Phase UX19 - Cloud Status Copy Safety

## Goal

Keep cloud analysis status and error copy short, honest, and readable on small iPhones while preventing secrets, storage paths, or presigned URL fragments from reaching the UI.

## Architecture

- Cloud remains responsible for analysis, candidate generation, GPT editing, render planning, rendering, and storage.
- iOS only displays cloud job status and backend error copy after sanitizing it for user visibility.
- No local iOS analysis, rendering, composition, or fake progress was added.

## Changes

- Cloud analysis progress stages now collapse whitespace and cap visible text at 72 characters.
- Backend error messages shown to users now cap at 96 characters.
- URL, presigned-link, R2/S3, object-key, credential, token, and fake `thinking`/ETA markers fall back to safe product copy.
- Timeout messages map to simple copy: `Cloud request timed out. Try again.`
- Retry timeout messages map to `Cloud analysis is retrying.`

## Safety

- Full presigned URLs remain hidden.
- R2/source object keys remain hidden.
- Backend technical diagnostics are not shown verbatim when they are too long or sensitive.
- Status text still reflects real cloud job state; no artificial waits or fake AI-thinking phrases were added.

## Validation

- Added iOS unit coverage for:
  - fake thinking/ETA and secret marker fallback
  - whitespace cleanup
  - compact progress-stage length
  - friendly timeout copy
  - secret-safe backend message fallback
  - compact backend error length

## Launch Recommendation

During real-device TestFlight smoke, include one normal cloud analysis run and one timeout/error-path check. The status card should remain readable without clipped words on smaller iPhones and accessibility text sizes.
