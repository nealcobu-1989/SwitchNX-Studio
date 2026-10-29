"""Switch texture codec (skynx.nvn) and the diet for converted archives (skynx.diet)."""
from __future__ import annotations

import hashlib
import os
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skynx import diet, nvn  # noqa: E402
from skynx.bsa import read_bsa, write_bsa  # noqa: E402
from skynx.textures import inspect  # noqa: E402
from skynx.tools import Toolset, locate  # noqa: E402

FAKE = ROOT / "tests" / "fake_tools"
UPLOADS = Path("private-test-data/SkyNX")
REAL_ROOTS = [UPLOADS / "Other modpacks", UPLOADS / "USSEP"]
USSEPT = UPLOADS / "USSEP" / "USSEPT.bsa"
KS = next((UPLOADS / "Other modpacks").rglob("KS_Hairdo_s_Lite_NoNPCs.bsa"), None) \
    if (UPLOADS / "Other modpacks").is_dir() else None

needs_real = pytest.mark.skipif(not USSEPT.is_file(), reason="real Switch archives not present")


def real_textures():
    """(archive name, path, raw) for every DFvN texture in the real archives."""
    for root in REAL_ROOTS:
        if not root.is_dir():
            continue
        for bsa in sorted(p for p in root.rglob("*") if p.suffix.lower() == ".bsa"):
            arc = read_bsa(bsa)
            with arc.path.open("rb") as f:
                for e in arc.entries:
                    if e.name.lower().endswith(".dds"):
                        raw = arc.read_file(e, f)
                        if raw[:4] == b"DFvN":
                            yield bsa.name, e.path, raw


