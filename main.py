import argparse
import logging

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="PreAuth Agent Worker")
    parser.add_argument(
        "--mode",
        choices=["worker", "single"],
        default="worker",
        help="worker = poll loop | single = process one preauth_id and exit"
    )
    parser.add_argument(
        "--preauth-id",
        type=str,
        help="Required when --mode=single"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Poll interval in seconds (worker mode only)"
    )
    args = parser.parse_args()

    if args.mode == "single":
        if not args.preauth_id:
            parser.error("--preauth-id is required when --mode=single")
        from src.worker.worker import process_preauth
        process_preauth(args.preauth_id)

    elif args.mode == "worker":
        from src.worker.worker import run_worker
        run_worker(poll_interval_seconds=args.interval)


if __name__ == "__main__":
    main()
