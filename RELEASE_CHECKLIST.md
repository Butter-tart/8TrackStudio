# 8T desktop release checklist

## Desktop builds

Build on each target OS and architecture. Cross-compilation is not supported.

```sh
python -m unittest discover -s tests -v
python packaging/build_desktop.py
```

Before uploading native artifacts:

- [ ] Application and dependency redistribution licenses have been reviewed.
- [ ] Required license, notice, and source-offer files are included.
- [ ] Windows installer is Authenticode-signed and verified.
- [ ] macOS app is Developer ID-signed, notarized, and stapled.
- [ ] Linux support baseline and glibc requirements are documented.
- [ ] Each artifact has a matching SHA-256 file, manifest, and passed smoke report.
- [ ] The manifest no longer reports unverified signing or redistribution review.
- [ ] Native downloads were tested on clean target machines.

Upload one file per platform, with the platform and architecture in the filename. Keep the checksum and manifest available with the corresponding release files.

## Functional acceptance

- [ ] Desktop starts after installation or extraction without development tools.
- [ ] Desktop records and plays back through a real audio interface.
- [ ] Desktop saves and reopens a `.8t` project.
- [ ] Desktop recovery, effects, and WAV export work.
- [ ] One third-party VST3 plugin has been tested, with its user-installed status documented.
- [ ] Buyer-view purchase, download, install, and launch have been tested.

## Product copy

State these desktop capabilities directly: eight tracks, ten-minute timeline,
native audio devices, effects, songwriting, recovery, and exports.
- Desktop plugins are installed by the user and are not bundled.
- Hardware compatibility depends on the operating system, drivers, and audio interface.

Publish as a preview until clean-machine and real-hardware checks pass. Promote
to stable only after those checks and a buyer walkthrough are complete.