def mip_error(surf: nvn.Surface, level: int) -> tuple[float, float]:
    """Error of a mip against mip 0 box-downscaled, and the same for the mip
    with its 4x4 blocks shuffled (what a wrong layout would look like)."""
    top = nvn.top_rgba(surf).astype(np.float32)[:, :, :3]
    m = nvn.drop_mips(surf, level)
    px = nvn.top_rgba(m).astype(np.float32)[:, :, :3]
    f = 1 << level
    ref = top.reshape(m.height, f, m.width, f, 3).mean(axis=(1, 3))
    blocks = px.reshape(m.height // 4, 4, m.width // 4, 4, 3).transpose(0, 2, 1, 3, 4)
    flat = blocks.reshape(-1, 4, 4, 3)
    shuffled = flat[np.random.default_rng(1).permutation(len(flat))]
    sh = shuffled.reshape(blocks.shape).transpose(0, 2, 1, 3, 4).reshape(px.shape)
    return float(np.abs(px - ref).mean()), float(np.abs(sh - ref).mean())


# ------------------------------------------------------------------ codec, synthetic
@pytest.mark.parametrize("fmt", sorted(nvn.FORMATS))
@pytest.mark.parametrize("size", [(1024, 512), (256, 256), (48, 80), (8, 8), (300, 20)])
def test_build_and_read_back(fmt, size):
    w, h = size
    rng = np.random.default_rng(fmt * 7 + w)
    mips = nvn.MAX_MIPS if w * h > 64 else 1
    mips = min(mips, max(w, h).bit_length())
    levels = [rng.integers(0, 256, nvn.linear_size(fmt, w, h, lv), dtype=np.uint8).tobytes()
              for lv in range(mips)]
    surf = nvn.Surface(fmt, w, h, False, [levels])
    raw = nvn.build(surf)
    tex = nvn.parse(raw)
    assert (tex.width, tex.height, tex.fmt, tex.mips, tex.style) == (w, h, fmt, mips, "nvn")
    assert raw[nvn.FILE_HEADER.size + nvn.BLOCK_HEADER.size + nvn.TEX_INFO.size:][:4] == b"HBvN"
    back = nvn.deswizzle(tex)
    assert back.levels == surf.levels
    assert nvn.build(back) == raw
    # through a PC DDS and back
    dds = nvn.write_dds(back)
    assert nvn.read_dds(dds).levels == surf.levels
    assert nvn.from_dds(dds) == raw
    info = inspect(raw[:256])
    assert (info.container, info.width, info.height, info.mips) == ("NVN", w, h, mips)


def test_block_linear_matches_the_gob_rules():
    # 128 x 16 bytes, block height 2: second GOB column starts 1024 bytes in
    offs = nvn._nvn_offsets(128, 16, 2, 1)
    assert offs[0, 0] == 0 and offs[0, 16] == 32 and offs[1, 0] == 16 and offs[2, 0] == 64
    assert offs[0, 32] == 256 and offs[8, 0] == 512 and offs[0, 64] == 1024
    assert sorted(offs.ravel().tolist()) == list(range(128 * 16))
    assert [nvn.block_height(r) for r in (512, 128, 64, 32, 16, 8, 2)] == [16, 16, 8, 4, 2, 1, 1]


def test_layers_and_cubemaps_are_stored_one_after_another():
    rng = np.random.default_rng(5)
    fmt, w, h = 0x44, 64, 64
    lv = lambda i: rng.integers(0, 256, nvn.linear_size(fmt, w, h, i), np.uint8).tobytes()  # noqa: E731
    surf = nvn.Surface(fmt, w, h, True, [[lv(i) for i in range(7)] for _ in range(6)])
    tex = nvn.parse(nvn.build(surf))
    assert tex.cube and tex.layers == 6 and tex.slice_size * 6 == tex.data_size
    assert nvn.deswizzle(tex).levels == surf.levels
    dds = nvn.write_dds(surf)
    assert struct.unpack_from("<I", dds, 112)[0] & 0x200 and nvn.read_dds(dds).levels == surf.levels


def test_bgra_dds_is_read_as_rgba():
    px = bytes([10, 20, 30, 40]) * 16           # B, G, R, A
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hd, 4, 124, 0x100F, 4, 4, 16, 0, 1)
    struct.pack_into("<II4s5I", hd, 76, 32, 0x41, b"\0" * 4, 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    surf = nvn.read_dds(bytes(hd) + px)
    assert surf.info.name == "RGBA8" and surf.levels[0][0][:4] == bytes([30, 20, 10, 40])


def test_bad_input_raises_bilingual_errors():
    with pytest.raises(nvn.NvnError) as e:
        nvn.parse(b"DDS " + b"\0" * 200)
    assert e.value.es != e.value.en
    with pytest.raises(nvn.NvnError):
        nvn.parse(b"DFvN" + struct.pack("<III", 16, 1, 1) + b"XXXX" + b"\0" * 40)


# ------------------------------------------------------------------ codec, real files
@needs_real
def test_every_real_texture_round_trips_byte_identical():
    counts = {"identical": 0, "different": [], "unsupported": []}
    styles = set()
    for bsa, rel, raw in real_textures():
        tex = nvn.parse(raw)
        if not tex.supported:
            counts["unsupported"].append((bsa, rel))
            continue
        styles.add(tex.style)
        dds = nvn.write_dds(nvn.deswizzle(tex))
        if nvn.from_dds(dds, tex.style) == raw:
            counts["identical"] += 1
        else:
            counts["different"].append((bsa, rel))
    assert counts["identical"] >= 300, counts
    assert not counts["different"] and not counts["unsupported"], counts
    assert styles == {"nvn", "toolkit"}


@needs_real
def test_real_textures_decode_to_images_not_noise():
    arc = read_bsa(USSEPT)
    by_name = {e.path.lower(): e for e in arc.entries}
    # FaceGen tint (RGBA8): neighbouring pixels are close, unlike a scrambled layout
    for p, e in by_name.items():                # first tint that isn't a flat colour
        if "facetint" in p:
            surf = nvn.deswizzle(nvn.parse(arc.read_file(e)))
            px = nvn.top_rgba(surf).astype(np.int32)
            if px[:, :, :3].reshape(-1, 3).std(axis=0).max() > 5:
                break
    smooth = np.abs(np.diff(px[:, :, :3], axis=1)).mean()
    chunks = surf.levels[0][0]
    scrambled = np.frombuffer(chunks, np.uint8).reshape(-1, 16)
    scrambled = scrambled[np.random.default_rng(0).permutation(len(scrambled))]
    sc = scrambled.reshape(px.shape).astype(np.int32)
    assert smooth < 0.5 * np.abs(np.diff(sc[:, :, :3], axis=1)).mean()
    # BC textures from the Toolkit (packed mips): mips look like mip 0, downscaled
    boots = by_name["textures\\armor\\dwarven\\m\\dwarvenboots.dds"]
    s = nvn.deswizzle(nvn.parse(arc.read_file(boots)))
    assert s.info.name == "BC3"
    for level in (1, 3, 5):
        err, bad = mip_error(s, level)
        assert err < 0.5 * bad, (level, err, bad)


@pytest.mark.skipif(KS is None, reason="NvnTexpkg-made archive not present")
def test_nvntexpkg_layout_mips_look_right():
    arc = read_bsa(KS)
    e = next(e for e in arc.entries if e.name.endswith(".dds"))
    tex = nvn.parse(arc.read_file(e))
    assert tex.style == "nvn" and tex.mips > 6
    s = nvn.deswizzle(tex)
    for level in (1, 3, 5):
        err, bad = mip_error(s, level)
        assert err < 0.5 * bad, (level, err, bad)


# ------------------------------------------------------------------ diet
def no_sdk_tools() -> Toolset:
    return Toolset(FAKE, texconv=FAKE / "texconv.exe")


def pc_dds(w, h):
    import etcpak
    from PIL import Image
    img = Image.new("RGBA", (w, h), (120, 80, 40, 255))
    for x in range(0, w, 8):
        img.putpixel((x, x % h), (255, 255, 255, 255))
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hd, 4, 124, 0x0002100F, h, w, 0, 0, 1)
    struct.pack_into("<II4s", hd, 76, 32, 4, b"DXT5")
    return bytes(hd) + etcpak.compress_bc3(img.tobytes("raw", "BGRA"), w, h)


