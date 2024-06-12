#!/usr/bin/env python3

from curses import wrapper
import curses
import argparse
import pygit2
import re
from pygit2.enums import DiffOption
from pygit2.enums import ApplyLocation
from pygit2.enums import DiffStatsFormat
from pygit2.enums import DeltaStatus

def render_box(box, lines, pallete_map, lines_start_offset, cursor_position, lines_selected):
    # render diff lines inside the box starting with `lines_start_offset`
    lines_index = 0
    text_y = 1
    height, width = box.getmaxyx()
    height -= 2 # minus top and bottom border

    for line in lines:
        # now skip `lines_start_offset` lines
        if lines_index < lines_start_offset:
            lines_index += 1
            continue

        while len(line) < width - 5:
            line += " "

        if lines_selected[lines_index]:
            line = "* " + line
        else:
            line = "  " + line

        ci, bi = pallete_map[lines_index]
        pallete = curses.color_pair(ci + (2 if cursor_position == lines_index else 0)) | bi;

        box.addstr(text_y, 1, line, pallete)
        lines_index += 1
        text_y += 1

        if text_y > height:
            break

def gen_navigation_map(box, lines):
    # what is a navigation map? It is an array of tuples (lines_start_offset, position)
    out = []
    out_pallete = []
    header_mode = True
    lines_index = 0
    height, width = box.getmaxyx()
    height -= 3

    for line in lines:
        pallete = (24, curses.A_NORMAL)

        current_patch_header = re.search(r"@@\s*(\-*\+*[0-9]+),([0-9]+)\s+(\-*\+*[0-9]+),([0-9]+)\s*@@", line)
        if current_patch_header:
            header_mode = False
            pallete = (30, curses.A_BOLD)

        if header_mode:
            pallete = (24, curses.A_BOLD)

        if len(line)>=1 and (line[0] == '-' or line[0] == '+') and not header_mode:
            scroll_oft = lines_index - height if lines_index > height else 0
            out.append((scroll_oft, lines_index))
            pallete = (26 +  (1 if line[0] == '+' else 0), curses.A_BOLD)

        out_pallete.append(pallete)

        lines_index += 1
    return (out, out_pallete)


def generate_patch(lines, lines_selected): pass

def partially_select(stdscr, diffconfig):
    max_row = curses.LINES - 2
    box = curses.newwin( max_row + 2, curses.COLS, 0, 0 )
    box.box()

    # parse lines
    text_patch = diffconfig.patch.data.decode('utf-8')
    lines = text_patch.splitlines()
    lines_selected = []

    for line in lines:
        lines_selected.append(False)

    # now create a map of navigation
    nav_map, pallete_map = gen_navigation_map(box, lines)

    nav_map_index = 0
    scroll_offset = 0
    height, width = box.getmaxyx()
    height -= 4 # minus top and bottom border

    while True:
        # now draw the patches

        n1, n2 = nav_map[nav_map_index]
        render_box(box, lines, pallete_map, scroll_offset, n2, lines_selected)

        stdscr.refresh()
        box.refresh()

        key = stdscr.getch()
        if key == curses.KEY_F10 or key == 113:
            break

        if key == curses.KEY_DOWN:
            if nav_map_index + 1 < len(nav_map):
                nav_map_index += 1
                n1, n2 = nav_map[nav_map_index]
            elif scroll_offset + height + 2 < len(lines):
                scroll_offset += 1
            if n2 - scroll_offset > height:
                scroll_offset = n2 - height - 1

        if key == curses.KEY_UP:
            if nav_map_index > 0:
                nav_map_index -= 1
            elif scroll_offset > 0:
                scroll_offset -= 1
            if n2 - scroll_offset <= 0:
                n1, n2 = nav_map[nav_map_index]
                scroll_offset = n2

        if key == 32:
            lines_selected[n2] = not lines_selected[n2]
            generate_patch(lines, lines_selected)

    del box

