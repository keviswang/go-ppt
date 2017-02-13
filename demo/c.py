import atexit
import datetime
import os
import sys
import time
import curses

import psutil


# --- curses stuff

def tear_down():
    win.keypad(0)
    curses.nocbreak()
    curses.echo()
    curses.endwin()


win = curses.initscr()
atexit.register(tear_down)
curses.endwin()
lineno = 0


def print_line(line, highlight=False):
    """A thin wrapper around curses's addstr()."""
    global lineno
    try:
        if highlight:
            line += " " * (win.getmaxyx()[1] - len(line))
            win.addstr(lineno, 0, line, curses.A_REVERSE)
        else:
            win.addstr(lineno, 0, line, 0)
    except curses.error:
        lineno = 0
        win.refresh()
        raise
    else:
        lineno += 1


def bytes2human(n):
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = int(float(n) / prefix[s])
            return '%s%s' % (value, s)
    return "%sB" % n


def poll(interval):
    # sleep some time
    time.sleep(interval)
    procs = []
    procs_status = {}
    for p in psutil.process_iter():
        try:
            p.dict = p.as_dict(['username', 'nice', 'memory_info',
                                'memory_percent', 'cpu_percent',
                                'cpu_times', 'name', 'status'])
            try:
                procs_status[p.dict['status']] += 1
            except KeyError:
                procs_status[p.dict['status']] = 1
        except psutil.NoSuchProcess:
            pass
        else:
            procs.append(p)

    # return processes sorted by CPU percent usage
    processes = sorted(procs, key=lambda p: p.dict['cpu_percent'],
                       reverse=True)
    return (processes, procs_status)


def print_header(procs_status, num_procs):
    def get_dashes(perc):
        dashes = "|" * int((float(perc) / 10 * 4))
        empty_dashes = " " * (40 - len(dashes))
        return dashes, empty_dashes

    # cpu usage
    percs = psutil.cpu_percent(interval=0, percpu=True)
    for cpu_num, perc in enumerate(percs):
        dashes, empty_dashes = get_dashes(perc)
        print_line(" CPU%-2s [%s%s] %5s%%" % (cpu_num, dashes, empty_dashes,
                                              perc))
    mem = psutil.virtual_memory()
    dashes, empty_dashes = get_dashes(mem.percent)
    line = " Mem   [%s%s] %5s%% %6s / %s" % (
        dashes, empty_dashes,
        mem.percent,
        str(int(mem.used / 1024 / 1024)) + "M",
        str(int(mem.total / 1024 / 1024)) + "M"
    )
    print_line(line)

    # swap usage
    swap = psutil.swap_memory()
    dashes, empty_dashes = get_dashes(swap.percent)
    line = " Swap  [%s%s] %5s%% %6s / %s" % (
        dashes, empty_dashes,
        swap.percent,
        str(int(swap.used / 1024 / 1024)) + "M",
        str(int(swap.total / 1024 / 1024)) + "M"
    )
    print_line(line)

    # processes number and status
    st = []
    for x, y in procs_status.items():
        if y:
            st.append("%s=%s" % (x, y))
    st.sort(key=lambda x: x[:3] in ('run', 'sle'), reverse=1)
    print_line(" Processes: %s (%s)" % (num_procs, ', '.join(st)))
    # load average, uptime
    uptime = datetime.datetime.now() - \
        datetime.datetime.fromtimestamp(psutil.boot_time())
    av1, av2, av3 = os.getloadavg()
    line = " Load average: %.2f %.2f %.2f  Uptime: %s" \
        % (av1, av2, av3, str(uptime).split('.')[0])
    print_line(line)


def refresh_window(procs, procs_status):
    """Print results on screen by using curses."""
    curses.endwin()
    templ = "%-6s %-8s %4s %5s %5s %6s %4s %9s  %2s"
    win.erase()
    header = templ % ("PID", "USER", "NI", "VIRT", "RES", "CPU%", "MEM%",
                      "TIME+", "NAME")
    print_header(procs_status, len(procs))
    print_line("")
    print_line(header, highlight=True)
    for p in procs:
        # TIME+ column shows process CPU cumulative time and it
        # is expressed as: "mm:ss.ms"
        if p.dict['cpu_times'] is not None:
            ctime = datetime.timedelta(seconds=sum(p.dict['cpu_times']))
            ctime = "%s:%s.%s" % (ctime.seconds // 60 % 60,
                                  str((ctime.seconds % 60)).zfill(2),
                                  str(ctime.microseconds)[:2])
        else:
            ctime = ''
        if p.dict['memory_percent'] is not None:
            p.dict['memory_percent'] = round(p.dict['memory_percent'], 1)
        else:
            p.dict['memory_percent'] = ''
        if p.dict['cpu_percent'] is None:
            p.dict['cpu_percent'] = ''
        if p.dict['username']:
            username = p.dict['username'][:8]
        else:
            username = ""
        line = templ % (p.pid,
                        username,
                        p.dict['nice'],
                        bytes2human(getattr(p.dict['memory_info'], 'vms', 0)),
                        bytes2human(getattr(p.dict['memory_info'], 'rss', 0)),
                        p.dict['cpu_percent'],
                        p.dict['memory_percent'],
                        ctime,
                        p.dict['name'] or '',
                        )
        try:
            print_line(line)
        except curses.error:
            break
        win.refresh()


def main():
    try:
        interval = 0
        while True:
            args = poll(interval)
            refresh_window(*args)
            interval = 1
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    main()