@pytest.fixture
def small_bsa(tmp_path):
    """A Switch archive with real NVN textures, a PC DDS and non-texture files."""
    pytest.importorskip("etcpak")
    pytest.importorskip("texture2ddecoder")
    if not USSEPT.is_file():
        pytest.skip("real Switch archives not present")
    files = tmp_path / "src"
    files.mkdir()
    arc = read_bsa(USSEPT)
    want, tints = {}, 0
    for e in arc.entries:
        raw = arc.read_file(e)
        tex = nvn.parse(raw)
        if tex.name == "RGBA8" and tints < 2:
            want[e.path] = raw
            tints += 1
        elif e.path.endswith("dwarvenboots.dds") or (tex.name == "BC1" and tex.width == 256
                                                    and "terrain" in e.path and
                                                    not any("terrain" in k for k in want)):
            want[e.path] = raw
    if KS is not None:
        ks = read_bsa(KS)
        e = next(e for e in ks.entries if e.name.endswith(".dds"))
        want[e.path] = ks.read_file(e)
    # an RGBA8 texture with real alpha: has to stay BC3
    rng = np.random.default_rng(3)
    px = rng.integers(0, 256, (256, 256, 4), dtype=np.uint8)
    want["textures\\test\\alpha_rgba.dds"] = nvn.build(nvn.Surface(0x25, 256, 256, False,
                                                                   [[px.tobytes()]]))
    want["textures\\test\\pc_big.dds"] = pc_dds(1024, 1024)
    want["meshes\\test\\thing.nif"] = b"Gamebryo File Format" + bytes(range(256)) * 20
    want["scripts\\test.pex"] = b"\xfa\x57\xc0\xde" + b"x" * 100
    pairs = []
    for i, (rel, raw) in enumerate(want.items()):
        p = files / f"{i}.bin"
        p.write_bytes(raw)
        pairs.append((rel, p))
    bsa = tmp_path / "Small.bsa"
    write_bsa(pairs, bsa)
    return bsa, {k.lower(): v for k, v in want.items()}


def check_result(src, dest, want, plans_by_rel):
    out = read_bsa(dest)
    assert len(out.entries) == len(want)
    got = {e.path: out.read_file(e) for e in out.entries}
    for rel, raw in want.items():
        new = got[rel]
        if not rel.endswith(".dds"):
            assert new == raw                                  # copied as is
            continue
        plan = plans_by_rel[rel]
        if raw[:4] == b"DFvN":
            assert new[:4] == b"DFvN"
            tex = nvn.parse(new)
            assert tex.supported and (tex.width, tex.height, tex.name) == (plan.tw, plan.th, plan.fmt)
            if not plan.changes:
                assert new == raw
        else:
            assert new[:4] == b"DDS "                          # no SDK: PC DDS stays DDS
    return got


