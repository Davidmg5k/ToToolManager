from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True, slots=True)
class Include:
    """Wrapper to include specific methods.

    Precondition: include is a sequence of method names
    Postcondition: stores the list of included methods
    """
    include: Sequence[str]

    def __iter__(self):
        return iter(self.include)

    def __len__(self):
        return len(self.include)


@dataclass(frozen=True, slots=True)
class Exclude:
    """Wrapper to exclude specific methods.

    Precondition: exclude is a sequence of method names
    Postcondition: stores the list of excluded methods
    """
    exclude: Sequence[str]

    def __iter__(self):
        return iter(self.exclude)

    def __len__(self):
        return len(self.exclude)