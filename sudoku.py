from enum import Enum
import itertools
import os
import time
from typing import Iterator
import click
import colorama
import cursor
import sys

def tick(dur: float = 0.5) -> None:
    time.sleep(dur)


class Stopwatch:
    start: int
    end: int

    def get_elapsed(self) -> int:
        return time.time() - self.start

    def __enter__(self) -> "Stopwatch":
        self.start = time.time()
        return self

    def __exit__(self, *args) -> None:
        pass


class BaseColor:
    black = 30
    red = 31
    green = 32
    yellow = 33
    blue = 34
    purple = 35
    cyan = 36
    white = 37

    reset = "\033[0m"

    _colors = ["black", "red", "green", "yellow", "blue", "purple", "cyan", "white"]

    format: lambda code: code

    def __init_subclass__(cls) -> None:
        for key in BaseColor._colors:
            code = getattr(BaseColor, key)
            setattr(cls, key, cls.format(code))

    @classmethod
    def swatch(cls):
        for key in cls._colors:
            color = getattr(cls, key)
            print(f"{color}{key}{cls.reset}", end=" ")
        print()


class Color(BaseColor):
    format = lambda code: f"\033[0;{code}m"


class Background(BaseColor):
    format = lambda code: f"\033[{code + 10}m"


class Cell:

    NONE = 0
    MAX = 9
    POSSIBLE_VALUES = {1, 2, 3, 4, 5, 6, 7, 8, 9}

    locked: bool
    mutated: bool
    show_empty: bool

    value: int
    incoming: int
    color: str
    options_iter: Iterator[int]
    options: list[int]

    def __init__(self, value: int = NONE) -> None:
        if value and value != Cell.NONE:
            self.value = value
            self.locked = True
        else:
            self.locked = False
            self.value = Cell.NONE

        self.show_empty = True
        self.mutated = False

        self.incoming = Cell.NONE
        self.color = ""
        self.options = []
        self.options_iter = iter(self.options)

    def __str__(self) -> str:
        return str(self.get_value())

    def __repr__(self) -> str:
        return str(self.get_value())

    def lock(self):
        self.locked = True

    def set_incoming(self, incoming: int) -> None:
        self.incoming = incoming
        self.mutated = True

    def set_color(self, color: str) -> None:
        self.color = color

    def set_options(self, options: list[int]) -> None:
        self.options_iter = iter(options)
        self.options = options

    def is_locked(self) -> bool:
        return self.locked

    def is_empty(self) -> bool:
        return (self.incoming if self.is_mutated() else self.value) == Cell.NONE

    def is_mutated(self) -> bool:
        return self.mutated

    def commit(self) -> None:
        self.value = self.incoming
        self.mutated = False

    def rollback(self) -> None:
        self.mutated = False

    def reset(self) -> None:
        self.value = Cell.NONE
        self.incoming = Cell.NONE
        self.options_iter = iter(self.options)

    def increment(self) -> bool:
        value = next(self.get_options(), None)
        if not value:
            return False

        self.set_incoming(value)
        return True

    def get_value(self) -> int:
        return self.incoming if self.is_mutated() else self.value

    def get_incoming(self) -> int:
        return self.incoming

    def get_options(self) -> Iterator[int]:
        return self.options_iter

    def render(self, selected: bool = False) -> str:
        def symbol():
            if self.is_empty():
                if self.show_empty:
                    return "."
                return " "
            return str(self.get_value())

        def color():
            if self.color:
                temp = self.color
                self.color = None
                return temp
            if selected:
                return Color.red
            if self.is_mutated():
                return Color.yellow
            if self.is_locked():
                return Color.cyan
            if self.is_empty():
                return Color.white

            return Color.green

        return f"{color()}{symbol()}{BaseColor.reset}"


