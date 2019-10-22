## [2.6.0] - 2019-09-27

This release includes four new device drivers, two bugfixes to device drivers, one minor
enhancement to a device driver, and one new feature for the `labscript_devices` module
itself.

- Support for the LightCrafter DMD. Contributed by Shaun Johnstone. 
  ([PR #43](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/43))

- Support for Tektronix oscilloscopes. Contributed by Russell Anderson.
  ([PR #61](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/61))

- Support for Basler cameras using the free Pylons API (as opposed to the IMAQdx API).
  Contributed by David Meyer.
  (PRs [#69](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/69)
   and [#74](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/74))

- Support for FLIR cameras using the free PyCapture2 API (as opposed to the IMAQdx API).
  Contributed by David Meyer and Dan Barker.
  ([PR #71](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/71))

- Bugfixes to RFBlaster support for Python 3. Contributed by Lincoln Turner.
  ([PR #75](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/75))

- IMAQdxCamera bugfixes: fix a deadlock upon tab restarting, fix a possible freeze when
  acquiring in manual mode at high frame rates, correctly interpret a series of images
  when `snap()` returns a 3D array, workaround a memory leak in the `pynivision`
  library. Contributed by Chris Billington.
  (PRs [#70](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/70),
       [#77](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/77),
       [#79](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/79),
   and [#83](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/83))

- Implement smart programming of camera attributes for cameras inheriting from
  IMAQdxCamera, and allow use of attributes with more complex datatypes. Contributed by
  Chris Billington.
  (PRs [#72](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/72)
   and [#73](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/73))

- Have `labscript_devices` search an additional user-configurable location for device
  classes, settable by its import path as `[DEFAULT]/user_devices` in labconfig.
  Contributed by Chris Billington.
  ([PR #81](https://bitucket.org/labscript_suite/labscript_devices/pull_requests/81))