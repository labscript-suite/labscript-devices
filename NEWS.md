## [2.6.0] - 2019-10-22

This release includes four new device drivers, two bugfixes to device drivers, one minor
enhancement to a device driver, and one new feature for the `labscript_devices` module
itself.

- Support for the LightCrafter DMD. Contributed by Shaun Johnstone, with fixes and
  enhancements from Michael Doris, Ian Spielman, Francisco Salces and Chris Billington.
  ([PR #43](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/43))

- Support for Tektronix oscilloscopes. Contributed by Russell Anderson.
  ([PR #61](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/61))

- Support for Basler cameras using the free Pylons API (as opposed to the IMAQdx API).
  Contributed by David Meyer.
  (PRs [#69](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/69)
   and [#74](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/74))

- Support for FLIR cameras using the free PyCapture2 API (as opposed to the IMAQdx API).
  Contributed by David Meyer and Dan Barker.
  ([PR #71](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/71))

- Bugfixes to RFBlaster support for Python 3. Contributed by Lincoln Turner.
  ([PR #75](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/75))

- IMAQdxCamera bugfixes: fix a deadlock upon tab restarting, fix a possible freeze when
  acquiring in manual mode at high frame rates, correctly interpret a series of images
  when `snap()` returns a 3D array, workaround a memory leak in the `pynivision`
  library. Contributed by Chris Billington.
  (PRs [#70](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/70),
       [#77](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/77),
       [#79](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/79),
   and [#83](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/83))

- Implement smart programming of camera attributes for cameras inheriting from
  IMAQdxCamera, and allow use of attributes with more complex datatypes. Contributed by
  Chris Billington.
  (PRs [#72](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/72)
   and [#73](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/73))

- Have `labscript_devices` search an additional user-configurable location for device
  classes, settable by its import path as `[DEFAULT]/user_devices` in labconfig.
  Contributed by Chris Billington.
  ([PR #81](https://bitbucket.org/labscript_suite/labscript_devices/pull-requests/81))