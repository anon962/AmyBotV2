from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

Alignment = Literal["left", "center", "right"]


def clip(x: Any, max_width: int, tail: Optional[str] = None):
    """Truncate long strings"""
    text = str(x)
    if tail and len(text) > max_width:
        end = max_width - len(tail)
        text = text[:end] + tail
    text = text[:max_width]
    return text


@dataclass
class Col:
    header: str = ""
    trailer: str = ""
    padding_left: int = 1
    padding_right: int = 1
    align: Alignment = "left"
    stringify: Callable[[Any], str] = str

    def pad(self, text: str, content_width: int) -> str:
        ws = lambda n: " " * n

        if len(text) > content_width:
            raise Exception((text, content_width))

        rem = content_width - len(text)
        if self.align == "left":
            result = text + ws(rem)
        elif self.align == "right":
            result = ws(rem) + text
        elif self.align == "center":
            lpad = rem // 2
            rpad = rem - lpad
            result = ws(lpad) + text + ws(rpad)
        else:
            raise Exception(self.align)

        result = ws(self.padding_left) + result + ws(self.padding_right)
        return result


@dataclass
class Table:
    cells: list[list] = field(default_factory=list)
    cols: list[Col] = field(default_factory=list)
    draw_outer_borders: bool = False
    draw_col_headers: bool = True
    draw_col_trailers: bool = False

    col_div = "|"
    row_div = "-"
    intersection_inner = "-"
    intersection_outer = "+"

    def __post_init__(self):
        # Check for jagged data
        assert all(len(row) == len(self.cols) for row in self.cells)

        # Check div chars
        assert len(self.col_div) == 1
        assert len(self.row_div) == 1
        assert len(self.intersection_inner) == 1
        assert len(self.intersection_outer) == 1

    def add_row(self, row: list, idx: Optional[int] = None):
        assert self.num_cols == len(row)
        idx = idx or len(self.cells)
        self.cells.insert(idx, row)

    def remove_row(self, idx: Optional[int] = None):
        idx = idx or len(self.cells) - 1
        if idx >= 0 and idx < len(self.cells):
            self.cells.pop(idx)
        else:
            raise Exception(idx)

    def add_col(self, col: Col, cells: list):
        if len(self.cells) == 0:
            self.cells = [[c] for c in cells]
            self.cols.append(col)
        else:
            assert len(cells) == len(self.cells)
            self.cells = [old + [new] for old, new in zip(self.cells, cells)]
            self.cols.append(col)

    def remove_col(self, idx: Optional[int] = None):
        idx = idx or len(self.cols) - 1
        if idx >= 0 and idx < len(self.cols):
            self.cols.pop(idx)
            for row in self.cells:
                row.pop(idx)
        else:
            raise Exception(idx)

    def print(self, cb: Callable[[str, str, int | None], str] | None = None) -> str:
        """Stringify table

        Args:
            cb: Callable that accepts (row_text, row_type, row_index).
                Where row_type is one of
                    BORDER_OUTER_TOP
                    HEADER
                    BORDER_INNER
                    BODY
                    TRAILER
                    BORDER_INNER
                    BORDER_OUTER_BOTTOM
                Useful for conditioanlly surrounding each row with something

        Returns:
            _description_
        """
        cb = cb or (lambda text, type, data: text)

        # Calculations
        content_widths = [self.get_col_width(idx) for idx in range(self.num_cols)]

        # Stringify cells
        headers: list[str] = [
            col.pad(col.header, content_widths[idx])
            for idx, col in enumerate(self.cols)
        ]
        trailers: list[str] = [
            col.pad(col.trailer, content_widths[idx])
            for idx, col in enumerate(self.cols)
        ]
        cell_texts: list[list[str]] = []
        for row in self.cells:
            row_texts: list[str] = []
            for idx, (cell, col) in enumerate(zip(row, self.cols)):
                txt = col.stringify(cell)
                txt = col.pad(txt, content_widths[idx])
                row_texts.append(txt)
            cell_texts.append(row_texts)

        # Render rows
        table_rows: list[str] = []
        total_width = self.total_width
        itx_out = self.intersection_outer
        itx_in = self.intersection_inner

        # Outer border, top
        if self.draw_outer_borders:
            div = self.row_div * total_width
            div = itx_out + div[1:-1] + itx_out
            div = cb(div, "BORDER_OUTER_TOP", None)
            table_rows.append(div)

        # Column headers
        if self.draw_col_headers:
            header_row = self.col_div.join(headers)
            if self.draw_outer_borders:
                header_row = self.col_div + header_row + self.col_div
            header_row = cb(header_row, "HEADER", None)
            table_rows.append(header_row)

            div = ""
            for w, col in zip(content_widths, self.cols):
                div += self.row_div * (w + col.padding_left + col.padding_right)
                div += itx_in
            if self.draw_outer_borders:
                div = itx_out + div[:-1] + itx_out
            else:
                div = div[:-1]
            div = cb(div, "BORDER_INNER_BOTTOM", None)
            table_rows.append(div)

        # Content rows
        for idx, row in enumerate(cell_texts):
            text = self.col_div.join(row)
            if self.draw_outer_borders:
                text = self.col_div + text + self.col_div
            text = cb(text, "BODY", idx)
            table_rows.append(text)

        # Column trailers
        if self.draw_col_trailers:
            div = ""
            for w, col in zip(content_widths, self.cols):
                div += self.row_div * (w + col.padding_left + col.padding_right)
                div += itx_in
            if self.draw_outer_borders:
                div = itx_out + div[:-1] + itx_out
            else:
                div = div[:-1]
            div = cb(div, "BORDER_INNER_BOTTOM", None)
            table_rows.append(div)

            trailer_row = self.col_div.join(trailers)
            if self.draw_outer_borders:
                trailer_row = self.col_div + trailer_row + self.col_div
            trailer_row = cb(trailer_row, "TRAILER", None)
            table_rows.append(trailer_row)

        # Outer border, bottom
        if self.draw_outer_borders:
            div = self.row_div * total_width
            div = itx_out + div[1:-1] + itx_out
            div = cb(div, "BORDER_OUTER_BOTTOM", None)
            table_rows.append(div)

        result = "\n".join(table_rows)
        # assert len(result) == self.char_count
        return result

    @property
    def num_cols(self) -> int:
        return len(self.cols)

    def get_col(self, idx: int) -> list:
        cells = [row[idx] for row in self.cells]
        return cells

    def get_col_width(self, idx: int) -> int:
        """Column width excluding padding (ie length of longest string in column)"""

        title = self.cols[idx].header if self.cols else ""
        cells = [self.cols[idx].stringify(cell) for cell in self.get_col(idx)]
        lengths = [len(title)] + [len(c) for c in cells]
        result = max(lengths)
        return result

    @property
    def total_width(self) -> int:
        content_width = sum(self.get_col_width(idx) for idx in range(self.num_cols))
        padding_width = sum(col.padding_left + col.padding_right for col in self.cols)

        border_width = self.num_cols - 1
        if self.draw_outer_borders:
            border_width += 2

        return content_width + padding_width + border_width

    @property
    def total_height(self) -> int:
        height = len(self.cells)
        if self.draw_col_headers:
            height += 2
        if self.draw_col_trailers:
            height += 2
        if self.draw_outer_borders:
            height += 2
        return height

    @property
    def char_count(self) -> int:
        """(rows * cols) + (newline_chars)"""
        return self.total_width * self.total_height + (self.total_height - 1)