def main(stdscr, sd):
    # Clear screen
    stdscr.clear()

    curses.noecho()
    curses.cbreak()
    curses.start_color()
    curses.curs_set( 0 )
    stdscr.keypad( 1 )

    curses.init_pair(DeltaStatus.MODIFIED, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(DeltaStatus.RENAMED, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(DeltaStatus.COPIED, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(DeltaStatus.DELETED, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(DeltaStatus.ADDED, curses.COLOR_GREEN, curses.COLOR_BLACK)

    curses.init_pair(DeltaStatus.MODIFIED + 12, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(DeltaStatus.RENAMED + 12, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(DeltaStatus.COPIED + 12, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(DeltaStatus.DELETED + 12, curses.COLOR_RED, curses.COLOR_BLUE)
    curses.init_pair(DeltaStatus.ADDED + 12, curses.COLOR_GREEN, curses.COLOR_BLUE)

    curses.init_pair(24, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(25, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(26, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(27, curses.COLOR_GREEN, curses.COLOR_BLACK)

    curses.init_pair(28, curses.COLOR_RED, curses.COLOR_BLUE)
    curses.init_pair(29, curses.COLOR_GREEN, curses.COLOR_BLUE)

    curses.init_pair(30, curses.COLOR_CYAN, curses.COLOR_BLACK)

    max_row = curses.LINES - 2

    box = curses.newwin( max_row + 2, curses.COLS, 0, 0 )
    box.box()

    box.addstr(1,1, "Please select changes you want to separate. Use space to mark patches to include to the step. Use [enter] to split the modification.")

    pos = 0
    cfg = []

    class DiffConfig:
        selected = False
        patch = None
        def __init__(self, p):
            self.patch = p

        def marking(self):
            return '+' if self.selected else ' '

        def select(self):
            self.selected = not self.selected

        def select_ex(self):
            if self.patch.delta.status != DeltaStatus.MODIFIED:
                return
            if self.patch.delta.is_binary:
                return

            partially_select(stdscr, self)


    while True:
        # draw menu
        start_oft = 3
        oft = start_oft

        for p in sd:
            if not oft - start_oft in cfg:
                cfg.append(DiffConfig(p))

            current_cfg = cfg[oft - start_oft]

            box.addstr(oft, 1, "[{}] {}".format(current_cfg.marking(), p.delta.new_file.path), curses.color_pair(p.delta.status + (12 if pos + start_oft == oft else 0)))
            oft = oft + 1


        stdscr.refresh()
        box.refresh()

        key = stdscr.getch()

        if key == curses.KEY_F10 or key == 113:
            break

        if key == curses.KEY_DOWN:
            if pos<len(sd)-1:
                pos += 1

        if key == curses.KEY_UP:
            if pos>0:
                pos -= 1

        if key == 32:
            cfg[pos].select()

        if key == 10:
            cfg[pos].select_ex()
            box.touchwin()

# parse command line options
parser = argparse.ArgumentParser(description='Git split-explain tool')
parser.add_argument('start commit', metavar='S', type=str, nargs=1,
                    help='start commit (end commit will be HEAD)')
parser.add_argument('-e', metavar='E', type=str,
                    help='end commits', default='HEAD')
parser.add_argument('-r', metavar='R', type=str, help='repository path', default='.')
args = parser.parse_args()

first_commit = getattr(args, 'start commit')[0]
last_commit = args.e
repo_path = args.r

# delete temp branch

repo = pygit2.Repository(repo_path)

try:
    repo.branches.delete("git-se/" + first_commit)
except:
    pass

last_commit_obj = repo.revparse_single(last_commit)

first_commit_obj = repo.revparse_single(first_commit)
repo.branches.local.create("git-se/" + first_commit, first_commit_obj)

d = repo.diff(first_commit_obj, last_commit_obj, flags=DiffOption.SHOW_BINARY)

repo.checkout("refs/heads/git-se/" + first_commit)
repo.apply(d, location=ApplyLocation.BOTH)

index = repo.index
author = pygit2.Signature('Git Se', 'gitse@gitse.se')
committer = pygit2.Signature('Git Se', 'gitse@gitse.se')
message = "Git Se auto generated commit"
tree = index.write_tree()
ref = repo.head.name
parents = [repo.head.target]
git_se_head = repo.create_commit(ref, author, committer, message, tree, parents)


sd = repo.diff(first_commit_obj, git_se_head, flags=DiffOption.SHOW_BINARY)

# now lets see what's in a diff
# sd = repo.diff(first_commit_obj, git_se_head, flags=DiffOption.SHOW_BINARY)
# for p in sd:
#     print("old file:", p.delta.old_file.path, "new file: ", p.delta.new_file.path, "is_binary: ", p.delta.is_binary, "nfiles:", p.delta.nfiles, "similarity:", p.delta.similarity, "status: ", p.delta.status)
#     print("-----------------")
#     print(p.data)
#     print("-----------------")
# 
# print(sd.stats.format(format= DiffStatsFormat.FULL | DiffStatsFormat.INCLUDE_SUMMARY, width=120))


wrapper(main, sd)

