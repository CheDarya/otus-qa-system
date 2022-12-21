import argparse
import csv
from subprocess import Popen, PIPE
from datetime import datetime
from collections import namedtuple

Proc = namedtuple('Proc', ('pid', 'user', 'cpu', 'mem', 'cmd'))

KB = 1024

# ps -a -x -o pid=pid,user=user,pcpu=cpu,rsz=mem,comm=cmd | sed -r  "s/ +/|/g"

PS = ['/usr/bin/ps', '-a', '-x', '-o',
      'pid=pid,user=user,pcpu=cpu,rsz=mem,comm=cmd']

SED = ['/usr/bin/sed', '-r', "s/ +/|/g"]

filename = datetime.now().strftime("%d-%m-%Y-%H:%M:%S-scan.txt")

parser = argparse.ArgumentParser()
parser.add_argument('--to-file', default=False,
                    action=argparse.BooleanOptionalAction)
args = parser.parse_args()


def tryconvert(*types):
    def convert(value):
        for t in types:
            try:
                return t(value)
            except (ValueError, TypeError):
                continue
        return value
    return convert


def get_procs():
    try:
        with Popen(PS, stdout=PIPE, universal_newlines=True) as ps:
            try:
                with Popen(SED, stdin=ps.stdout, stdout=PIPE, universal_newlines=True) as sed:
                    reader = csv.DictReader(sed.stdout, delimiter='|')
                    raw = [{k.strip(): tryconvert(int, float)(v.strip())
                            for k, v in row.items() if v} for row in list(reader)]
            except Exception as e:
                raise
    except Exception as e:
        print(e)
        exit(1)

    return raw


def update_user(users, row):
    user = row['user']

    if user not in users:
        users.update({user: {'cpu': 0, 'mem': 0, 'procs': 0}})

    for key in ('cpu', 'mem'):
        users[user][key] += row[key]
    users[user]['procs'] += 1


def get_max_usage(data, param) -> Proc:
    data = sorted(data, key=lambda x: x[param], reverse=True)
    return Proc(*data[0].values())


def out_to_file(data, file):
    try:
        with open(file, 'w') as f:
            f.writelines(f'{line}\n' for line in data)
    except Exception as e:
        print(e)
        exit(1)


def out_to_console(data):
    for line in data:
        print(line)


def prepare_report(result):
    users = {}
    for row in result:
        update_user(users, row)

    users = dict(
        sorted(users.items(), key=lambda x: x[1]['procs'], reverse=True))

    mem = cpu = procs = 0

    for user, data in users.items():
        mem += data['mem']
        cpu += data['cpu']
        procs += data['procs']

    max_mem_consumer = get_max_usage(result, 'mem')
    max_cpu_consumer = get_max_usage(result, 'cpu')

    report = []
    report.append(f"Активные пользователи системы: {', '.join(users.keys())}")
    report.append(f"Всего процессов запущено: {procs}")
    report.append(f"Пользовательских процессов:")
    for user, data in users.items():
        report.append(f"{user}: {data['procs']}")
    report.append(
        f"Всего физической памяти используется: {(mem / KB):.1f} mb")
    report.append(f"Всего CPU используется: {cpu:.1f} %")
    report.append(
        f"Больше всего памяти использует {max_mem_consumer.cmd} [pid{max_mem_consumer.pid}]: {max_mem_consumer.mem / KB:.1f} mb")
    report.append(
        f"Больше всего CPU использует {max_cpu_consumer.cmd} [pid {max_cpu_consumer.pid}]: {max_cpu_consumer.cpu} %")

    return report


def main():
    rep = prepare_report(get_procs())
    out_to_console(rep)

    if args.to_file:
        out_to_file(rep, filename)
        print(f"Данные сохранены в файл {filename}")


if __name__ == '__main__':
    main()
