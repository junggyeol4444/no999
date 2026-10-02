from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .database import Database
from .services import NovelFactory
from .diagnostics import run_self_test


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel-factory", description="AI Novel Factory 관리 CLI")
    parser.add_argument("--data-dir", type=Path, help="데이터 저장 디렉터리")
    commands = parser.add_subparsers(dest="command", required=True)
    reference = commands.add_parser("analyze", help="참고소설을 등록하고 분석합니다")
    reference.add_argument("file", type=Path)
    reference.add_argument("--title")
    novel = commands.add_parser("create-novel", help="새 작품과 Novel Bible을 생성합니다")
    novel.add_argument("title")
    novel.add_argument("--genre", required=True)
    novel.add_argument("--premise", required=True)
    novel.add_argument("--episodes", type=int, default=250)
    commands.add_parser("list", help="등록된 작품과 참고소설을 표시합니다")
    commands.add_parser("desktop", help="데스크톱 프로그램을 실행합니다")
    commands.add_parser("self-test", help="DB·분석·메모리·회차 파이프라인을 진단합니다")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    base = args.data_dir.resolve() if args.data_dir else Settings.from_env().data_dir
    settings = Settings(base, base / "novel_factory.db", base / "uploads")
    settings.ensure_directories()
    factory = NovelFactory(Database(settings.database_path), settings.upload_dir)
    if args.command == "analyze":
        reference = factory.register_reference(args.title or args.file.stem, args.file)
        output = factory.analyze_reference(reference["id"])
    elif args.command == "create-novel":
        output = factory.create_novel({"title": args.title, "genre": args.genre, "premise": args.premise,
                                       "target_episodes": args.episodes, "characters_per_episode": 5000})
    elif args.command == "list":
        output = {"novels": factory.list_novels(), "references": factory.list_references()}
    elif args.command == "desktop":
        from .desktop import main as desktop_main
        desktop_main(factory=factory)
        return
    else:
        report = run_self_test()
        print(report.to_json())
        raise SystemExit(0 if report.passed else 1)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
