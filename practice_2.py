import argparse
import os
import sys
from urllib.parse import urlparse


def file_out(value: str) -> str: #проверяем, что выдает нормальный файл
    if not value.endswith(".png"):
        raise argparse.ArgumentTypeError(
            f"Неверное имя файла '{value}': требуется расширение .png"
        )
    return value


def positive_int(value: str) -> int: #проверяем, что нормально ввели глубину
    try:
        num = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': требуется целое число"
        )
    if num <= 0:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': число должно быть > 0"
        )
    return num


def build_parser() -> argparse.ArgumentParser: #парсер для аргументов
    parser = argparse.ArgumentParser(
        description="Практика 2: Инструмент визуализации графа зависимостей"
    )

    parser.add_argument(
        "-p", "--package-name",
        required=True,
        type=str,
        help="Имя анализируемого пакета"
    )

    parser.add_argument(
        "-r", "--repo",
        required=True,
        type=str,
        help="URL репозитория или путь к тестовому репозиторию"
    )

    parser.add_argument(
        "--mode",
        choices=["real", "test"],
        default="real",
        help="Режим работы: real (реальный репозиторий в сети) или test (тестовый в системе)"
    )

    parser.add_argument(
        "-o", "--out",
        default="depgraph.png",
        type=file_out,
        help="Имя файла изображения графа (должно оканчиваться на .png)"
    )

    parser.add_argument(
        "-d", "--max-depth",
        default=1,
        type=positive_int,
        help="Максимальная глубина анализа зависимостей (целое положительное число)"
    )

    return parser


def validate_package_name(name: str) -> None: #проверяем имя пакета
    if not name.strip():
        raise SystemExit("<Ошибка> Имя пакета не может быть пустым")


def validate_repo(args: argparse.Namespace) -> None: #проверяем адрес репозитория
    repo = args.repo
    mode = args.mode

    if mode == "test":
        # Для тестового режима нужен существующий путь (файл или директория)
        if not os.path.exists(repo):
            raise SystemExit(
                f"<Ошибка> Тестовый репозиторий '{repo}' не найден на диске"
            )
    elif mode == "real":
        # Для реального режима нужен URL
        parsed = urlparse(repo)
        if parsed.scheme not in ("http", "https"):
            raise SystemExit(
                f"<Ошибка> Для режима real ожидается URL (http/https), получено: '{repo}'"
            )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    validate_package_name(args.package_name)
    validate_repo(args)

    print("Параметры запуска:")
    print(f" package_name = {args.package_name}")
    print(f" repo         = {args.repo}")
    print(f" mode         = {args.mode}")
    print(f" out          = {args.out}")
    print(f" max_depth    = {args.max_depth}")


if __name__ == "__main__":
    main()
