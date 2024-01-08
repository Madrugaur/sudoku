// Constants

const BOARD_WIDTH = 9;
const BOARD_HEIGHT = 9;
const SQUARE_WIDTH = 3;
const SQUARE_HEIGHT = 3;

// Cell Selection Stuff

let _selected_cells = [];

function set_selected_cell(elm) {
  if (_selected_cells.length == 1 && _selected_cells[0] == elm) {
    _selected_cells = []
  } else {
    for (let other of _selected_cells) {
      other.toggle_class("highlight");
    }
    _selected_cells = [elm];
  }

  elm.toggle_class("highlight");
}

function unset_selected_cell() {
  if (_selected_cells == []) return;
  _selected_cells[0].toggle_class('highlight')
  _selected_cells = []
}

function add_selected_cell(elm) {
  _selected_cells.push(elm);
}

function remove_selected_cell(elm) {
  _selected_cells = _selected_cells.filter((i) => i != elm);
}

function toggle_selected_cell(elm) {
  if (_selected_cells.find((i) => i == elm)) {
    remove_selected_cell(elm);
  } else {
    add_selected_cell(elm);
  }

  elm.toggle_class("highlight");
}

function selected_set_content(digit) {
  _selected_cells.forEach((elm) => elm.set_content(elm, digit))
}

// JQuery Knockoff

function $(id) {
  return $wrap(document.getElementById(id));
}

function $new(
  tagName,
  className = "none",
  id = undefined,
  _onclick = undefined,
  extra={}
) {
  const elm = document.createElement(tagName);
  elm.className = className;
  if (id) elm.id = id;
  if (_onclick) elm.onclick = _onclick;
  for (let key of Object.keys(extra)) {
    elm[key] = extra[key]
  }
  return $wrap(elm);
}

function $wrap(elm) {
  elm.toggle_class = (className) => {
    if (elm.classList.contains(className)) {
      elm.classList.remove(className);
    } else {
      elm.classList.add(className);
    }
  };

  return elm;
}

function generate_board() {
  function cell(cell_id) {
    function cell_selection(event) {
      event.preventDefault();
      if (event.shiftKey) {
        toggle_selected_cell(event.target);
      } else {
        set_selected_cell(event.target);
      }
    }
    return $new(
      "div",
      (className = "board-cell noselect"),
      (id = `board-cell-${cell_id}`),
      (_onclick = cell_selection),
      (extra={
        set_content: (self, digit) => {
          if (self.content == digit) {
            self.content = undefined
            self.classList.remove('large-content')
            self.innerText = ""
          } else {
            self.content = digit;
            self.innerText = digit
            self.classList.add('large-content')
          }
        } 
      })
    );
  }

  function row(row_id) {
    return $new(
      "div",
      (className = "board-row"),
      (id = `board-row-${row_id}`),
      (onclick = undefined)
    );
  }

  const root_node = $("board-container");

  for (let row_index = 0; row_index < BOARD_HEIGHT; row_index++) {
    const row_node = row(row_index);
    for (let col_index = 0; col_index < BOARD_WIDTH; col_index++) {
      row_node.appendChild(cell(row_index * BOARD_WIDTH + col_index));
      if ((col_index + 1) % SQUARE_WIDTH == 0 && col_index + 1 != BOARD_WIDTH) {
        row_node.appendChild($new("div", (className = "square-vert-div")));
      }
    }
    root_node.appendChild(row_node);
    if ((row_index + 1) % SQUARE_HEIGHT == 0 && row_index + 1 != BOARD_HEIGHT) {
      root_node.appendChild($new("div", (className = "square-horz-div")));
    }
  }
  console.log(root_node);
}

function generate_event_listners() {
  window.addEventListener("keypress", (event) => {
    if (isFinite(event.key)) {
      selected_set_content(Number(event.key))
    }
  })
}

function main() {
  console.log("hello World");
  generate_board();
  generate_event_listners();
}

main();
