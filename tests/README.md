# Tests

    python -m pytest -q
    cd extras/nxmods && make -f Makefile.linux test_modlist && ./test_modlist

The tests run on Linux or Windows with Python 3.12+ (`pip install -r requirements.txt pytest`).
`tests/fake_tools` holds small stand-ins for the Windows tools (texconv, ffmpeg, VGAudioCli...)
so the converter can be tested anywhere; they aren't the real programs.

Some tests need files this repository can't include, and skip themselves without them:

| Folder | What it needs |
| --- | --- |
| `tests/fixtures/ussep/` | USSEP for Switch: `All_CC`, `No_CC` and `SurvivalMode` folders with the plugin, and `USSEP.bsa`, `USSEPA.bsa`, `USSEPT.bsa`, `USSEPV.bsa` (small extracts are enough) |
| `tests/fixtures/havok/` | `staggerbehavior_pc.hkx` and `staggerbehavior_nx.hkx`, the same behavior file from the PC and Switch versions of the game |
| `private-test-data/SkyNX/` (at the repository root) | `Other modpacks/` and `Other converted mods/`: shared Switch modpacks used as real-world samples |

Those folders are in `.gitignore`: never commit them.
