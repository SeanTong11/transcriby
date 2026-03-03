# Release Automation Guide (Windows/macOS)

## Release Types

- Stable release: triggered by `v*` tags (for example `v0.4.0`) and published as a normal GitHub Release.
- Nightly release: triggered by pushes to `main` and continuously updated under the `nightly` prerelease tag.

## Current Workflows

- Windows: `.github/workflows/windows-release.yml`
  - Uses a pinned shinchiro `mpv-dev` release via `MPV_WINBUILD_TAG`
  - Downloads and extracts `libmpv` runtime from GitHub releases
  - Produces `Transcriby-Windows.zip` and `SHA256SUMS.txt`
- macOS: `.github/workflows/macos-release.yml`
  - Builds both `arm64` and `x64`
  - Produces `Transcriby-macOS-arm64.zip`, `Transcriby-macOS-x64.zip`, and architecture-specific SHA256 files

## Recommended Release Flow

1. Ensure nightly builds from `main` are green.
2. Run manual regression checks (playback, speed, loop, favorites, import/export).
3. Create a stable version tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

4. Verify release assets include:
   - Windows zip + SHA256
   - macOS arm64/x64 zips + SHA256

## Rollback Strategy

- Nightly rollback: push a fix to `main`; the next nightly run replaces the previous artifacts.
- Stable rollback: publish a new corrective tag (for example `vX.Y.Z+1`) instead of mutating an existing stable tag.

## Maintenance Notes

- Keep `MPV_WINBUILD_TAG` pinned; do not track `latest`.
- When updating `MPV_WINBUILD_TAG`, validate with a manual workflow run on a branch before merging.
- Keep artifact names stable to avoid overwrite conflicts when updating nightly releases.
