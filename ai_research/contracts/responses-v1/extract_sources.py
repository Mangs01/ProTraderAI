"""Offline readable copies of retained official HTML; never retrieves URLs."""
from html.parser import HTMLParser
from pathlib import Path


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


if __name__ == "__main__":
    for source in Path(__file__).parent.joinpath("sources").glob("*.html"):
        parser = Text()
        parser.feed(source.read_text(encoding="utf-8"))
        source.with_suffix(".txt").write_text("\n".join(parser.parts) + "\n", encoding="utf-8")
