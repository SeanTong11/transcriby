# Transcriby Release Guide

## 1. Build the Windows package

```bash
powershell -ExecutionPolicy Bypass -File tools\\package_windows.ps1
```

Expected artifact:
- `dist/Transcriby-Windows-<version>.zip`

## 2. Commit and push

```bash
git add .
git commit -m "chore: prepare release vX.Y.Z"
git push origin main
```

## 3. Create tag

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

## 4. Publish GitHub Release with zip

```bash
gh release create vX.Y.Z dist/Transcriby-Windows-<version>.zip \
  --repo SeanTong11/transcriby \
  --title "Transcriby vX.Y.Z" \
  --notes "See changelog for details."
```

## 5. Verify

- Open: https://github.com/SeanTong11/transcriby/releases
- Confirm the release tag, notes, and zip asset are visible.
