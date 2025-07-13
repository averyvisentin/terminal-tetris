#!/bin/bash
kitty -T "Terminal Tetris" \
    -o initial_window_width=640 \
    -o initial_window_height=800 \
    -e python3 terminal-tetris.py


#   Just a simple wrapper to launch in kitty terminal
#   I'll refine later for other terminals
#   I need to figure out why my TERM env is xterm-kitty first
#   HAHA
#
