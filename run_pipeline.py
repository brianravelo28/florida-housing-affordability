"""
Rebuilds every data file the dashboard reads: python run_pipeline.py
Steps: fetch the Census API tables, clean them, simplify the boundary files.
Needs the CENSUS_API_KEY environment variable and the packages in requirements-pipeline.txt.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import clean
import fetch_acs
import geometry

if __name__ == '__main__':
    fetch_acs.main()
    clean.main()
    geometry.main()
