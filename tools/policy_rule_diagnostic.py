"""Expose best-then-veto policy decisions; do not change the frozen rule."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.sim.io import tree_sha256, value, write_json


def diagnose(root):
    records = []
    checked = rejected = 0
    sources = {}
    for path in sorted(root.glob('*/results.json')):
        result = json.loads(path.read_text(encoding='utf-8'))
        params = result['parameters']
        if params.get('strategy') != 'adaptive':
            continue
        checked += 1
        minimum = float(value(params, 'management', 'T_min', 3.))
        benefit_minimum = float(params.get('adaptive_options', {}).get('minimum_benefit_myr', 1e-6))
        sources[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        for decision in result['placements']['adaptive_decisions']:
            if decision['action'] != 'retreat_assessment' or decision.get('reason') != 'forecast_protection_below_minimum':
                continue
            rejected += 1
            feasible = [row for row in decision['candidates']
                        if row['delta_E_b'] > benefit_minimum and row['protection_q10'] >= minimum]
            if feasible:
                records.append({'run': path.parent.name, 't': decision['t'],
                                'minimum_years': minimum,
                                'rejected_highest_score': decision['best'],
                                'highest_score_passing_protection': max(feasible, key=lambda row: row['score'])})
    return {'code_sha256': tree_sha256('src'), 'checked_deterministic_runs': checked,
            'protection_veto_decisions': rejected, 'vetoes_with_passing_alternative': len(records),
            'examples': records, 'input_sha256': sources,
            'contract': 'SCENARIOS_STRATEGIES section 4.1: maximize benefit/cost, then veto the best proposal by protection period.',
            'interpretation': 'Implementation follows the current contract. This is not optimization over all protection-feasible candidates. A feasible-first rule is a policy change and needs a paired rerun; no alternate-policy outcome is inferred here.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    root = Path(args.root)
    report = diagnose(root)
    write_json(root/'policy_rule_diagnostic.json', report)
    print('POLICY RULE DIAGNOSTIC', report['vetoes_with_passing_alternative'],
          'vetoes with a passing alternative in', report['checked_deterministic_runs'], 'deterministic runs')


if __name__ == '__main__':
    main()
