from collections import deque
from typing import Generic, Iterator, Optional, Sequence, TypeVar

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

    def clear(self) -> None:
        self._data.clear()
