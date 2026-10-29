"""The Help page's manual: generated file up to date, same sections in both
languages, every link and every page's Help target pointing to a real section."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _builder():
    spec = importlib.util.spec_from_file_location("build_manual", ROOT / "docs" / "build_manual.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_manual_js_is_up_to_date():
    b = _builder()
    assert (ROOT / "app" / "web" / "manual.js").read_text(encoding="utf-8") == b.build(), \
        "run: python docs/build_manual.py"


def test_sections_links_and_help_targets():
    b = _builder()
    data = {lang: b.sections((ROOT / "docs" / f"manual.{lang}.md").read_text(encoding="utf-8")) for lang in b.LANGS}
    ids = [s["id"] for s in data["en"]]
    assert ids == [s["id"] for s in data["es"]] and len(ids) == len(set(ids))
    assert ids[0] == "start"
    for lang, secs in data.items():
        for s in secs:
            assert s["html"] and "<script" not in s["html"].lower(), (lang, s["id"])
            for target in re.findall(r'href="#h-([a-z0-9-]+)"', s["html"]):
                assert target in ids, (lang, s["id"], target)
            assert "—" not in s["html"] and "—" not in s["title"], (lang, s["id"])   # no em-dashes
    js = (ROOT / "app" / "web" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"const HELP_FOR = \{(.+?)\};", js, re.S)
    targets = set(re.findall(r':\s*"([a-z0-9-]+)"', m.group(1)))
    targets |= set(re.findall(r'openHelp\("([a-z0-9-]+)"\)', js))
    assert targets and targets <= set(ids), targets - set(ids)


def test_markdown_subset():
    b = _builder()
    secs = b.sections("## One {#one}\n\nA `<b>` **bold** [go](#h-one).\n\n- a\n- b\n\n| x | y |\n| --- | --- |\n| 1 | 2 |\n\n> tip\n")
    h = secs[0]["html"]
    assert "<code>&lt;b&gt;</code>" in h and "<b>bold</b>" in h and '<a href="#h-one">go</a>' in h
    assert "<ul><li>a</li><li>b</li></ul>" in h and "<td>1</td><td>2</td>" in h and 'class="tip"' in h
