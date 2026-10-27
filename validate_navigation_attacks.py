"""Before/after synthetic security regression; models are never trained here."""
import importlib.util
import json

import torch

import navigation
import validation
from real_data_catalog import ROOT

OUTPUT = ROOT/'validation_results'/'navigation_fix_20261023'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def evaluate():
    torch.set_num_threads(1)
    old_fusion = module('saved_fusion_before_navigation_fix', OUTPUT/'baseline_fusion.py')
    old_navigation = module('saved_navigation_before_fix', OUTPUT/'baseline_navigation.py')
    old_navigation.get_fused_position = old_fusion.get_fused_position
    scenarios = ('normal', 'jamming', 'spoofing', 'slow_spoofing', 'stealth_spoofing')
    cases = []
    original = validation.process_navigation
    try:
        for seed in (91001, 91002, 91003):
            for scenario in scenarios:
                validation.process_navigation = old_navigation.process_navigation
                before = validation.evaluate_synthetic(seed, scenario, 600)
                validation.process_navigation = navigation.process_navigation
                after = validation.evaluate_synthetic(seed, scenario, 600)
                unchanged = all(before[key] == after[key] for key in
                    ('layers', 'phase_metrics', 'navigation_rmse_m', 'ekf_rmse_m'))
                cases.append(dict(seed=seed, scenario=scenario, synthetic=True,
                                  unchanged=unchanged, before=before, after=after))
            print(f'Synthetic security comparison seed {seed} completed', flush=True)
    finally:
        validation.process_navigation = original
    report = dict(protocol='Same models/inputs/seeds before and after navigation fix. '
                  'Synthetic independent-IMU scenarios; no training or threshold fitting.',
                  samples_per_version=9000, cases=cases,
                  all_security_metrics_unchanged=all(row['unchanged'] for row in cases),
                  limitations='Synthetic regression does not certify real receiver or unknown attack performance.')
    (OUTPUT/'synthetic_security_comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['all_security_metrics_unchanged']:
        raise ValueError('Synthetic security regression changed; inspect before/after report')
    print('All 15 synthetic security cases retain their previous metrics.', flush=True)
    return report


if __name__ == '__main__':
    evaluate()
