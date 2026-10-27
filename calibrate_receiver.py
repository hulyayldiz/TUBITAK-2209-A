"""Create a separate-session checked receiver profile; never overwrite one."""
import argparse
import json
from pathlib import Path

from receiver_registry import calibrate, save_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal', required=True)
    parser.add_argument('--validation', required=True)
    parser.add_argument('--receiver-id', required=True)
    parser.add_argument('--profile-id', required=True)
    parser.add_argument('--motion', choices=['static', 'moving'], required=True)
    parser.add_argument('--warmup-s', type=float, default=30.)
    parser.add_argument('--position-sigma-m', type=float)
    parser.add_argument('--trusted-normal', action='store_true')
    parser.add_argument('--output-dir', type=Path, help='Export directory; default installs in receiver_profiles')
    args = parser.parse_args()
    try:
        if args.output_dir is not None:
            import receiver_registry
            receiver_registry.PROFILE_DIR = args.output_dir.resolve()
        profile = calibrate(args.normal, args.validation, receiver_id=args.receiver_id,
            profile_id=args.profile_id, motion=args.motion, trusted_normal=args.trusted_normal,
            warmup_s=args.warmup_s, position_sigma_m=args.position_sigma_m)
        if profile['validation']['status'] != 'passed':
            print(json.dumps(profile, ensure_ascii=False, indent=2))
            parser.exit(1, 'Normal-session validation failed; profile was not installed.\n')
        print(save_profile(profile))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Receiver calibration rejected: {error}\n')


if __name__ == '__main__':
    main()
