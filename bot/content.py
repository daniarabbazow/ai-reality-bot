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


class Content:
    def __init__(self, categories: list[Category]):
        self.categories = categories
        self._by_id = {c.id: c for c in categories}

    def get_category(self, category_id: str) -> Optional[Category]:
        return self._by_id.get(category_id)

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

    seen_ids: set[str] = set()
    categories: list[Category] = []

    for cat_raw in raw.get("categories", []):
        cat_id = cat_raw.get("id")
        cat_title = cat_raw.get("title")
        if not cat_id or not cat_title:
            raise ContentError("У категории должны быть заполнены поля 'id' и 'title'")

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
                if item_id in seen_ids:
                    raise ContentError(f"Дублирующийся id элемента: {item_id!r}")
                seen_ids.add(item_id)

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
                        raise ContentError(f"[{item_id}] для type='photo' обязательно поле 'file'")
                    if text_value:
                        raise ContentError(f"[{item_id}] для type='photo' не должно быть поля 'text'")

                    file_path = BASE_DIR / file_rel
                    if not file_path.exists():
                        raise ContentError(f"[{item_id}] файл картинки не найден: {file_path}")
                else:  # text
                    if not text_value or not text_value.strip():
                        raise ContentError(
                            f"[{item_id}] для type='text' обязательно непустое поле 'text'"
                        )
                    if file_rel:
                        raise ContentError(f"[{item_id}] для type='text' не должно быть поля 'file'")

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

        categories.append(Category(id=cat_id, title=cat_title, levels=levels))

    if not categories:
        raise ContentError("В content.json нет ни одной категории")

    logger.info(
        "Контент загружен: категорий=%d, элементов=%d", len(categories), len(seen_ids)
    )
    return Content(categories=categories)
