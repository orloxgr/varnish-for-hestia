#!/usr/bin/python3
"""Rebuild before native startup when a package upgrade changes its ABI."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from native_build import build

if __name__=='__main__':
    build()
