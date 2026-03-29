import argparse

from src.enrollment import enroll_person
from src.exporter import export_attendance_to_excel, export_today
from src.gui import launch_app
from src.recognition import recognize_and_mark
from src.training import train_model


def handle_enroll(args: argparse.Namespace) -> None:
    enroll_person(name=args.name, max_images=args.images)


def handle_train(_: argparse.Namespace) -> None:
    train_model()


def handle_recognize(_: argparse.Namespace) -> None:
    recognize_and_mark()


def handle_gui(_: argparse.Namespace) -> None:
    launch_app()


def handle_export(args: argparse.Namespace) -> None:
    if args.today:
        file_path = export_today()
    else:
        if not args.start_date or not args.end_date:
            raise ValueError("Provide --today or both --start-date and --end-date.")
        file_path = export_attendance_to_excel(args.start_date, args.end_date)
    print(f"Exported to {file_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Facial recognition attendance system")
    subparsers = parser.add_subparsers(dest="command", required=False)

    enroll_parser = subparsers.add_parser("enroll", help="Capture face images for one person")
    enroll_parser.add_argument("--name", required=True, help="Person name")
    enroll_parser.add_argument("--images", type=int, default=10, help="Number of images to capture")
    enroll_parser.set_defaults(handler=handle_enroll)

    train_parser = subparsers.add_parser("train", help="Generate encodings from saved face images")
    train_parser.set_defaults(handler=handle_train)

    recognize_parser = subparsers.add_parser("recognize", help="Recognize faces and mark attendance")
    recognize_parser.set_defaults(handler=handle_recognize)

    export_parser = subparsers.add_parser("export", help="Export attendance to Excel")
    export_parser.add_argument("--today", action="store_true", help="Export only today's attendance")
    export_parser.add_argument("--start-date", default="", help="Start date in YYYY-MM-DD format")
    export_parser.add_argument("--end-date", default="", help="End date in YYYY-MM-DD format")
    export_parser.set_defaults(handler=handle_export)

    gui_parser = subparsers.add_parser("gui", help="Launch the desktop GUI")
    gui_parser.set_defaults(handler=handle_gui)

    return parser
