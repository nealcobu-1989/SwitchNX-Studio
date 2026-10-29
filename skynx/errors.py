"""Errors that carry their message in both languages."""


class SkynxError(Exception):
    def __init__(self, en: str, es: str | None = None):
        super().__init__(en)
        self.en, self.es = en, es or en

    def text(self, lang: str = "en") -> str:
        return self.es if lang == "es" else self.en
