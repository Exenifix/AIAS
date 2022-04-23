from collections import deque
from typing import Generic, Iterator, Optional, Sequence, TypeVar

from disnake import Member

T = TypeVar("T")


class Queue(Generic[T]):
    def __init__(
        self,
        initial_values: Optional[Sequence[T]] = None,
        max_size: Optional[int] = None,
    ):
        if initial_values is None:
            self._data = deque()
        else:
            self._data = deque(initial_values)

        self.max_size = max_size

    def __str__(self):
        val = '"' + '", "'.join(map(str, self._data)) + '"'
        return f"Queue([{val}])"

    def __len__(self):
        return len(self._data)

    def __iter__(self) -> Iterator[T]:
        return iter(self._data)

    def add(self, value: T) -> None:
        self._data.append(value)

        if self.max_size is not None and len(self._data) > self.max_size:
            self._data.popleft()

    def pop(self) -> T:
        return self._data.popleft()

    def remove(self, value: T) -> None:
        self._data.remove(value)

    def clear(self) -> None:
        self._data.clear()

    def copy(self) -> "Queue[T]":
        return self._data.copy()


async def try_send(member: Member, content: Optional[str] = None, **kwargs):
    try:
        await member.send(content, **kwargs)
    except:
        pass


def split_text(text: str, symbols_per_string: Optional[int] = 100) -> list[str]:
    new_texts = []
    text_length = len(text)
    for i in range(0, text_length, symbols_per_string):
        new_texts.append(text[i : i + symbols_per_string])

    return new_texts


def sorted_dict(d: dict) -> dict:
    keys = sorted(d.keys())
    return {k: d[k] for k in keys}
