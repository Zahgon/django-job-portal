"""Paging for the rendered pages.

The page object the templates read keeps the same attribute names the previous
template layer gave them, so the pagination markup needed no rewriting.
"""
from __future__ import annotations

from starlette.exceptions import HTTPException


class Page:
    """One page of a list, with the links the markup asks it for."""

    def __init__(self, paginator: "Paginator", number: int, rows: list):
        self.paginator = paginator
        self.number = number
        self.object_list = rows

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self) -> int:
        return len(self.object_list)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.paginator.num_pages

    @property
    def previous_page_number(self) -> int:
        return self.number - 1

    @property
    def next_page_number(self) -> int:
        return self.number + 1


class Paginator:
    """Splits a list into fixed-size pages, counting from one."""

    def __init__(self, rows: list, per_page: int):
        self.rows = rows
        self.per_page = per_page
        self.count = len(rows)
        self.num_pages = max(1, -(-self.count // per_page))

    @property
    def page_range(self):
        return range(1, self.num_pages + 1)

    def page(self, number: int) -> Page:
        start = (number - 1) * self.per_page
        return Page(self, number, self.rows[start:start + self.per_page])


def paginate(rows: list, per_page: int, raw_number) -> tuple[Page, Paginator, bool]:
    """Page a list, answering 404 for a page number that is not there."""
    paginator = Paginator(rows, per_page)
    try:
        number = int(raw_number) if raw_number not in (None, "") else 1
    except (TypeError, ValueError):
        raise HTTPException(status_code=404) from None
    if number < 1 or number > paginator.num_pages:
        raise HTTPException(status_code=404)
    return paginator.page(number), paginator, paginator.num_pages > 1
