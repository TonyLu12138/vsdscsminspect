#! /usr/bin/env python3
import argparse
import sys
from log_record import Logger
from control import Control, display_version

def main():
    parser = argparse.ArgumentParser(description='csmpreinstaller')
    parser.add_argument('-v', '--version', action='store_true',
                        help='show version information')
    args = parser.parse_args()

    logger = Logger("vsdscsminspect")

    if args.version:
        display_version()
        sys.exit()
    
    control = Control(logger)
    control.all_control()

if __name__ == '__main__':
    main()
