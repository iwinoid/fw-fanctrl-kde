<!--
GitHub Release title:
  New Model, New Harness, New Standard (but no new ability)

The body of this file is the release description. To publish it together with
the package archive:

  gh release create v1.3.1 ../com.github.iwinoid.fw-fanctrl-kde-1.3.1.tar.xz \
    --title "New Model, New Harness, New Standard (but no new ability)" \
    --notes-file docs/release-notes-1.3.1.md
-->

This is a maintenance release. It adds no new features and no new abilities.

It was produced with a new model, a new Harness and a new standard. The stricter
pass found and fixed a number of potential bugs:

- The config editor marked the configuration as modified just by browsing
  strategies, so Save lit up and Reload asked to discard changes.
- Editing one strategy and then switching to another left stale values in the
  editor: the next spin box edit could write the previous strategy's values into
  the newly selected one, and a stale name field could rename the wrong
  strategy.
- The strategy slider stopped following external strategy changes after it had
  been dragged once.
- The offline notification repeated every minute while fw-fanctrl was down. It
  is now sent once per offline episode, with normal urgency.
- Strategy names starting with `-` were accepted, but fw-fanctrl parses them as
  options, so such a strategy could never be activated. They are now rejected.
- A local scratch directory could end up inside the release package, and the
  config page was not covered by QML lint.
- The CI lint job could fail before it ran, because the container image ships
  without git while the checkout step needs it.

Strategy switching, the config editor and the service controls behave exactly as
in 1.3; the fixes only make them more predictable. The package id, the
configuration format and the backend command line are unchanged.
