from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class WhereBuilder:
    mode: Literal["OR", "AND"] = "AND"
    ignore_case: bool = True
    fragments: list["Condition | WhereBuilder"] = field(default_factory=list)

    def add(self, expr: str, data: Any = None):
        self.fragments.append(Condition(expr, data))

    def add_builder(self, builder: "WhereBuilder"):
        self.fragments.append(builder)

    def print(self, root=True) -> tuple[str, list[Any]]:
        if len(self.fragments) == 0:
            return ("", [])
        else:
            exprs: list[str] = []
            data: list = []

            for frag in self.fragments:
                if isinstance(frag, Condition):
                    ex = frag.expr
                    if self.ignore_case:
                        ex += " COLLATE NOCASE"
                    exprs.append(ex)

                    if frag.data is not None:
                        data.append(str(frag.data))
                elif isinstance(frag, WhereBuilder):
                    e, d = frag.print(root=False)
                    exprs.append(e)
                    data.extend(d)
                else:
                    raise Exception

            clause = "WHERE " if root else ""
            clause += f" {self.mode} ".join(exprs)
            if not root:
                clause = f"({clause})"

            result = (clause, data)
            return result


@dataclass
class Condition:
    expr: str
    data: Any = None
