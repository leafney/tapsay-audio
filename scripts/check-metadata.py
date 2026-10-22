#!/usr/bin/env python3
"""Validate the single product configuration."""
import argparse
import sys
from product import load_product

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata')
    args = parser.parse_args()
    load_product(args.metadata)
    print('产品配置检查通过')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError) as error:
        print('产品配置检查失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
