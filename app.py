from src.attendance import build_parser
from src.gui import launch_app


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "command", None) is None:
        launch_app()
        return

    args.handler(args)


if __name__ == "__main__":
    main()
