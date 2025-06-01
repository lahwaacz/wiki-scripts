import copy
import logging
from typing import TYPE_CHECKING, Generator, Iterable, Iterator, Self

import ws.ArchWiki.lang as lang
from ws.client.api import API

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT

logger = logging.getLogger(__name__)

__all__ = ["CategoryGraph"]


# TODO: refactoring: move the generic stuff to ws.utils and add tests


def cmp[T: SupportsDunderLT](left: T, right: T) -> int:
    if left < right:
        return -1
    elif right < left:
        return 1
    else:
        return 0


class MyIterator[T](Iterator[T]):
    """
    Wrapper around python generators that allows to explicitly check if the
    generator has been exhausted or not.
    """

    def __init__(self, iterable: Iterable[T]):
        self._iterator = iter(iterable)
        self._exhausted = False
        self._next_item: T | None = None
        self._cache_next_item()

    def _cache_next_item(self):
        try:
            self._next_item = next(self._iterator)
        except StopIteration:
            self._exhausted = True

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> T | None:  # type: ignore[override]
        if self._exhausted:
            return None
        # FIXME: workaround for strange behaviour of lists inside tuples -> investigate
        next_item = copy.deepcopy(self._next_item)
        self._cache_next_item()
        return next_item

    def __bool__(self) -> bool:
        return not self._exhausted


class CategoryGraph:

    def __init__(self, api: API):
        self.api = api

        # `parents` maps category names to the list of their parents
        self.parents: dict[str, list[str]] = {}
        # `subcats` maps category names to the list of their subcategories
        self.subcats: dict[str, list[str]] = {}
        # a mapping of category names to the corresponding "categoryinfo" dictionary
        self.info: dict[str, dict] = {}

        self.update()

    def update(self) -> None:
        self.parents.clear()
        self.subcats.clear()
        self.info.clear()

        for page in self.api.generator(
            generator="allpages",
            gaplimit="max",
            gapnamespace=14,
            prop="categories|categoryinfo",
            cllimit="max",
            clshow="!hidden",
            clprop="hidden",
        ):
            if "categories" in page:
                self.parents.setdefault(page["title"], []).extend(
                    [cat["title"] for cat in page["categories"]]
                )
                for cat in page["categories"]:
                    self.subcats.setdefault(cat["title"], []).append(page["title"])
            # empty categories don't have the "categoryinfo" field
            i = self.info.setdefault(
                page["title"], {"files": 0, "pages": 0, "subcats": 0, "size": 0}
            )
            if "categoryinfo" in page:
                i.update(page["categoryinfo"])

    @staticmethod
    def walk(
        graph: dict[str, list[str]],
        node: str,
        levels: list[int] | None = None,
        visited: set[str] | None = None,
    ) -> Generator[tuple[str, str, list[int]]]:
        if levels is None:
            levels = []
        if visited is None:
            visited = set()
        children = graph.get(node, [])
        for i, child in enumerate(sorted(children, key=str.lower)):
            if child not in visited:
                levels.append(i)
                visited.add(child)
                yield child, node, levels
                yield from CategoryGraph.walk(graph, child, levels, visited)
                visited.remove(child)
                levels.pop(-1)

    @staticmethod
    def compare_components(
        graph: dict[str, list[str]], left: str, right: str
    ) -> Generator[
        tuple[tuple[str, str, list[int]] | None, tuple[str, str, list[int]] | None]
    ]:
        def cmp_tuples(left: tuple | None, right: tuple | None) -> int:
            if left is None and right is None:
                return 0
            elif left is None:
                return 1
            elif right is None:
                return -1
            return cmp(
                (-len(left[2]), lang.detect_language(left[0])[0]),
                (-len(right[2]), lang.detect_language(right[0])[0]),
            )

        lgen = MyIterator(CategoryGraph.walk(graph, left))
        rgen = MyIterator(CategoryGraph.walk(graph, right))

        try:
            lval = next(lgen)
            rval = next(rgen)
        except StopIteration:
            # both empty, there is nothing to do
            return

        while lgen and rgen:
            while cmp_tuples(lval, rval) < 0:
                yield lval, None
                lval = next(lgen)
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = next(lgen)
                rval = next(rgen)
                # avoid infinite loop if both generators get to the end in the inner loop
                if lval is None and rval is None:
                    break
            while cmp_tuples(lval, rval) > 0:
                yield None, rval
                rval = next(rgen)

        while lgen:
            while cmp_tuples(lval, rval) < 0:
                yield lval, None
                lval = next(lgen)
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = next(lgen)
                rval = None

        while rgen:
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = None
                rval = next(rgen)
            while cmp_tuples(lval, rval) > 0:
                yield None, rval
                rval = next(rgen)

        yield lval, rval

    def create_category(self, category: str) -> None:
        title = self.api.Title(category)
        if title.iwprefix or title.namespace != "Category":
            raise ValueError(f"Invalid category name: [[{category}]]")
        # normalize name
        category = title.fullpagename

        # skip existing categories
        if category in self.info:
            return

        pure, langname = lang.detect_language(category)
        if langname == lang.get_local_language():
            logger.warning(
                f"Cannot automatically create {lang.get_local_language()} category: [[{category}]]"
            )
            return

        local = lang.format_title(pure, lang.get_local_language())
        if local not in self.info:
            logger.warning(
                f"Cannot create category [[{category}]]: {lang.get_local_language()} category [[{local}]] does not exist."
            )
            return

        def localized_category(cat: str, langname: str) -> str:
            pure, lgn = lang.detect_language(cat)
            if pure == "Category:Languages":
                # this terminates the recursive creation
                return pure
            elif pure.lower() == "category:" + lgn.lower():
                return f"Category:{langname}"
            return lang.format_title(pure, langname)

        if local in self.parents.keys():
            parents = [localized_category(p, langname) for p in self.parents[local]]
            content = "\n".join(f"[[{p}]]" for p in parents)
        else:
            parents = None
            content = ""

        self.api.create(title=category, text=content, summary="init wanted category")
        self.update()

        if parents is not None:
            for p in parents:
                self.create_category(p)

    def init_wanted_categories(self) -> None:
        for page in self.api.list(
            list="querypage", qppage="Wantedcategories", qplimit="max"
        ):
            self.create_category(page["title"])