def test_diet_without_sdk_uses_own_writer(small_bsa, tmp_path):
    src, want = small_bsa
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    est = diet.estimate_bsa(src, "extreme", bc1=True)
    assert est["nvn_rgba"] == 3 and est["after"] < est["before"] and est["count"] >= 5
    plans = {p.rel.lower(): p for p in diet.plan_bsa(src, "extreme", sdk=False, bc1=True)}
    dest = tmp_path / "out" / "Small.bsa"
    ticks = []
    st = diet.diet_bsa(src, dest, "extreme", no_sdk_tools(), bc1=True,
                       progress=lambda *a: ticks.append(a))
    assert hashlib.sha256(src.read_bytes()).hexdigest() == digest   # source untouched
    assert st["failed"] == 0, st["errors"]
    assert st["nvn_own"] >= 4 and st["nvntexpkg"] == 0 and st["bc1"] == 2
    assert st["drop_mips"] >= 1 and st["after"] < st["before"] and st["other_files"] == 2
    assert ticks[-1] == ("BSA",)
    got = check_result(src, dest, want, plans)
    # the real tints are opaque: BC1; the noisy-alpha one stays BC3
    tints = [r for r in want if "facetint" in r]
    assert all(nvn.parse(got[r]).name == "BC1" for r in tints)
    for r in tints:                              # same picture, same colours
        old = nvn.top_rgba(nvn.deswizzle(nvn.parse(want[r]))).astype(np.int32)
        new = nvn.top_rgba(nvn.deswizzle(nvn.parse(got[r]))).astype(np.int32)
        assert np.abs(old[:, :, :3] - new[:, :, :3]).mean() < 8
    assert nvn.parse(got["textures\\test\\alpha_rgba.dds"]).name == "BC3"
    # dropped mips are the original mips, bit for bit
    boots = next(r for r in want if r.endswith("dwarvenboots.dds"))
    old, new = nvn.deswizzle(nvn.parse(want[boots])), nvn.deswizzle(nvn.parse(got[boots]))
    assert new.width == old.width // 2 and new.levels[0] == old.levels[0][1:]
    # estimated memory went down
    mem = lambda raw: inspect(raw[:256]).est_bytes  # noqa: E731
    assert sum(mem(got[r]) for r in want if r.endswith(".dds")) < \
        sum(mem(want[r]) for r in want if r.endswith(".dds"))
    with pytest.raises(Exception):
        diet.diet_bsa(dest, dest, "extreme", no_sdk_tools())


def test_diet_with_sdk_checks_nvntexpkg_output(small_bsa, tmp_path, monkeypatch):
    src, want = small_bsa
    ts = locate(FAKE)
    assert ts.sdk
    plans = {p.rel.lower(): p for p in diet.plan_bsa(src, "diet", sdk=True, bc1=False)}
    st = diet.diet_bsa(src, tmp_path / "a.bsa", "diet", ts)
    assert st["failed"] == 0 and st["nvntexpkg"] >= 3 and st["nvn_fallback"] == 0
    got = {e.path: e for e in read_bsa(tmp_path / "a.bsa").entries}
    assert set(got) == set(want)
    for rel in want:
        if want[rel][:4] == b"DFvN" and plans[rel].changes:
            assert plans[rel].fmt == "BC3" or plans[rel].action == "drop_mips"
    # a broken NvnTexpkg result is caught and our writer takes over
    monkeypatch.setenv("FAKE_NVN_JUNK", "1")
    st = diet.diet_bsa(src, tmp_path / "b.bsa", "diet", ts)
    assert st["nvn_fallback"] >= 3
    out = read_bsa(tmp_path / "b.bsa")
    for e in out.entries:
        raw = out.read_file(e)
        if e.path in want and want[e.path][:4] == b"DFvN":
            assert nvn.parse(raw).supported


def test_failures_leave_textures_untouched(small_bsa, tmp_path):
    src, want = small_bsa
    st = diet.diet_bsa(src, tmp_path / "c.bsa", "extreme", Toolset(None), bc1=True)
    out = read_bsa(tmp_path / "c.bsa")
    got = {e.path: out.read_file(e) for e in out.entries}
    # no texconv: RGBA8 and the PC DDS fail and are kept; mip drops still work
    assert st["failed"] >= 4 and st["drop_mips"] >= 1 and len(st["errors"]) == st["failed"]
    for rel, raw in want.items():
        if "facetint" in rel or rel.endswith("pc_big.dds"):
            assert got[rel] == raw
