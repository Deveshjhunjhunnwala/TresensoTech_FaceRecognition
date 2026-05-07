from src.attendance import build_parser, launch_web_app


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "command", None) is None:
        launch_web_app()
        return

    args.handler(args)


if __name__ == "__main__":
    main()