class Board:
    class CollectionMode(Enum):
        ROW = 0
        COLUMN = 1
        GROUP = 2

    class SolveResult(Enum):
        EXHAUSTED = 0
        INVALID = 1
        SUCCESS = 2
        LOCKED = 3

    class SolveException(Exception):
        result: "Board.SolveResult"

        def __init__(self, result: "Board.SolveResult") -> None:
            self.result = result

    MAX_COL_INDEX = 8
    MAX_ROW_INDEX = 8
    MIN_COL_INDEX = 0
    MIN_ROW_INDEX = 0
    GROUP_SIZE = 3
    ANIMATION_DELAY = 0

    cells: list[list[Cell]]

    row: int
    col: int
    
    animate: bool
    tick: float

    def __init__(self, starting_state: list[list[int]] | None = None, animate: bool = False, tick: float = 0):
        self.animate = animate
        self.tick = tick
        self.row = 0
        self.col = 0
        self.cells = []
        if starting_state:
            for rindex in range(Board.MAX_ROW_INDEX + 1):
                self.cells.append(
                    [
                        Cell(value=starting_state[rindex][cindex])
                        for cindex in range(Board.MAX_COL_INDEX + 1)
                    ]
                )
        else:
            for _ in range(Board.MAX_ROW_INDEX + 1):
                self.cells.append([Cell() for _ in range(Board.MAX_COL_INDEX + 1)])

        self.preflight()

    def populate_cell_options(self, depth=0):
        need_to_rerun = False
        for rindex in range(Board.MAX_ROW_INDEX + 1):
            for cindex in range(Board.MAX_COL_INDEX + 1):
                cell: Cell = self.cells[rindex][cindex]
                if cell.is_locked():
                    continue

                collections = self.get_all_collections(rindex=rindex, cindex=cindex)

                used_options = {
                    cell.value
                    for cell in itertools.chain(*collections)
                    if cell.value != Cell.NONE
                }
                remainig_options = list(Cell.POSSIBLE_VALUES - used_options)

                if not remainig_options:
                    raise ValueError(
                        f"Detected unsolvable puzzle, no options for cell@({rindex}, {cindex})"
                    )

                if len(remainig_options) == 1:
                    cell.set_incoming(remainig_options[0])
                    cell.commit()
                    cell.lock()
                    need_to_rerun = True
                else:
                    cell.set_options(options=remainig_options)
        if need_to_rerun:
            self.populate_cell_options(depth=depth + 1)

    def preflight(self) -> None:
        self.populate_cell_options()

    def next(self) -> bool:
        def go_forward():
            if self.col == Board.MAX_COL_INDEX:
                if self.row + 1 > Board.MAX_ROW_INDEX:
                    return False

                self.row += 1
                self.col = Board.MIN_COL_INDEX
            else:
                self.col += 1

            return True

        if not go_forward():
            return False
        while self.cells[self.row][self.col].is_locked():
            if not go_forward():
                return False

        return True

    def prev(self) -> bool:
        def go_back():
            if self.col == Board.MIN_COL_INDEX:
                if self.row - 1 < Board.MIN_ROW_INDEX:
                    return False
                self.row -= 1
                self.col = Board.MAX_COL_INDEX
            else:
                self.col -= 1

            return True

        self.cells[self.row][self.col].reset()
        if not go_back():
            return False
        while self.cells[self.row][self.col].is_locked():
            if not go_back():
                return False

        return True

    def collect(self, mode: CollectionMode, rindex: int, cindex: int) -> list[Cell]:
        def group_range(n: int) -> int:
            base = (n // Board.GROUP_SIZE) * Board.GROUP_SIZE
            return range(base, base + Board.GROUP_SIZE)

        match mode:
            case Board.CollectionMode.ROW:
                return self.cells[rindex]
            case Board.CollectionMode.COLUMN:
                return [row[cindex] for row in self.cells]
            case Board.CollectionMode.GROUP:
                res = []
                for row in group_range(rindex):
                    for col in group_range(cindex):
                        res.append(self.cells[row][col])

                return res

    def get_all_collections(self, rindex: int, cindex: int) -> list[list[Cell]]:
        return [
            self.collect(mode=mode, rindex=rindex, cindex=cindex)
            for mode in Board.CollectionMode
        ]

    def validate_collection(self, collection: list[Cell]) -> bool:
        seen = set()
        for cell in collection:
            if not cell.is_empty():
                value = cell.get_value()
                if value in seen:
                    return False

                seen.add(value)
        return True

    def validate(self, row: int | None = None, col: int | None = None) -> bool:
        row = row or self.row
        col = col or self.col
        return all(
            self.validate_collection(collection=collection)
            for collection in self.get_all_collections(row, col)
        )

    def is_win(self) -> bool:
        for rindex in range(Board.MAX_ROW_INDEX + 1):
            for cindex in range(Board.MAX_COL_INDEX + 1):
                if not self.validate(rindex, cindex):
                    return False

        for row in self.cells:
            for cell in row:
                if cell.is_empty():
                    return False

        return True

    def flash(self, color) -> None:
        self.cells[self.row][self.col].set_color(color)
        self.render()
        tick(self.tick)

    def solve(self) -> SolveResult:
        cell: Cell = self.cells[self.row][self.col]
        try:
            if cell.is_locked():
                raise Board.SolveException(Board.SolveResult.LOCKED)
            if not cell.increment():
                raise Board.SolveException(Board.SolveResult.EXHAUSTED)
            if self.animate:
                self.render()
                tick(self.tick)
            # validate new state
            if not self.validate():
                if self.animate:
                    self.flash(Color.red)
                raise Board.SolveException(Board.SolveResult.INVALID)

            # commit state
            cell.commit()

            return Board.SolveResult.SUCCESS
        except Board.SolveException as solve_exception:
            cell.rollback()
            return solve_exception.result

    def move(self, y, x):
        print(f"\033[{y};{x}H", end="")

    def render(self) -> str:
        buffer = ""
        self.move(0, 0)

        for row_index, row in enumerate(self.cells):
            for col_index, cell in enumerate(row):
                if row_index == self.row and col_index == self.col:
                    # selected cell
                    buffer += cell.render(selected=False)
                else:
                    buffer += cell.render()

                if col_index != Board.MAX_COL_INDEX:
                    buffer += " "

            if row_index != Board.MAX_ROW_INDEX:
                buffer += "\n"
        print(buffer, flush=True, end="")


class Solver:
    board: Board
    
    animate: bool
    tick: float
    
    def __init__(self, path: str | None, animate: bool = False, tick: float = 0):
        self.animate = animate
        self.tick = tick
        if path:
            with open(path, "r", encoding="UTF-8") as file:
                lines = file.readlines()

                if len(lines) != Board.MAX_ROW_INDEX + 1:
                    raise ValueError("Incorrect number of rows in provided file")

                state = []
                for line in lines:
                    line = line.strip()
                    if len(line) != (Board.MAX_COL_INDEX + 1):
                        raise ValueError(
                            f"Incorrect number of columns in at least one row in provided file: {len(line)}"
                        )
                    state.append([int(col) for col in line])

            self.board = Board(starting_state=state, animate=animate, tick=tick)
        else:
            self.board = Board(animate=animate, tick=tick)

    def render(self):
        self.board.render()

    def handle(self, result: Board.SolveResult) -> bool:
        if self.animate:
            self.render()
        match result:
            case Board.SolveResult.SUCCESS | Board.SolveResult.LOCKED:
                return self.board.next()
            case Board.SolveResult.EXHAUSTED:
                return self.board.prev()
            case Board.SolveResult.INVALID:
                return self.handle(self.board.solve())

    def solve(self):
        self.render()
        tick(self.tick)
        if self.board.is_win():
            self.board.render()
        with Stopwatch() as stopwatch:
            while self.handle(self.board.solve()):
                if self.animate:
                    tick(self.tick)
                    print(f"\n{stopwatch.get_elapsed():02.2f} Seconds ")

            self.render()
            print(f"\n{stopwatch.get_elapsed():0f} Seconds ")
            if not self.board.is_win():
                exit(1)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


@click.command()
@click.option("-a", "--animate", is_flag=True, default=False, type=bool, help="To animate, or not to animate. If yes, extra frames are renders and printed to the terminal.")
@click.option("-t", "--tick", "_tick", default=0, type=float, help="The amount of time, in seconds, that application will hold after printing a frame.")
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
def run(animate: bool, _tick: float, paths: tuple[str]):
    """Solve every puzzle in PATHS; if none are provided, solve an empty puzzle"""
    try:
        colorama.init()
        cursor.hide()
        clear()

        if paths:
            for path in paths:
                solver = Solver(animate=animate, path=path, tick=_tick)
                solver.solve()
                tick(_tick)
        else:
            solver = Solver(animate=animate, path=None, tick=_tick)
            solver.solve()
    except:
        raise
    finally:
        cursor.show()

if __name__ == "__main__":
    run()