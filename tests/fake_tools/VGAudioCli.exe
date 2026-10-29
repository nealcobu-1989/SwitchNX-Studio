#!/usr/bin/env python3
"""Stand-ins for the Windows tools, for tests on Linux.

texconv: real conversion with Pillow + etcpak (format, size, mips) so the
converter's checks see real DDS files. It reads BC1-BC5, BC7 and RGBA8 DDS,
writes BC1/BC3/BC4/BC5 and honours "-m N" (N > 0). NvnTexpkg: a real DFvN
made with skynx.nvn when the DDS is one it can store, otherwise (or with
FAKE_NVN_JUNK set) "DFvN" plus junk. VGAudioCli: files with the right magic
numbers. ffmpeg is the real one.
"""
import os, struct, sys
from pathlib import Path

tool = Path(sys.argv[0]).name.lower()
args = sys.argv[1:]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def dds_header(w, h, mips, fourcc):
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hd, 4, 124, 0x0002100F, h, w, 0, 0, mips)
    struct.pack_into("<II4s", hd, 76, 32, 4, fourcc)
    struct.pack_into("<I", hd, 108, 0x401008)
    return bytes(hd)


if tool.startswith("texconv"):
    import etcpak, texture2ddecoder as t2d
    from PIL import Image
    from skynx.textures import inspect
    fmt = args[args.index("-f") + 1]
    w = int(args[args.index("-w") + 1]) if "-w" in args else None
    h = int(args[args.index("-h") + 1]) if "-h" in args else None
    out = Path(args[args.index("-o") + 1]); src = Path(args[-1])
    raw = src.read_bytes(); info = inspect(raw[:256])
    off = 148 if raw[84:88] == b"DX10" else 128
    bw, bh = max(1, info.width // 4), max(1, info.height // 4)
    if info.fmt == "RGBA8":
        img = Image.frombytes("RGBA", (info.width, info.height),
                              raw[off:off + info.width * info.height * 4], "raw", "RGBA")
    elif info.fmt == "BC2":
        from skynx import nvn
        img = Image.fromarray(nvn.top_rgba(nvn.read_dds(raw)).copy(), "RGBA")
    else:
        dec = {"BC1": (t2d.decode_bc1, 8), "BC3": (t2d.decode_bc3, 16), "BC7": (t2d.decode_bc7, 16),
               "BC4": (t2d.decode_bc4, 8), "BC5": (t2d.decode_bc5, 16)}[info.fmt]
        px = dec[0](raw[off:off + bw * bh * dec[1]], info.width, info.height)
        img = Image.frombytes("RGBA", (info.width, info.height), px, "raw", "BGRA")
    w, h = w or info.width, h or info.height
    img = img.resize((w, h))
    want = int(args[args.index("-m") + 1]) if "-m" in args else 0
    data, mips, cw, ch = b"", 0, w, h
    enc = {"BC1_UNORM": (etcpak.compress_bc1, b"DXT1"), "BC3_UNORM": (etcpak.compress_bc3, b"DXT5"),
           "BC4_UNORM": (etcpak.compress_bc4, b"ATI1"), "BC5_UNORM": (etcpak.compress_bc5, b"ATI2")}[fmt]
    while True:
        im = img.resize((max(4, cw), max(4, ch)))
        data += enc[0](im.tobytes("raw", "RGBA"), max(4, cw), max(4, ch)); mips += 1
        if (cw <= 4 and ch <= 4) or mips == want:
            break
        cw, ch = max(1, cw // 2), max(1, ch // 2)
    out.mkdir(parents=True, exist_ok=True)
    (out / src.name).write_bytes(dds_header(w, h, mips, enc[1]) + data)
elif tool.startswith("nvntexpkg"):
    src = Path(args[args.index("-i") + 1]); out = Path(args[args.index("-o") + 1])
    if os.environ.get("FAKE_NVN_FAIL"):
        sys.exit(3)
    try:
        if os.environ.get("FAKE_NVN_JUNK"):
            raise ValueError("junk requested")
        from skynx import nvn
        out.write_bytes(nvn.from_dds(src.read_bytes()))
    except Exception:  # noqa: BLE001
        out.write_bytes(b"DFvN" + b"\0" * 60 + src.read_bytes()[:16])
elif tool.startswith("vgaudiocli"):
    out = Path(args[-1])
    if out.suffix == ".lopus":
        out.write_bytes(b"\x01\x00\x00\x80" + b"\x18\x00\x00\x00" + b"\x00" * 40)
    else:
        body = b"\x11" * 96
        out.write_bytes(struct.pack("<III", 1, 12, len(body)) + body)
elif tool.startswith("havokbehaviorpostprocess"):
    # Like the real one: reads XML (only contentsversion "hk_2010.2.0-r1") and
    # 32-bit binaries, not 64-bit ones; prints the error and exits 0 without
    # writing anything when it can't load the input.
    src, out = Path(args[-2]), Path(args[-1])
    raw = src.read_bytes()
    plat = next((a[len("--platform"):] for a in args if a.startswith("--platform")), "")
    if plat not in ("ps4", "amd64", "win32", "360", "ps3"):
        print("Could not find platform in list.  [win32, 360, ps3, amd64, ps4]")
        sys.exit(0)
    if os.environ.get("FAKE_HBPP_FAIL") or (raw[:5] == b"<?xml" and b'contentsversion="hk_2010.2.0-r1"' not in raw) \
            or (raw[:4] == b"\x57\xe0\xe0\x57" and raw[16] == 8):
        print(f"Could not load resource: {src}.  Does file exist?  Is it a proper Havok file?")
        sys.exit(0)
    if raw[:5] == b"<?xml":
        import re
        m = re.search(rb"<!--fake:([0-9a-f]+)-->", raw)
        body = bytearray(bytes.fromhex(m.group(1).decode()) if m else b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10" + bytes(56))
    else:
        body = bytearray(raw)
    body[16:20] = bytes([8, 1, 1 if plat == "ps4" else 0, 1])
    out.write_bytes(bytes(body))
    print(f"Saved {out}.")
elif tool.startswith("hkxc"):
    # serde-hkx: "convert -i IN -o OUT -v xml"; keeps the input inside the XML.
    i, o = Path(args[args.index("-i") + 1]), Path(args[args.index("-o") + 1])
    raw = i.read_bytes()
    if os.environ.get("FAKE_HKXC_FAIL") or raw[:4] != b"\x57\xe0\xe0\x57":
        sys.exit("error: not a hkx file")
    o.write_bytes(b'<?xml version="1.0" encoding="ascii"?>\n<hkpackfile classversion="8" '
                  b'contentsversion="hk_2010.2.0 - r1" toplevelobject="#0001">\n<!--fake:'
                  + raw.hex().encode() + b'-->\n</hkpackfile>\n')
else:
    sys.exit(f"unknown fake tool {tool}")
