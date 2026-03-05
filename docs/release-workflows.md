# Release Automation Guide (Windows/macOS)

## Release Types

- Stable release: triggered by `v*` tags (for example `v0.4.0`) and published as a normal GitHub Release.
- Nightly release: triggered by pushes to `main` and continuously updated under the `nightly` prerelease tag.

## Current Workflows

- Windows: `.github/workflows/windows-release.yml`
  - Uses a pinned shinchiro `mpv-dev` release via `MPV_WINBUILD_TAG`
  - Downloads and extracts `libmpv` runtime from GitHub releases
  - Generates build metadata (`app_version`, `build_tag`, `build_commit`, `channel`) before packaging
  - Produces `Transcriby-Windows.zip` and `SHA256SUMS.txt`
- macOS: `.github/workflows/macos-release.yml`
  - Builds both `arm64` and `x64`
  - Installs `mpv` only for build-time dependency resolution, then bundles `libmpv.dylib` into `Transcriby.app/Contents/Frameworks`
  - Runs packaged-app smoke check (`--smoke-check`) after unsetting mpv-related env vars and temporarily removing common system `libmpv` files
  - Smoke check fails unless resolved `libmpv` path is inside the app bundle
  - Generates build metadata (`app_version`, `build_tag`, `build_commit`, `channel`) before packaging
  - Produces `Transcriby-macOS-arm64.zip`, `Transcriby-macOS-x64.zip`, and architecture-specific SHA256 files

## Version Binding

- Runtime version comes from `transcriby/build_version.py`.
- CI updates `transcriby/build_version.py` using `tools/set_build_version.py`:
  - `v*` tag builds: `channel=stable`, `app_version=<tag without v>`
  - `main` builds: `channel=nightly`, `app_version=<base>-nightly+<shortsha>`
- Exported `.tby` files include `build_info` so session files carry the app build identity.

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

## Icon Generation From SVG

Use the icon generation script to rebuild all app icon assets from a single SVG source.

Recommended command:

```bash
uv run --with cairosvg --with pillow python tools/generate_icons_from_svg.py \
  --svg transcriby/resources/Icona-clean.svg
```

What it generates:

- `transcriby/resources/Icona-{16,20,24,32,40,48,64,96,128,256,1024}.png`
- `transcriby/resources/icona.png` (256x256 alias)
- `transcriby/resources/Icona.ico` (exact multi-size PNG frames for Windows)

Useful options:

- `--supersample 8`: render at `size*8` before downsampling (improves small-size quality).
- `--padding 0.06`: enforce transparent edge padding and centered composition.
- `--no-small-sharpen`: disable mild sharpening for `<=48px` icons.

If taskbar/titlebar still shows stale icons on Windows, clear icon cache:

```powershell
powershell -ExecutionPolicy Bypass -File tools/refresh_windows_icon_cache.ps1
```

## Rollback Strategy

- Nightly rollback: push a fix to `main`; the next nightly run replaces the previous artifacts.
- Stable rollback: publish a new corrective tag (for example `vX.Y.Z+1`) instead of mutating an existing stable tag.

## Maintenance Notes

- Keep `MPV_WINBUILD_TAG` pinned; do not track `latest`.
- When updating `MPV_WINBUILD_TAG`, validate with a manual workflow run on a branch before merging.
- Keep artifact names stable to avoid overwrite conflicts when updating nightly releases.
