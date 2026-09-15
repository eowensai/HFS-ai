"""Compatibility entry point for the retained September 14 machine directory."""
import argparse
from pathlib import Path
import subprocess
import sys

CURRENT = Path('/home/eko/hfsai/scripts/deployment.py')
ACTIONS = {'dflash': 'adopt', 'mtp': 'mtp', 'previous': 'previous-fp4', 'status': 'status'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS)
    args = parser.parse_args()
    if not CURRENT.is_file():
        raise SystemExit('Maintained HFS-ai manager is missing; no legacy restoration attempted.')
    subprocess.run([sys.executable, str(CURRENT), 'current', ACTIONS[args.action]], check=True)


if __name__ == '__main__':
    main()
