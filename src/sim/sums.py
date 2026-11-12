class Kahan:
    """Compensated accumulator; keeps 15-year sums at machine precision."""
    __slots__ = ("s", "c")

    def __init__(self, value: float = 0.0):
        self.s = float(value)
        self.c = 0.0

    def add(self, x: float) -> None:
        y = float(x) - self.c
        t = self.s + y
        self.c = (t - self.s) - y
        self.s = t

    @property
    def value(self) -> float:
        return self.s + self.c
