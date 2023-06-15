import re
from typing import Optional
from config import logger

logger = logger.bind(tags=["discord_bot"])


def alias_by_prefix(
    text: str,
    starting_at: int = 2,
    include_full=False,
    exclude: Optional[list[str]] = None,
) -> list[str]:
    """eg "equip" -> ["eq", "equ", "equi"]

    Args:
        text:
        starting_at: Defaults to 2.
        include_full: Defaults to False.
        except_: Defaults to None.
    """
    aliases = []
    end = starting_at
    while end < len(text):
        aliases.append(text[:end])
        end += 1

    if include_full:
        aliases.append(text)

    if exclude:
        for x in exclude or []:
            aliases.remove(x)

    return aliases


def extract_quoted(
    text: str, tokens: Optional[list[str]] = None
) -> tuple[str, list[tuple[str | None, str]]]:
    """Extracts quoted substrings

    For example...
        the 'lazy dog' jumped over the"brown bear"
    becomes...
        [
            "the  jumped over",
            [
                ("lazy dog", ""),
                ("brown bear", the)
            ]
        ]
    """

    tokens = tokens or ['"', "'"]

    def main():
        rem = text
        substrings: list[tuple[str | None, str]] = []

        while True:
            start = find_next_token(rem)
            end = find_next_token(rem, start + 1)

            if end == -1:
                rem = purge_tokens(rem)
                break
            else:
                sub = rem[start + 1 : end]  # does not include quote-tokens
                prefix = get_prefix(rem, start)
                substrings.append((prefix, sub))
                rem = rem[0 : start - len(prefix or "")] + rem[end + 1 :]

        return (rem, substrings)

    def find_next_token(text: str, start=0) -> int:
        for t in tokens:
            idx = text.find(t, start)
            if idx != -1:
                return idx
        else:
            return -1

    def purge_tokens(text: str) -> str:
        for t in tokens:
            text = text.replace(t, "")
        return text

    def get_prefix(text: str, prefix_end: int) -> str | None:
        idx = prefix_end
        prefix = ""
        while idx > 0:
            idx -= 1
            char = text[idx]

            if char.strip():
                prefix = char + prefix
            else:
                break
        return prefix if prefix else None

    return main()


def paginate(*texts: str, page_size=1950) -> list[str]:
    def main():
        lines = to_lines(texts)
        cbs = find_code_blocks(lines)
        pages: list[list[str]] = []

        # Reserve space for wrapping a page in codeblock (```py...```)
        CODEBLOCK_SIZE = 12

        pg: list[str] = []
        pg_top = 0
        content_size = 0  # sum of line lengths, excluding \n
        for idx in range(len(lines)):
            line = lines[idx]
            total_size = content_size + len(line) + len(pg)

            # Handle edge case of insanely long line
            if len(line) > page_size - CODEBLOCK_SIZE:
                logger.warning(f"Truncating long line: {line}")
                line = line[: page_size - CODEBLOCK_SIZE]

            # Check if new page needed
            if total_size > page_size - CODEBLOCK_SIZE:
                # Fix any broken code blocks
                cb_top = find_cb(pg_top, cbs)
                if cb_top and cb_top[0] != pg_top:
                    pg = [f"```{cb_top[2]}"] + pg

                cb_bot = find_cb(idx, cbs)
                if cb_bot and cb_bot[1] != idx:
                    pg.append("```")

                # Start new page
                pg_top = idx
                pages.append(pg)
                pg = [line]
                content_size = len(line)
            else:
                pg.append(line)
                content_size += len(line)

        if pg:
            # Fix any broken code blocks
            cb_top = find_cb(pg_top, cbs)
            if cb_top and cb_top[0] != pg_top:
                pg = [f"```{cb_top[2]}"] + pg

            # New page
            pages.append(pg)

        result = ["\n".join(pg) for pg in pages]
        return result

    def to_lines(texts: tuple[str]) -> list[str]:
        lines = []
        for t in texts:
            lns = [x for x in t.split("\n")]
            lines.extend(lns)
        return lines

    def find_code_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
        """Find markdown-style code blocks (start (inclusive) / end (exclusive) / language)

        Code blocks are surrounded by ```
        Insane cases like `````` are not considered

        None of the [start, end) intervals returned should overlap
        """
        blocks: list[tuple[int, int, str]] = []

        start = None
        lang = ""
        for idx, l in enumerate(lines):
            ms = re.findall(r"```(\w*)", l)
            if len(ms) == 1:
                if start is None:
                    # Found start
                    start = idx
                    lang = ms[0]
                else:
                    # Found end
                    blocks.append((start, idx + 1, lang))
                    start = None
                    lang = ""
            elif len(ms) == 2:
                if start is None:
                    # Found one-liner
                    blocks.append((idx, idx + 1, ms[0]))
                else:
                    # Found end of old one and start of new one
                    blocks.append((start, idx + 1, ms[1]))
                    start = idx
            elif len(ms) > 2:
                # Ignore the crazy, output is probably wrong from here on
                logger.warning(f">6 backticks on line: {l}")

        return blocks

    def find_cb(
        idx: int, cbs: list[tuple[int, int, str]]
    ) -> tuple[int, int, str] | None:
        for cb in cbs:
            (start, end, _) = cb
            if idx >= start and idx < end:
                return cb
        else:
            return None

    return main()
