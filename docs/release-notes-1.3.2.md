<!--
GitHub Release title:
  Saving and Packaging Fixes

The body of this file is the release description. To publish it together with
the package archive:

  gh release create v1.3.2 ../com.github.iwinoid.fw-fanctrl-kde-1.3.2.tar.xz \
    --title "Saving and Packaging Fixes" \
    --notes-file docs/release-notes-1.3.2.md
-->

This is a maintenance release. It adds no new features.

## Configuration editing

- Apply and OK in the Plasma configuration dialog now save the curve
  configuration. Before, they closed the dialog and discarded the edits.
  Cancel now asks before it throws changes away.
- Saving a configuration larger than 4 KB works. fw-fanctrl reads each command
  with a single 4 KB socket read, and the old send format left about 177 bytes
  of room, so adding one strategy made every save fail.
- The editor reports why a save was rejected. An oversized configuration gets
  an explicit message instead of a socket error.

## Status and strategy switching

- The strategy slider can no longer show a strategy that was not applied.
  Refused or failed changes move the slider back to the active strategy.
- Fast repeated changes keep the correct strategy name in the OSD.
- A missing temperature shows `--` instead of 0.0 °C.
- Status messages stay visible after the popup is collapsed.
- Service errors show a short text. Raw shell output and JSON blobs no longer
  appear in the status line or in notifications.

## Installation and CI

- `make install` builds the release archive and installs that archive. It no
  longer copies the whole checkout into the install directory when
  `kpackagetool6` fails, and it never starts a second plasmashell.
- Plasma is not restarted by default. Run `make restart-plasma` when needed.
- The CI lint gate uses qmllint's JSON output and fails on any diagnostic. The
  old text filter hid import, alias and property errors.
- CI checks the exact package contents, the helper's execute bit and the
  metadata icon. The Python tests grow from 36 to 103 cases.

The package id, the configuration format and the backend command line are
unchanged. Upgrade with `make install`, or with
`kpackagetool6 --type=Plasma/Applet --upgrade <archive>`.
