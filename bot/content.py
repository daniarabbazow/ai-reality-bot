import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


class ContentError(Exception):
    pass


@dataclass
class Item:
    id: str
    type: str  # "photo" | "text"
    answer: str
    note: str
    file: Optional[str] = None
    text: Optional[str] = None


@dataclass
class Level:
    level: int
    title: str
    items: list[Item]


@dataclass
class Category:
    id: str
    title: str
    levels: list[Level]
    item_label: Optional[str] = None
    show_answers_at_end: bool = False


@dataclass
class ContentType:
    id: str
    title: str
    categories: list[Category]


class Content:
    def __init__(self, types: list[ContentType]):
        self.types = types
        self._types_by_id = {t.id: t for t in types}
        self._categories_by_id: dict[str, Category] = {}
        self._category_type_id: dict[str, str] = {}
        for t in types:
            for category in t.categories:
                self._categories_by_id[category.id] = category
                self._category_type_id[category.id] = t.id

    def get_type(self, type_id: str) -> Optional[ContentType]:
        return self._types_by_id.get(type_id)

    def get_category(self, category_id: str) -> Optional[Category]:
        return self._categories_by_id.get(category_id)

    def get_type_id_for_category(self, category_id: str) -> Optional[str]:
        return self._category_type_id.get(category_id)

    def all_categories(self) -> list[Category]:
        return list(self._categories_by_id.values())

    def get_level(self, category_id: str, level: int) -> Optional[Level]:
        category = self.get_category(category_id)
        if category is None:
            return None
        for lvl in category.levels:
            if lvl.level == level:
                return lvl
        return None

    def get_next_level(self, category_id: str, level: int) -> Optional[Level]:
        category = self.get_category(category_id)
        if category is None:
            return None
        levels = sorted(category.levels, key=lambda l: l.level)
        for i, lvl in enumerate(levels):
            if lvl.level == level and i + 1 < len(levels):
                return levels[i + 1]
        return None

    def is_last_level(self, category_id: str, level: int) -> bool:
        return self.get_next_level(category_id, level) is None


def load_content(path: Optional[Path] = None) -> Content:
    path = path or (BASE_DIR / "content.json")
    if not path.exists():
        raise ContentError(f"Файл контента не найден: {path}")

    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    seen_item_ids: set[str] = set()
    seen_category_ids: set[str] = set()
    seen_type_ids: set[str] = set()
    types: list[ContentType] = []

    for type_raw in raw.get("types", []):
        type_id = type_raw.get("id")
        type_title = type_raw.get("title")
        if not type_id or not type_title:
            raise ContentError("У типа должны быть заполнены поля 'id' и 'title'")
        if type_id in seen_type_ids:
            raise ContentError(f"Дублирующийся id типа: {type_id!r}")
        seen_type_ids.add(type_id)

        categories: list[Category] = []
        for cat_raw in type_raw.get("categories", []):
            cat_id = cat_raw.get("id")
            cat_title = cat_raw.get("title")
            if not cat_id or not cat_title:
                raise ContentError(
                    f"[{type_id}] У категории должны быть заполнены поля 'id' и 'title'"
                )
            if cat_id in seen_category_ids:
                raise ContentError(f"Дублирующийся id категории: {cat_id!r}")
            seen_category_ids.add(cat_id)

            item_label = cat_raw.get("item_label")
            if item_label is not None and (
                not isinstance(item_label, str) or not item_label.strip()
            ):
                raise ContentError(f"[{cat_id}] 'item_label' должен быть непустой строкой")

            show_answers_at_end = cat_raw.get("show_answers_at_end", False)
            if not isinstance(show_answers_at_end, bool):
                raise ContentError(f"[{cat_id}] 'show_answers_at_end' должен быть true/false")

            levels: list[Level] = []
            for lvl_raw in sorted(cat_raw.get("levels", []), key=lambda l: l.get("level", 0)):
                lvl_num = lvl_raw.get("level")
                lvl_title = lvl_raw.get("title")
                if lvl_num is None or not lvl_title:
                    raise ContentError(
                        f"[{cat_id}] У уровня должны быть заполнены поля 'level' и 'title'"
                    )

                items: list[Item] = []
                for item_raw in lvl_raw.get("items", []):
                    item_id = item_raw.get("id")
                    item_type = item_raw.get("type", "photo")
                    file_rel = item_raw.get("file")
                    text_value = item_raw.get("text")
                    answer = item_raw.get("answer")
                    note = item_raw.get("note", "")

                    if not item_id:
                        raise ContentError(f"[{cat_id}/{lvl_num}] У элемента отсутствует 'id'")
                    if item_id in seen_item_ids:
                        raise ContentError(f"Дублирующийся id элемента: {item_id!r}")
                    seen_item_ids.add(item_id)

                    if item_type not in ("photo", "text"):
                        raise ContentError(
                            f"[{item_id}] 'type' должен быть 'photo' или 'text', получено: {item_type!r}"
                        )

                    if answer not in ("real", "ai"):
                        raise ContentError(
                            f"[{item_id}] 'answer' должен быть 'real' или 'ai', получено: {answer!r}"
                        )

                    if item_type == "photo":
                        if not file_rel:
                            raise ContentError(
                                f"[{item_id}] для type='photo' обязательно поле 'file'"
                            )
                        if text_value:
                            raise ContentError(
                                f"[{item_id}] для type='photo' не должно быть поля 'text'"
                            )

                        file_path = BASE_DIR / file_rel
                        if not file_path.exists():
                            raise ContentError(f"[{item_id}] файл картинки не найден: {file_path}")
                    else:  # text
                        if not text_value or not text_value.strip():
                            raise ContentError(
                                f"[{item_id}] для type='text' обязательно непустое поле 'text'"
                            )
                        if file_rel:
                            raise ContentError(
                                f"[{item_id}] для type='text' не должно быть поля 'file'"
                            )

                    items.append(
                        Item(
                            id=item_id,
                            type=item_type,
                            answer=answer,
                            note=note,
                            file=file_rel,
                            text=text_value,
                        )
                    )

                if not items:
                    raise ContentError(f"[{cat_id}/{lvl_num}] в уровне нет элементов")

                levels.append(Level(level=lvl_num, title=lvl_title, items=items))

            if not levels:
                raise ContentError(f"[{cat_id}] в категории нет уровней")

            categories.append(
                Category(
                    id=cat_id,
                    title=cat_title,
                    levels=levels,
                    item_label=item_label,
                    show_answers_at_end=show_answers_at_end,
                )
            )

        if not categories:
            raise ContentError(f"[{type_id}] в типе нет категорий")

        types.append(ContentType(id=type_id, title=type_title, categories=categories))

    if not types:
        raise ContentError("В content.json нет ни одного типа")

    logger.info(
        "Контент загружен: типов=%d, категорий=%d, элементов=%d",
        len(types),
        len(seen_category_ids),
        len(seen_item_ids),
    )
    return Content(types=types)
