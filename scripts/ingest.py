#!/usr/bin/env python3
"""Run the project's ingestion CLI from the repository scripts directory."""
import runpy

if __name__ == '__main__':
    runpy.run_module('rtve_rag.ingestion.cli', run_name='__main__')
