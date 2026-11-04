import pandas as pd
import pytest

import acs_config as cfg
import clean

# A neutral default for every variable; tests override what they care about.
DEFAULTS = {}
for _base in cfg.ALL_BASES:
    DEFAULTS[_base + 'E'] = 100
    DEFAULTS[_base + 'M'] = 10


@pytest.fixture
def make_raw():
    """Build a raw API-style frame (numeric variable columns, like clean.to_frame returns) from per-row overrides"""
    def build(*row_overrides, geography='tract'):
        rows = []
        for i, overrides in enumerate(row_overrides or [{}]):
            row = {**DEFAULTS, **overrides}
            row.update({'NAME': f'Tract {i}', 'state': '12', 'county': '086', 'tract': f'{i:06d}'})
            rows.append(row)
        return pd.DataFrame(rows)
    return build


@pytest.fixture
def cleaned():
    """Run the cleaning for a raw frame and return the cleaned frame (log discarded)"""
    def run(raw, api_year=2024, geography='tract'):
        frame, _ = clean.clean_dataset(raw, api_year, geography, '2020-2024')
        return frame
    return run
