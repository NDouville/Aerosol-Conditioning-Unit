# Note: This file was developed with the assistance of AI code generation tools.

import sys
import uselect


stdin_poll = uselect.poll()
stdin_poll.register(sys.stdin, uselect.POLLIN)


def read_command():
    if not stdin_poll.poll(10):
        return None
    return sys.stdin.readline().strip()
