#!/usr/bin/env python3
"""Wrapper para tarsila_vaga (lib). A logica mora em /usr/local/lib/tarsila/."""

import sys
sys.path.insert(0, "/usr/local/lib/tarsila")

import tarsila_vaga

if __name__ == "__main__":
    sys.exit(tarsila_vaga.main())
