# Third-party code

## Native prototype dependencies

- binjnes: https://github.com/binji/binjnes
  - Revision: `e2f5871a28ff189daa82b70be9324a42e2aaf9fd`.
  - MIT, Copyright 2021 Ben Smith (source headers retain their individual years).
  - Required core files are included with an optional internal/cartridge RAM-write observer/filter in emulator.c/h; upstream/local hashes and the exact patch are in `binjnes/PROVENANCE.json` and `binjnes/wiiz-ram-observer.patch`. Timing, CPU/PPU/APU and mapper algorithms are retained.
  - CPU, PPU, APU, Mapper 1/MMC1 and Mapper 4/MMC3, controller and reset APIs are reused.
  - Only core C11 sources are built. Sokol, upstream UI, rewind, third-party submodules and test ROMs are not included or needed.
  - Palette in upstream emulator.c references palgen-persune; MIT-0 (Copyright 2024 Persune),
    retained in `binjnes/PALETTE-LICENSE.txt`: https://github.com/Gumball2415/palgen-persune/blob/main/LICENSE .
  - Application adapter corrects unspecified Wiz1 PRG-RAM size to 8 KiB for the hash-verified ROM,
    and releases upstream audio storage before calling its destructor. These are adapter changes; the optional RAM callback patch is described above.
  - 3 target ROMs pass 720-frame execution, generated video/audio, reset RAM preservation/vector,
    and 8 KiB battery save roundtrip tests on Windows MSVC. Android is not yet verified.
  - Install retains both licenses. Selection rationale and remaining limitations: `docs/native-core.md`.

- SDL 3.2.28: https://github.com/libsdl-org/SDL/releases/tag/release-3.2.28
  - zlib license; official sources fetched by CMake. Windows applies a local Switch SPI reply validation patch; exact patch, rationale, hashes and retained license are in `sdl3/`. Existing controller protocol/calibration decoding is retained; no extra dependency or Mapper role.
  - ZIP SHA256: `24a30069af514a6c6b773bdc8ccca8b321661b251381acc1daeebf8c8f4a109a`.
  - Used for window/render/input/dialog/file APIs. Windows verified locally; Android not yet integrated.
  - CMake install retains LICENSE.txt as licenses/SDL3.txt. SDL has no ROM Mapper role.
- PicoSHA2: https://github.com/okdshin/PicoSHA2
  - Revision: `161cb3fc4170fa7a3eca9e582cebd27cc4d1fe29`.
  - MIT, Copyright (c) 2017 okdshin; unmodified header and LICENSE in picosha2/.
  - Header SHA256: `b13c180161ffac8d0adc81e033e493c409457c4d1258ab9781ac80579ba3bdd8`.
  - Header-only standard C++ dependency; validates ROM revisions before ROM-specific extraction.
  - CMake install retains license as licenses/PicoSHA2.txt.

## JSNES 2.1.0

Native save additions:
- bryful/Wiz, MIT, revision `020e0b5eb180595d7ce879d8305ed3792c49455d`: existing FC I/II/III character layouts, CRC16 and mirror reconstruction adapted in `app/save_json.cpp`. Unmodified C# references, license and provenance are in `wiz-save/`. No C# runtime or Mapper implementation is added. Actual-ROM carry handling correction and verification: `docs/save-data.md`.
- nlohmann/json 3.12.0, MIT, official unmodified single header and license in `nlohmann/`; version, source and hashes in PROVENANCE.json. Standard C++ only, no runtime dependency or Mapper role. Both licenses are retained by CMake install.
- binjnes's existing state serializer is reused. The application adapter adds non-pointer frame/resampler storage around its state payload; CPU/PPU/APU/Mapper algorithms remain upstream.

- Upstream: https://github.com/bfirsh/jsnes
- Source revision: `cbad9f1db57dfb275b90ffa26f9c479c355d8d5c`
- Distribution: https://registry.npmjs.org/jsnes/-/jsnes-2.1.0.tgz
- License: Apache-2.0; see `jsnes/LICENSE` and `jsnes/AUTHORS.md`.
- Verification: tarball SHA512 matched the npm `dist.integrity` recorded in `jsnes/PROVENANCE.json`.

The runtime sources and `dist/jsnes.js` are unmodified copies from the official npm package. AUTHORS.md is from the corresponding upstream revision. Unused npm distribution artifacts were omitted. There are no runtime npm dependencies. The local BGM adapter lives outside this directory in `web/audio/driver.js`; it selects music through the original ROM driver's RAM interface and filters unrelated game-scene sound requests. Generated players retain the upstream license and author list.

- GBWiz inventory UI: local `../GBWiz/src/item_menu.h`, MIT, Copyright (c) 2026 bryful. The two-character paused editor and flag-preserving action model are adapted for NES in `app/item_editor.hpp`; original source, license and provenance are retained in `gbwiz-items/`. Gambatte is not linked; native equipment recalculation uses the already-adopted binjnes Mapper 1/4 cores and the user's ROM. See `docs/item-editor.md` for supported contexts and validation.
