from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True, slots=True)
class Include:
    """Wrapper para incluir métodos específicos.

    Precondición: include es una secuencia de nombres de métodos
    Postcondición: almacena la lista de métodos incluidos
    """
    include: Sequence[str]

    def __iter__(self):
        return iter(self.include)

    def __len__(self):
        return len(self.include)


@dataclass(frozen=True, slots=True)
class Exclude:
    """Wrapper para excluir métodos específicos.

    Precondición: exclude es una secuencia de nombres de métodos
    Postcondición: almacena la lista de métodos excluidos
    """
    exclude: Sequence[str]

    def __iter__(self):
        return iter(self.exclude)

    def __len__(self):
        return len(self.exclude)